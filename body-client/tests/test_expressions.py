"""表情预设库测试: 参数域合法性 + 编码后可被解析 + M2 事件映射完整。"""

import json

import pytest

from stackchan_body import protocol as p
from stackchan_body.expressions import EVENT_EXPRESSION, EXPRESSIONS, NEUTRAL

ALL = {**EXPRESSIONS, "NEUTRAL": NEUTRAL}


@pytest.mark.parametrize("name", list(ALL))
def test_parameter_ranges(name):
    """固件参数域: 位置±100, weight 0-100, size ±100 (rotation 0.1° 任意)。"""
    for feature, params in ALL[name].items():
        assert feature in ("leftEye", "rightEye", "mouth")
        assert -100 <= params.get("x", 0) <= 100
        assert -100 <= params.get("y", 0) <= 100
        assert 0 <= params.get("weight", 50) <= 100
        assert -100 <= params.get("size", 0) <= 100
        for v in params.values():
            assert isinstance(v, int), f"{name}.{feature}: 固件只认 int (is<int>), got {v!r}"


@pytest.mark.parametrize("name", list(ALL))
def test_xy_always_paired(name):
    """固件坑: x/y 必须成对否则 setPosition 被静默忽略。预设必须自带成对 x/y。"""
    for params in ALL[name].values():
        assert ("x" in params) == ("y" in params)


@pytest.mark.parametrize("name", list(ALL))
def test_encodes_and_decodes(name):
    raw = p.encode_avatar("aabbccddeeff", ALL[name])
    frame = p.decode(raw)
    assert frame.msg_type == p.MsgType.CONTROL_AVATAR
    assert json.loads(frame.payload[12:]) == ALL[name]


def test_event_mapping_covers_all_watcher_kinds():
    """happy-watcher 产出的每种 RobotEvent.kind 都要有表情。"""
    assert set(EVENT_EXPRESSION) == {"attention", "happy", "pouty", "thinking", "idle"}


def test_neutral_resets_everything():
    for feature in ("leftEye", "rightEye", "mouth"):
        assert feature in NEUTRAL
        assert NEUTRAL[feature].get("x") == 0 and NEUTRAL[feature].get("y") == 0
    assert NEUTRAL["leftEye"]["weight"] == 100
    assert NEUTRAL["mouth"]["weight"] == 0
