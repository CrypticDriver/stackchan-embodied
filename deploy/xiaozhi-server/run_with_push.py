"""xiaozhi-server 启动包装: 原样跑 app.py + 装载 goudan_push 主动播报插件。
systemd 的 ExecStart 指向本文件 (工作目录 = xiaozhi-server)。"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import goudan_push  # noqa: E402  (monkeypatch 在 import 时生效)
import app  # noqa: E402  上游入口


_orig_main = app.main


async def _main_with_push():
    goudan_push.install()
    await _orig_main()


app.main = _main_with_push

if __name__ == "__main__":
    try:
        asyncio.run(app.main())
    except KeyboardInterrupt:
        pass
