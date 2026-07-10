"""用固件 C++ 代码产的 token 连真实 Go server，deviceType=StackChan——
即刷机后设备侧鉴权的精确模拟。再用 body-client 从 App 侧发帧验证双向路由。"""
import asyncio, subprocess, sys
sys.path.insert(0, "/home/ec2-user/worklog/stackchan/stackchan-embodied/body-client")
import websockets
from stackchan_body import BodyClient, MsgType
from stackchan_body import protocol as p

MAC = "cafe00112233"

async def main():
    token = subprocess.check_output(["./token_harness", MAC]).decode().strip().split("token=")[1]
    print("firmware-C++ token:", token[:40], "...")

    # 1) device-side connect with firmware token
    ws = await websockets.connect(
        "ws://127.0.0.1:12800/stackChan/ws?deviceType=StackChan",
        additional_headers={"Authorization": token})
    print("PASS: Go server accepted firmware-generated token (101)")

    # replicate firmware hello (hal_ws_avatar.cpp OnConnected)
    await ws.send('{"type":"hello", "msg":"Hello from StackChan!"}')

    got = asyncio.Queue()
    async def reader():
        async for m in ws:
            if isinstance(m, bytes):
                got.put_nowait(p.decode(m))
    rt = asyncio.create_task(reader())

    # 2) App side drives it through the relay
    async with BodyClient("ws://127.0.0.1:12800", MAC,
        "/home/ec2-user/worklog/stackchan/stackchan-go-server/server_public.pem") as body:
        await body.look(yaw=30, pitch=45)
        frame = await asyncio.wait_for(got.get(), 5)
        assert frame.msg_type == MsgType.CONTROL_MOTION, frame
        print("PASS: motion frame routed to firmware-authenticated device:", frame.payload.decode())

    # 3) stale token must be rejected (firmware clock skew guard)
    stale = subprocess.check_output(["./token_harness", MAC]).decode().strip().split("token=")[1]
    await asyncio.sleep(11)
    try:
        await websockets.connect("ws://127.0.0.1:12800/stackChan/ws?deviceType=StackChan",
            additional_headers={"Authorization": stale})
        print("FAIL: stale token accepted!"); return 1
    except websockets.InvalidStatus as e:
        print(f"PASS: 11s-old token rejected ({e.response.status_code}) — ±10s window enforced")
    rt.cancel(); await ws.close()
    return 0

sys.exit(asyncio.run(main()))
