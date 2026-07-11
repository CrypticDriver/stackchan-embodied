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

PUSH_URL = "http://127.0.0.1:9101/goudan/say"


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
    req = urllib.request.Request(
        PUSH_URL,
        data=json.dumps({"text": event.speak}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.load(r)
            if not resp.get("ok"):
                print("  push failed:", resp, flush=True)
    except Exception as e:  # noqa: BLE001
        print("  push error:", e, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="只打印, 不让设备说话")
    ap.add_argument("--interval", type=int, default=20)
    args = ap.parse_args()

    server = os.environ.get("HAPPY_SERVER_URL", "https://d2nkikyt4i91kk.cloudfront.net")
    quiet_spec = os.environ.get("QUIET_HOURS", "")

    poller = HappyPoller(server)
    watcher = Watcher()
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
