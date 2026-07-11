"""终极闭环: BodyClient(真) → Go relay(真, :12800, RSA 鉴权) → 设备侧收帧(真协议栈)
→ 固件 json_helper.cpp(真, sha256 同源) → 断言舵机/表情调用。
链路上没有任何一环是假的, 只有'物理执行'被 spy 桩替代。"""
import asyncio, subprocess, sys
sys.path.insert(0, "/home/ec2-user/worklog/stackchan/stackchan-embodied/body-client")
sys.path.insert(0, "/tmp/secret-logic-host")
import websockets
from stackchan_body import BodyClient, MsgType
from stackchan_body import protocol as p

MAC = "cafe00112233"
PUB = "/home/ec2-user/worklog/stackchan/stackchan-go-server/server_public.pem"

def firmware(mode, payload: bytes) -> list[str]:
    out = subprocess.run(["./json_sim", mode, payload.decode()], capture_output=True, text=True)
    return [l for l in out.stdout.strip().split("\n") if l]

async def main():
    # 设备端: 用固件 C++ 代码产的 token 连 relay(和上次鉴权验证同一 harness)
    token = subprocess.check_output(
        ["/tmp/secret-logic-host/token_harness", MAC]).decode().strip().split("token=")[1]
    dev = await websockets.connect(
        "ws://127.0.0.1:12800/stackChan/ws?deviceType=StackChan",
        additional_headers={"Authorization": token})
    inbox = asyncio.Queue()
    async def rx():
        async for m in dev:
            if isinstance(m, bytes):
                inbox.put_nowait(p.decode(m))
    t = asyncio.create_task(rx())

    async with BodyClient("ws://127.0.0.1:12800", MAC, PUB) as body:
        # 场景: 狗蛋让 StackChan 转头看大哥 + 开心表情
        await body.look(yaw=40, pitch=25, speed=60)
        await body.emotion({"mouth": {"size": 85}, "leftEye": {"y": -3}, "rightEye": {"y": -3}})

        f1 = await asyncio.wait_for(inbox.get(), 5)
        assert f1.msg_type == MsgType.CONTROL_MOTION
        calls1 = firmware("motion", f1.payload)   # relay 已剥 MAC, payload 即纯 JSON
        assert calls1 == ["yaw.moveWithSpeed(40,60)", "pitch.moveWithSpeed(25,60)"], calls1
        print("PASS 转头指令穿全链路:", calls1)

        f2 = await asyncio.wait_for(inbox.get(), 5)
        assert f2.msg_type == MsgType.CONTROL_AVATAR
        calls2 = firmware("avatar", f2.payload)
        assert calls2 == ["mouth.size(85)", "leftEye.pos(0,-3)", "rightEye.pos(0,-3)"] or \
               set(calls2) == {"mouth.size(85)"} | {"leftEye.pos(0,-3)", "rightEye.pos(0,-3)"}, calls2
        print("PASS 表情指令穿全链路:", calls2)

    t.cancel(); await dev.close()
    print("\nFULL-CHAIN PASS: BodyClient→relay(RSA)→device frames→firmware parser 语义一致")

asyncio.run(main())
