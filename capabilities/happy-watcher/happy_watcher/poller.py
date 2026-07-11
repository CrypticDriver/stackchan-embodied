"""Happy server 轮询器: API → 解密 → SessionSnapshot 列表。

数据源: 自托管 Happy server /v1/sessions (Bearer token 来自 ~/.happy/access.key),
metadata/agentState 用本机 sessions.json 里的 per-session dataKey (AES-256-GCM) 解密。

状态判定 (2026-07 重写, 用真实字段而非"更新时间"猜):
  - agentState.requests 非空      → WAITING_INPUT (有待审批工具调用, 最高优先级)
  - metadata.lifecycleState        → running/exited/archived 的权威来源
  - agentState.controlledByUser    → 你正在亲自操作的前台会话
过滤 (只监听"真正需要监工的后台任务"):
  - archived / 已退出 的会话        → 跳过 (你已经归档 = 不用管了)
  - controlledByUser 的前台会话     → 跳过 (你正在亲自操作, 监工无意义)
  - 僵尸: active=false 且 N 小时无更新 → 跳过 (废弃残留)
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
ZOMBIE_HOURS = 6          # active=false 且这么久没更新 = 废弃, 不监控
RUNNING_FRESH_MIN = 3     # lifecycleState=running 且这么新 = 真在干活


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

    def fetch(self, include_filtered: bool = False) -> list[SessionSnapshot]:
        """返回需要监工的后台会话。include_filtered=True 时也返回被过滤的(带 skip 标记), 供控制台展示。"""
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
                continue  # 别的机器的会话
            meta = self._decrypt(s.get("metadata"), key) or {}
            state = self._decrypt(s.get("agentState"), key) or {}

            title = pathlib.Path(meta.get("path", s["id"])).name or s["id"][:8]
            requests = state.get("requests") or {}
            lifecycle = meta.get("lifecycleState", "")
            controlled = bool(state.get("controlledByUser"))
            active = bool(s.get("active"))
            idle_h = (now_ms - s.get("updatedAt", now_ms)) / 3600000

            # ---- 过滤: 不该监工的会话 ----
            skip = None
            if lifecycle in ("archived", "exited", "killed"):
                skip = lifecycle                      # 已归档/退出 = 你不管了
            elif not active and idle_h >= ZOMBIE_HOURS:
                skip = "zombie"                       # 废弃残留
            elif controlled:
                skip = "foreground"                   # 你正在亲自操作

            # ---- 状态判定 (真实字段) ----
            if requests:
                st = SessionState.WAITING_INPUT
            elif skip:
                st = SessionState.IDLE
            elif lifecycle == "running" and idle_h * 60 < RUNNING_FRESH_MIN:
                st = SessionState.RUNNING
            elif lifecycle == "running":
                st = SessionState.COMPLETED           # 在线但久无更新 = 干完待命
            else:
                st = SessionState.IDLE

            # 待审批的工具明细
            detail = ""
            if requests:
                first = next(iter(requests.values()))
                if isinstance(first, dict):
                    tool = first.get("tool", "")
                    cmd = (first.get("arguments") or {}).get("command", "")
                    detail = (f"{tool}: {cmd}" if cmd else tool)[:60]

            snap = SessionSnapshot(s["id"], title, st, detail)
            if skip and not requests:
                # 被过滤且无待审批 → 只在 include_filtered 时给控制台看, 不进监工事件流
                if include_filtered:
                    snap = SessionSnapshot(s["id"], f"{title} ({skip})", SessionState.IDLE, detail)
                    out.append(snap)
                continue
            out.append(snap)
        return out

    def pending_requests(self) -> list[dict]:
        """所有待审批请求的结构化列表 (给语音审批用): [{session_id, title, request_id, tool, command}]。"""
        self._refresh_keys()
        req = urllib.request.Request(
            f"{self.server}/v1/sessions", headers={"Authorization": f"Bearer {self.token}"}
        )
        sessions = json.load(urllib.request.urlopen(req, timeout=10))["sessions"]
        out = []
        for s in sessions:
            key = self._keys.get(s["id"])
            if not key:
                continue
            state = self._decrypt(s.get("agentState"), key) or {}
            meta = self._decrypt(s.get("metadata"), key) or {}
            for rid, r in (state.get("requests") or {}).items():
                if not isinstance(r, dict):
                    continue
                out.append({
                    "session_id": s["id"],
                    "title": pathlib.Path(meta.get("path", s["id"])).name,
                    "request_id": rid,
                    "tool": r.get("tool", ""),
                    "command": (r.get("arguments") or {}).get("command", ""),
                })
        return out
