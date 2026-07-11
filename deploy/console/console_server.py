"""控制台静态页 + API 反代聚合 (单进程, 127.0.0.1:9100)。

/               → index.html (无鉴权, 页面本身不含敏感数据)
/console/api/*  → 状态聚合 (X-Console-Token 鉴权)
"""

import os
import pathlib

from aiohttp import web

import status_api

HERE = pathlib.Path(__file__).parent


async def index(_: web.Request) -> web.Response:
    return web.FileResponse(HERE / "index.html", headers={"Cache-Control": "no-cache"})


app = status_api.app
app.router.add_get("/", index)
app.router.add_get("/console", index)
app.router.add_get("/console/", index)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=9100, print=None)
