"""BodyClient — 伪装 App 客户端驱动 StackChan 身体。

用法:
    async with BodyClient(server, device_mac, key_path) as body:
        await body.emotion({"mouth": {"size": 80}})
        await body.look(yaw=45, pitch=20)
        await body.say("狗蛋", "大哥，CC 在等你审批")
        jpeg = await body.snapshot()
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Callable, Optional

import websockets

from . import protocol as p
from .auth import load_public_key, make_token

log = logging.getLogger("stackchan.body")


class BodyClient:
    def __init__(
        self,
        server_url: str,
        device_mac: str,
        server_pubkey_path: str,
        *,
        client_mac: str = "app000000001",
        device_id: str = "goudan-brain",
        ping_interval: float = 25.0,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.device_mac = p.normalize_mac(device_mac).decode()
        self.client_mac = client_mac
        self.device_id = device_id
        self._pubkey = load_public_key(server_pubkey_path)
        self._ping_interval = ping_interval
        self._ws: Optional[websockets.ClientConnection] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._jpeg_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=8)
        self._opus_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=64)
        self.on_frame: Optional[Callable[[p.Frame], None]] = None
        self.device_online: Optional[bool] = None

    async def connect(self) -> "BodyClient":
        token = make_token(self.client_mac, self._pubkey)
        url = f"{self.server_url}/stackChan/ws?deviceType=App&deviceId={self.device_id}"
        self._ws = await websockets.connect(
            url,
            additional_headers={"Authorization": token},
            max_size=2**23,
        )
        self._recv_task = asyncio.create_task(self._recv_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())
        log.info("connected to %s as App(%s)", self.server_url, self.client_mac)
        return self

    async def close(self) -> None:
        for t in (self._recv_task, self._ping_task):
            if t:
                t.cancel()
        if self._ws:
            await self._ws.close()

    async def __aenter__(self) -> "BodyClient":
        return await self.connect()

    async def __aexit__(self, *exc) -> None:
        await self.close()

    # ------------------------------------------------------------- transport

    async def _send(self, frame: bytes) -> None:
        assert self._ws, "not connected"
        await self._ws.send(frame)

    async def _recv_loop(self) -> None:
        assert self._ws
        try:
            async for msg in self._ws:
                if not isinstance(msg, bytes):
                    log.debug("text from server: %s", msg)
                    continue
                try:
                    frame = p.decode(msg)
                except ValueError as e:
                    log.warning("bad frame: %s", e)
                    continue
                self._dispatch(frame)
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass

    def _dispatch(self, frame: p.Frame) -> None:
        if frame.msg_type == p.MsgType.JPEG:
            if not self._jpeg_queue.full():
                self._jpeg_queue.put_nowait(frame.payload)
        elif frame.msg_type == p.MsgType.OPUS:
            if not self._opus_queue.full():
                self._opus_queue.put_nowait(frame.payload)
        elif frame.msg_type == p.MsgType.DEVICE_ONLINE:
            self.device_online = True
        elif frame.msg_type == p.MsgType.DEVICE_OFFLINE:
            self.device_online = False
        elif frame.msg_type == p.MsgType.PING:
            asyncio.get_running_loop().create_task(self._send(p.encode(p.MsgType.PONG)))
        if self.on_frame:
            self.on_frame(frame)

    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._ping_interval)
                await self._send(p.encode(p.MsgType.PING))
        except (asyncio.CancelledError, websockets.ConnectionClosed):
            pass

    # ------------------------------------------------------------------ body

    async def emotion(self, avatar: dict) -> None:
        """表情 (0x03)。avatar 例: {"mouth":{"size":90},"leftEye":{"y":-4}}"""
        await self._send(p.encode_avatar(self.device_mac, avatar))

    async def look(self, yaw: int | None = None, pitch: int | None = None, speed: int | None = None) -> None:
        """转头 (0x04)。yaw=水平角, pitch=竖直角(0-90), speed 可选。"""
        motion: dict = {}
        if yaw is not None:
            motion["yawServo"] = {"angle": yaw, **({"speed": speed} if speed else {})}
        if pitch is not None:
            motion["pitchServo"] = {"angle": pitch, **({"speed": speed} if speed else {})}
        await self._send(p.encode_motion(self.device_mac, motion))

    async def spin(self, degrees: int) -> None:
        """水平舵机相对旋转（360° 无限旋转模式）。"""
        await self._send(p.encode_motion(self.device_mac, {"yawServo": {"rotate": degrees}}))

    async def say(self, name: str, content: str) -> None:
        """向设备屏幕推文本消息 (0x07)。"""
        await self._send(p.encode_text(self.device_mac, name, content))

    async def snapshot(self, timeout: float = 10.0) -> bytes:
        """开摄像头 (0x05) → 收一帧 JPEG (0x02) → 关摄像头 (0x06)。"""
        while not self._jpeg_queue.empty():
            self._jpeg_queue.get_nowait()
        await self._send(p.encode_targeted(p.MsgType.ON_CAMERA, self.device_mac))
        try:
            return await asyncio.wait_for(self._jpeg_queue.get(), timeout)
        finally:
            await self._send(p.encode_targeted(p.MsgType.OFF_CAMERA, self.device_mac))

    async def stream_jpeg(self, duration: float) -> AsyncIterator[bytes]:
        """持续取 JPEG 帧 duration 秒（人脸追踪用）。"""
        await self._send(p.encode_targeted(p.MsgType.ON_CAMERA, self.device_mac))
        loop = asyncio.get_running_loop()
        end = loop.time() + duration
        try:
            while loop.time() < end:
                remaining = end - loop.time()
                try:
                    yield await asyncio.wait_for(self._jpeg_queue.get(), min(remaining, 2.0))
                except asyncio.TimeoutError:
                    continue
        finally:
            await self._send(p.encode_targeted(p.MsgType.OFF_CAMERA, self.device_mac))
