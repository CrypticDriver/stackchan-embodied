"""真机冒烟: 转头 + 表情 + 文本。刷机后验证用。

用法:
    STACKCHAN_DEVICE_MAC=aa:bb:cc:dd:ee:ff python wave_hello.py
"""

import asyncio
import os

from stackchan_body import BodyClient

SERVER = os.environ.get("STACKCHAN_SERVER", "ws://127.0.0.1:12800")
MAC = os.environ["STACKCHAN_DEVICE_MAC"]
KEY = os.environ.get(
    "STACKCHAN_SERVER_PUBKEY",
    "/home/ec2-user/worklog/stackchan/stackchan-go-server/server_public.pem",
)


async def main():
    async with BodyClient(SERVER, MAC, KEY) as body:
        print("connected; driving device", MAC)
        await body.say("狗蛋", "大哥好！我上身了")
        for yaw in (40, -40, 0):
            await body.look(yaw=yaw, pitch=30, speed=60)
            await asyncio.sleep(1.2)
        await body.emotion({"mouth": {"size": 90}})
        await asyncio.sleep(1)
        await body.emotion({"mouth": {"size": 30}})
        print("done — 设备应已转头、变表情、显示文本")


asyncio.run(main())
