"""狗蛋控制台状态聚合 API (只读)。

监听 0.0.0.0:9100 (SG 只放 ALB, 等效内网), 经 ALB/CloudFront 暴露 /console/api/status。
鉴权: X-Console-Token 头 (CONSOLE_TOKEN 环境变量)。
聚合: systemd 三服务状态 / 设备最近活动(journald) / 主机资源。
"""

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone

from aiohttp import web

TOKEN = os.environ["CONSOLE_TOKEN"]
DEVICE_MAC = "44:1b:f6:e3:85:e4"

SERVICES = {
    "litellm": "stackchan-litellm",
    "xiaozhi": "stackchan-xiaozhi",
    "goserver": "stackchan-goserver",
}


def _run(cmd: list[str], timeout: int = 5) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception:
        return ""


def service_status() -> dict:
    out = {}
    for key, unit in SERVICES.items():
        active = _run(["systemctl", "is-active", unit]) == "active"
        since = _run(["systemctl", "show", unit, "--property=ActiveEnterTimestamp", "--value"])
        out[key] = {"active": active, "since": since}
    return out


def device_activity() -> dict:
    """从 journald 提取设备最近活动。"""
    logs = _run(["journalctl", "-u", "stackchan-xiaozhi", "--since", "-30min",
                 "-o", "cat", "--no-pager"], timeout=8)
    last_ota = last_chat = last_said = None
    chat_count = 0
    for line in logs.split("\n"):
        ts = line[:21].strip("[]")
        if f"OTA请求设备ID: {DEVICE_MAC}" in line:
            m = re.match(r"(\d{6} \d{2}:\d{2}:\d{2})", line)
            last_ota = m.group(1) if m else ts
        if "识别文本:" in line:
            m2 = re.search(r"识别文本: (.+)", line)
            if m2:
                last_chat = m2.group(1)[:60]
                chat_count += 1
        if "发送第一段语音:" in line:
            m3 = re.search(r"发送第一段语音: (.+)", line)
            if m3:
                last_said = m3.group(1)[:60]
    ws_lines = [l for l in logs.split("\n") if "conn - Headers" in l and DEVICE_MAC in l]
    return {
        "mac": DEVICE_MAC,
        "voice_ws_connected_recently": bool(ws_lines),
        "last_ota_check": last_ota,
        "last_heard": last_chat,
        "last_said": last_said,
        "chats_30min": chat_count,
    }


def host_status() -> dict:
    mem = _run(["free", "-m"]).split("\n")
    mem_line = mem[1].split() if len(mem) > 1 else ["", "0", "0"]
    disk = _run(["df", "-h", "/"]).split("\n")
    disk_line = disk[1].split() if len(disk) > 1 else ["", "", "", "", "0%"]
    load = _run(["cat", "/proc/loadavg"]).split()[:3]
    return {
        "mem_used_mb": int(mem_line[2]) if mem_line[2].isdigit() else 0,
        "mem_total_mb": int(mem_line[1]) if mem_line[1].isdigit() else 0,
        "disk_used_pct": disk_line[4],
        "load": load,
    }


async def status(request: web.Request) -> web.Response:
    if request.headers.get("X-Console-Token") != TOKEN:
        return web.json_response({"error": "unauthorized"}, status=401)
    return web.json_response({
        "ts": datetime.now(timezone.utc).isoformat(),
        "services": service_status(),
        "device": device_activity(),
        "host": host_status(),
    }, headers={"Cache-Control": "no-store"})


async def health(_: web.Request) -> web.Response:
    return web.Response(text="ok")


app = web.Application()
app.router.add_get("/console/api/status", status)
app.router.add_get("/console/api/health", health)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=9100, print=None)
