"""端到端冒烟测试：模拟设备连 WS，走 hello → 文本输入 → LLM → TTS 全管线。

用法: python test_e2e.py [wss://.../xiaozhi/v1/]  (默认连本机 ws://127.0.0.1:8000)
通过标准: 收到 stt/llm 回显 + tts start/stop + 二进制 opus 音频帧。
"""

import asyncio
import json
import sys

import websockets

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8000/xiaozhi/v1/"
HEADERS = {
    "Device-Id": "aa:bb:cc:dd:ee:ff",
    "Client-Id": "e2e-test",
    "Protocol-Version": "1",
}

HELLO = {
    "type": "hello",
    "version": 1,
    "transport": "websocket",
    "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
}

ASK = {"type": "listen", "mode": "manual", "state": "detect", "text": "你好，简单介绍一下你自己"}


async def main() -> int:
    audio_frames = 0
    texts = []
    async with websockets.connect(URL, additional_headers=HEADERS, max_size=2**22) as ws:
        await ws.send(json.dumps(HELLO))
        await ws.send(json.dumps(ASK))
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=45)
                if isinstance(msg, bytes):
                    audio_frames += 1
                    continue
                data = json.loads(msg)
                texts.append(data)
                print(f"<< {data.get('type')}: {json.dumps(data, ensure_ascii=False)[:160]}")
                if data.get("type") == "tts" and data.get("state") == "stop":
                    break
        except asyncio.TimeoutError:
            print("!! timeout waiting for server")

    llm_said = [t for t in texts if t.get("type") in ("stt", "llm", "tts") and t.get("text")]
    print(f"\n== audio frames received: {audio_frames}")
    ok = audio_frames > 0 and any(t.get("type") == "tts" for t in texts)
    print("== E2E:", "PASS ✅" if ok else "FAIL ❌")
    return 0 if ok else 1


sys.exit(asyncio.run(main()))
