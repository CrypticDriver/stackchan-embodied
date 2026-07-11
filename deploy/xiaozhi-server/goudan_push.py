"""goudan_push — xiaozhi-server 主动播报插件 (stackchan-embodied M2)。

在不改动上游架构的前提下补一条"服务器→设备主动说话"通道:
- 连接注册表: monkeypatch ConnectionHandler.handle_connection 记录 device_id→conn
- loopback HTTP :9101 /goudan/say {"text": "...", "device_id": 可选}
  → 找到活跃连接, 用 conn.tts.tts_one_sentence 走完整 TTS 管线(设备就会开口+动嘴)

安装: 由 app.py 侧 sitecustomize 或启动包装导入 (见 run_with_push.py)。
"""

import asyncio
import json
import os
import time

from aiohttp import web

import uuid

from core.connection import ConnectionHandler
from core.handle.intentHandler import speak_txt
from core.handle.sendAudioHandle import send_tts_message

_conns: dict[str, "ConnectionHandler"] = {}
_orig_handle = ConnectionHandler.handle_connection


async def _tracking_handle(self, ws):
    try:
        await _orig_handle(self, ws)
    finally:
        did = getattr(self, "device_id", None)
        if did and _conns.get(did) is self:
            _conns.pop(did, None)


_orig_post_auth = None


def _register(self):
    did = getattr(self, "device_id", None)
    if did:
        _conns[did] = self


class _RegisterOnAttr:
    """在 handle_connection 里 device_id 赋值后注册: 用属性钩子最稳。"""


_orig_setattr = ConnectionHandler.__setattr__


def _hook_setattr(self, name, value):
    _orig_setattr(self, name, value)
    if name == "device_id" and value:
        _conns[value] = self


ConnectionHandler.__setattr__ = _hook_setattr
ConnectionHandler.handle_connection = _tracking_handle


BODY_TOKEN = os.environ.get("BODY_TOKEN", "")


async def _say(request: web.Request) -> web.Response:
    if BODY_TOKEN and request.headers.get("X-Body-Token") != BODY_TOKEN:
        return web.json_response({"error": "unauthorized"}, status=401)
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    text = (body.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "text required"}, status=400)

    device_id = body.get("device_id")
    conn = None
    if device_id:
        conn = _conns.get(device_id)
    elif _conns:
        conn = next(iter(_conns.values()))

    if conn is None or getattr(conn, "websocket", None) is None:
        return web.json_response({"error": "device not connected", "known": list(_conns)}, status=404)

    try:
        # 防回音/插嘴: 设备正在说话或在听用户说话时, 等一会儿再播 (最多 30s)
        for _ in range(60):
            if not getattr(conn, "client_is_speaking", False):
                break
            await asyncio.sleep(0.5)
        # 关键: 设备只在收到 tts start 后进入 Speaking 态才播放音频 (application.cc OnIncomingJson)
        await send_tts_message(conn, "start")
        # 完整播报流程 (同 intent 语音指令): FIRST 引导帧 → 正文 → LAST 收尾
        conn.sentence_id = uuid.uuid4().hex
        speak_txt(conn, text)
        return web.json_response({"ok": True, "device": conn.device_id, "text": text})
    except Exception as e:  # noqa: BLE001
        return web.json_response({"error": str(e)}, status=500)


async def _devices(_: web.Request) -> web.Response:
    return web.json_response({
        "connected": [
            {"device_id": d, "client_ip": getattr(c, "client_ip", "?")}
            for d, c in _conns.items()
        ]
    })


async def start_push_api():
    app = web.Application()
    app.router.add_post("/goudan/say", _say)
    app.router.add_get("/goudan/devices", _devices)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 9101)
    await site.start()


def install():
    loop = asyncio.get_event_loop()
    loop.create_task(start_push_api())
