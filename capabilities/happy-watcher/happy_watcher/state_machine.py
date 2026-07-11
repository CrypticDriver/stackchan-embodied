"""M2 状态机：把 Happy session 状态变化翻译成机器人动作事件（去重、合并）。

数据源无关：喂 SessionSnapshot 列表进来即可（真实 Happy API 或 fake 模式）。
输出 RobotEvent，由 sink（真机 BodyClient / 打印）消费。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class SessionState(str, Enum):
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"   # 卡在 permission/提问
    COMPLETED = "completed"
    FAILED = "failed"
    IDLE = "idle"


@dataclass(frozen=True)
class SessionSnapshot:
    session_id: str
    title: str
    state: SessionState
    detail: str = ""   # 完成摘要/错误要点，供播报


@dataclass(frozen=True)
class RobotEvent:
    kind: str            # attention | happy | pouty | thinking | idle
    speak: str | None    # 播报文本（None=只做表情不出声）
    session_id: str


# 状态 → (表情事件, 播报模板)。播报≤20字、口语化。
_RULES: dict[SessionState, tuple[str, str | None]] = {
    SessionState.WAITING_INPUT: ("attention", "老大，{title}在等你审批"),
    SessionState.COMPLETED: ("happy", "{title}干完了"),
    SessionState.FAILED: ("pouty", "{title}出岔子了"),
    SessionState.RUNNING: ("thinking", None),
    SessionState.IDLE: ("idle", None),
}


@dataclass
class Watcher:
    """同一 session 同一状态只提醒一次；批量变化合并。

    状态持久化: 传 state_path 则把 _last 落盘, 扛住进程重启不重放
    (否则每次重启所有 session 都"首次观察"刷屏)。
    """

    quiet: bool = False   # 安静时段: 只表情不出声
    state_path: str | None = None
    _last: dict[str, SessionState] = field(default_factory=dict)
    _primed: bool = False

    def __post_init__(self):
        if self.state_path:
            try:
                import json
                raw = json.load(open(self.state_path))
                self._last = {k: SessionState(v) for k, v in raw.items()}
                self._primed = True   # 有历史 = 非首次启动, 不静默
            except Exception:
                self._last = {}

    def _persist(self):
        if not self.state_path:
            return
        try:
            import json
            json.dump({k: v.value for k, v in self._last.items()}, open(self.state_path, "w"))
        except Exception:
            pass

    def observe(self, snapshots: Iterable[SessionSnapshot]) -> list[RobotEvent]:
        events: list[RobotEvent] = []
        first_run = not self._primed and not self._last
        for snap in snapshots:
            if self._last.get(snap.session_id) == snap.state:
                continue
            self._last[snap.session_id] = snap.state
            kind, template = _RULES[snap.state]
            speak = None
            if template and not self.quiet:
                speak = template.format(title=_short(snap.title))
                if snap.detail:
                    speak += "，" + _short(snap.detail, 14)
            events.append(RobotEvent(kind, speak, snap.session_id))
        self._primed = True
        self._persist()
        # 冷启动(无持久化历史)时静默 warm-up: 记录状态但不播报存量, 只播后续变化
        if first_run:
            return [e for e in events if e.speak is None]  # 只保留表情类, 吞掉存量播报
        return _merge(events)


def _short(text: str, limit: int = 10) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _merge(events: list[RobotEvent]) -> list[RobotEvent]:
    """同类事件≥3个合并成一句话，避免连环播报轰炸。"""
    speaking = [e for e in events if e.speak]
    if len(speaking) < 3:
        return events
    by_kind: dict[str, list[RobotEvent]] = {}
    for e in speaking:
        by_kind.setdefault(e.kind, []).append(e)
    merged: list[RobotEvent] = [e for e in events if not e.speak]
    for kind, group in by_kind.items():
        if len(group) >= 3:
            summary = {"attention": f"有{len(group)}个活儿等你审批",
                       "happy": f"{len(group)}个任务都干完了",
                       "pouty": f"{len(group)}个任务翻车了"}.get(kind, f"{len(group)}件事")
            merged.append(RobotEvent(kind, summary, group[0].session_id))
        else:
            merged.extend(group)
    return merged
