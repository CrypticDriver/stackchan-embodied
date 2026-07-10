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
    """同一 session 同一状态只提醒一次；批量变化合并。"""

    quiet: bool = False   # 安静时段: 只表情不出声
    _last: dict[str, SessionState] = field(default_factory=dict)

    def observe(self, snapshots: Iterable[SessionSnapshot]) -> list[RobotEvent]:
        events: list[RobotEvent] = []
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
