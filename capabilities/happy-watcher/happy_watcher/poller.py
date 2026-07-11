"""Happy server 轮询器: API → 解密 → SessionSnapshot 列表。

数据源: 自托管 Happy server /v1/sessions (Bearer token 来自 ~/.happy/access.key),
metadata/agentState 用本机 sessions.json 里的 per-session dataKey (AES-256-GCM) 解密。
"""

from __future__ import annotations

import base64
import json
import pathlib
import time
import urllib.request

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .state_machine import SessionSnapshot, SessionState

HAPPY_HOME = pathlib.Path.home() / ".happy"


class HappyPoller:
    def __init__(self, server_url: str):
        self.server = server_url.rstrip("/")
        self.token = json.load(open(HAPPY_HOME / "access.key"))["token"]
        self._keys: dict[str, bytes] = {}
        self._keys_mtime = 0.0

    def _refresh_keys(self) -> None:
        p = HAPPY_HOME / "sessions.json"
        mtime = p.stat().st_mtime
        if mtime == self._keys_mtime:
            return
        data = json.load(open(p))["sessions"]
        self._keys = {
            sid: base64.b64decode(s["encryptionKey"])
            for sid, s in data.items()
            if s.get("encryptionVariant") == "dataKey"
        }
        self._keys_mtime = mtime

    def _decrypt(self, b64: str | None, key: bytes):
        if not b64:
            return None
        try:
            bundle = base64.b64decode(b64)
            if bundle[0] != 0:
                return None
            return json.loads(AESGCM(key).decrypt(bundle[1:13], bundle[13:], None))
        except Exception:
            return None

    def fetch(self) -> list[SessionSnapshot]:
        self._refresh_keys()
        req = urllib.request.Request(
            f"{self.server}/v1/sessions", headers={"Authorization": f"Bearer {self.token}"}
        )
        sessions = json.load(urllib.request.urlopen(req, timeout=10))["sessions"]

        now_ms = time.time() * 1000
        out: list[SessionSnapshot] = []
        for s in sessions:
            key = self._keys.get(s["id"])
            if not key:
                continue  # 没本机密钥的会话(别的机器)跳过
            meta = self._decrypt(s.get("metadata"), key) or {}
            state = self._decrypt(s.get("agentState"), key) or {}

            title = pathlib.Path(meta.get("path", s["id"])).name or s["id"][:8]
            requests = state.get("requests") or {}
            lifecycle = meta.get("lifecycleState", "")
            active = bool(s.get("active"))
            idle_min = (now_ms - s.get("updatedAt", now_ms)) / 60000

            if requests:
                st = SessionState.WAITING_INPUT     # 有 pending permission/问题
            elif not active or lifecycle in ("exited", "archived"):
                st = SessionState.IDLE
            elif idle_min < 3:
                st = SessionState.RUNNING           # 3 分钟内有更新 = 在干活
            else:
                st = SessionState.COMPLETED         # 活跃连接但久无更新 = 干完待命

            detail = ""
            if requests:
                first = next(iter(requests.values()))
                if isinstance(first, dict):
                    detail = str(first.get("tool") or first.get("type") or "")[:20]
            out.append(SessionSnapshot(s["id"], title, st, detail))
        return out
