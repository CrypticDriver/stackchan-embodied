"""M2 监工主循环: Happy 轮询 → 状态机 → 狗蛋播报。

播报通道 = xiaozhi-server 的 goudan_push 插件 (127.0.0.1:9101 /goudan/say),
设备用现有语音链路开口说话 (自带表情+嘴型)。--fake 模式只打印不播报。

用法:
    python -m happy_watcher.main [--fake] [--interval 20]
环境:
    HAPPY_SERVER_URL (默认自托管地址) / QUIET_HOURS (如 "22-8")
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

from .poller import HappyPoller
from .state_machine import RobotEvent, Watcher

PUSH_URL = os.environ.get("PUSH_URL", "http://127.0.0.1:9101/goudan/say")
AGENT_URL = os.environ.get("AGENT_URL", "http://10.0.1.80:18790/v1/chat/completions")
AGENT_TOKEN = os.environ.get("OPENCLAW_TOKEN", "")
USE_AGENT_PHRASING = os.environ.get("AGENT_PHRASING", "1") == "1"


def agent_phrase(event: "RobotEvent") -> str | None:
    """把监工事件交给小狗蛋组织语言 (它有记忆和上下文判断)。失败返回 None 用模板兜底。"""
    if not (USE_AGENT_PHRASING and AGENT_TOKEN):
        return None
    prompt = (
        f"[监工事件] kind={event.kind} session={event.session_id[:10]} 模板播报=「{event.speak}」\n"
        "你现在要通过桌面机器人身体开口向大哥播报这件事。用你自己的话说, 一两句, 口语化,"
        "禁 markdown。直接输出要说的话, 不要任何解释。")
    req = urllib.request.Request(
        AGENT_URL,
        data=json.dumps({"model": "openclaw/xiaogoudan", "user": "happy-watcher",
                          "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {AGENT_TOKEN}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            text = json.load(r)["choices"][0]["message"]["content"].strip()
            return text[:120] if text else None
    except Exception as e:  # noqa: BLE001
        print("  agent phrasing failed, fallback to template:", e, flush=True)
        return None


def in_quiet_hours(spec: str) -> bool:
    if not spec:
        return False
    try:
        start, end = (int(x) for x in spec.split("-"))
    except ValueError:
        return False
    h = time.localtime().tm_hour
    return (start <= h or h < end) if start > end else (start <= h < end)


def speak(event: RobotEvent, fake: bool) -> None:
    line = f"[{event.kind}] {event.speak or '(表情)'} <- session {event.session_id[:10]}"
    print(time.strftime("%H:%M:%S"), line, flush=True)
    if fake or not event.speak:
        return
    phrased = agent_phrase(event)
    if phrased:
        event = RobotEvent(event.kind, phrased, event.session_id)
        print(time.strftime("%H:%M:%S"), f"  agent说法: {phrased}", flush=True)
    req = urllib.request.Request(
        PUSH_URL,
        data=json.dumps({"text": event.speak}).encode(),
        headers={"Content-Type": "application/json",
                 "X-Body-Token": os.environ.get("BODY_TOKEN", "")},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.load(r)
            if not resp.get("ok"):
                print("  push failed:", resp, flush=True)
    except Exception as e:  # noqa: BLE001
        print("  push error:", e, flush=True)




def start_work_query_api(poller):
    """只读工作状态查询 API (us-east 本机, 有 Happy 凭据)。
    check_work 工具经 peering 调它, 而不是自己解密 (凭据只在 us-east)。"""
    import threading, json as _json
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            try:
                snaps = poller.fetch()
                running = [s.title for s in snaps if s.state.value == "running"]
                pending = poller.pending_requests()
                body = _json.dumps({
                    "pending": [{"title": r["title"], "tool": r["tool"],
                                 "command": r["command"][:80]} for r in pending],
                    "running": running,
                }, ensure_ascii=False).encode()
                self.send_response(200); self.send_header("Content-Type","application/json")
                self.end_headers(); self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())

    def run():
        HTTPServer(("0.0.0.0", 9102), H).serve_forever()
    threading.Thread(target=run, daemon=True).start()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="只打印, 不让设备说话")
    ap.add_argument("--interval", type=int, default=20)
    args = ap.parse_args()

    server = os.environ.get("HAPPY_SERVER_URL", "https://d2nkikyt4i91kk.cloudfront.net")
    quiet_spec = os.environ.get("QUIET_HOURS", "")

    state_path = os.environ.get("WATCHER_STATE", "/home/ec2-user/.happy/goudan-watcher-state.json")
    poller = HappyPoller(server)
    start_work_query_api(poller)
    watcher = Watcher(state_path=state_path)
    print(f"happy-watcher up: server={server} interval={args.interval}s fake={args.fake}", flush=True)

    while True:
        try:
            watcher.quiet = in_quiet_hours(quiet_spec)
            events = watcher.observe(poller.fetch())
            for ev in events:
                speak(ev, args.fake)
        except Exception as e:  # noqa: BLE001
            print("poll error:", e, flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
