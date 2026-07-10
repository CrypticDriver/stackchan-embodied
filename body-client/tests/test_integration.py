"""回环集成测试：连真实自建 Go server (:12800)。

模拟 StackChan 设备端 (deviceType=StackChan) + BodyClient App 端，
验证: RSA 鉴权、表情/动作/文本帧路由、摄像头开→JPEG 回传→关。

需要 stackchan-goserver 服务在本机运行；不在则整组 skip。
"""

import asyncio
import json
import os
import socket

import pytest
import pytest_asyncio
import websockets

from stackchan_body import BodyClient, MsgType
from stackchan_body import protocol as p
from stackchan_body.auth import load_public_key, make_token

SERVER = os.environ.get("STACKCHAN_SERVER", "ws://127.0.0.1:12800")
KEY = os.environ.get(
    "STACKCHAN_SERVER_PUBKEY",
    "/home/ec2-user/worklog/stackchan/stackchan-go-server/server_public.pem",
)
DEVICE_MAC = "cafe00112233"

def _server_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 12800), timeout=2):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _server_up(), reason="Go server not running on :12800"),
]


class FakeDevice:
    """最小 StackChan 设备模拟：收帧记录，收 ON_CAMERA 回一帧 JPEG。"""

    def __init__(self, mac: str):
        self.mac = mac
        self.frames: list[p.Frame] = []
        self.ws = None
        self._task = None

    async def connect(self):
        token = make_token(self.mac, load_public_key(KEY))
        self.ws = await websockets.connect(
            f"{SERVER}/stackChan/ws?deviceType=StackChan",
            additional_headers={"Authorization": token},
        )
        self._task = asyncio.create_task(self._loop())
        return self

    async def _loop(self):
        try:
            async for msg in self.ws:
                if not isinstance(msg, bytes):
                    continue
                frame = p.decode(msg)
                self.frames.append(frame)
                if frame.msg_type == MsgType.ON_CAMERA:
                    await self.ws.send(p.encode(MsgType.JPEG, b"\xff\xd8fakejpeg\xff\xd9"))
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass

    async def wait_for(self, msg_type: MsgType, timeout: float = 5.0) -> p.Frame:
        async def _poll():
            while True:
                for f in self.frames:
                    if f.msg_type == msg_type:
                        return f
                await asyncio.sleep(0.05)

        return await asyncio.wait_for(_poll(), timeout)

    async def close(self):
        if self._task:
            self._task.cancel()
        if self.ws:
            await self.ws.close()


@pytest_asyncio.fixture
async def device():
    d = await FakeDevice(DEVICE_MAC).connect()
    yield d
    await d.close()


@pytest_asyncio.fixture
async def body():
    async with BodyClient(SERVER, DEVICE_MAC, KEY) as b:
        yield b


async def test_auth_rejected_without_token():
    with pytest.raises(websockets.InvalidStatus) as ei:
        await websockets.connect(f"{SERVER}/stackChan/ws?deviceType=App&deviceId=x")
    assert ei.value.response.status_code == 401


async def test_auth_rejected_with_stale_token():
    token = make_token("cafe00112233", load_public_key(KEY), now=1_000_000)
    with pytest.raises(websockets.InvalidStatus) as ei:
        await websockets.connect(
            f"{SERVER}/stackChan/ws?deviceType=App&deviceId=x",
            additional_headers={"Authorization": token},
        )
    assert ei.value.response.status_code == 401


async def test_avatar_routing(device, body):
    await body.emotion({"mouth": {"size": 90}})
    frame = await device.wait_for(MsgType.CONTROL_AVATAR)
    assert json.loads(frame.payload) == {"mouth": {"size": 90}}


async def test_motion_routing(device, body):
    await body.look(yaw=45, pitch=30, speed=50)
    frame = await device.wait_for(MsgType.CONTROL_MOTION)
    data = json.loads(frame.payload)
    assert data["yawServo"] == {"angle": 45, "speed": 50}
    assert data["pitchServo"] == {"angle": 30, "speed": 50}


async def test_text_routing(device, body):
    await body.say("狗蛋", "测试消息")
    frame = await device.wait_for(MsgType.TEXT_MESSAGE)
    assert json.loads(frame.payload) == {"name": "狗蛋", "content": "测试消息"}


async def test_snapshot_camera_cycle(device, body):
    jpeg = await body.snapshot(timeout=8)
    assert jpeg.startswith(b"\xff\xd8")
    await device.wait_for(MsgType.OFF_CAMERA)
