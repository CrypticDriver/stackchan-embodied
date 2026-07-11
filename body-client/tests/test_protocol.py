import json

import pytest

from stackchan_body import protocol as p


def test_roundtrip():
    raw = p.encode(p.MsgType.TEXT_MESSAGE, b"hello")
    frame = p.decode(raw)
    assert frame.msg_type == p.MsgType.TEXT_MESSAGE
    assert frame.payload == b"hello"


def test_header_layout():
    raw = p.encode(p.MsgType.CONTROL_MOTION, b"\x01\x02\x03")
    assert raw[0] == 0x04
    assert raw[1:5] == (3).to_bytes(4, "big")
    assert raw[5:] == b"\x01\x02\x03"


def test_empty_payload():
    raw = p.encode(p.MsgType.PING)
    assert raw == bytes([0x10, 0, 0, 0, 0])
    assert p.decode(raw).payload == b""


def test_decode_length_mismatch():
    bad = bytes([0x07, 0, 0, 0, 9]) + b"abc"
    with pytest.raises(ValueError, match="length mismatch"):
        p.decode(bad)


def test_decode_too_short():
    with pytest.raises(ValueError, match="too short"):
        p.decode(b"\x07")


def test_normalize_mac():
    assert p.normalize_mac("AA:BB:CC:DD:EE:FF") == b"aabbccddeeff"
    assert p.normalize_mac("aabbccddeeff") == b"aabbccddeeff"
    with pytest.raises(ValueError):
        p.normalize_mac("nope")
    with pytest.raises(ValueError):
        p.normalize_mac("aa:bb:cc:dd:ee")


def test_targeted_frame_carries_mac_prefix():
    raw = p.encode_targeted(p.MsgType.ON_CAMERA, "AA:BB:CC:DD:EE:FF", b"")
    frame = p.decode(raw)
    assert frame.payload[:12] == b"aabbccddeeff"


def test_avatar_json():
    raw = p.encode_avatar("aabbccddeeff", {"mouth": {"size": 88}})
    frame = p.decode(raw)
    assert json.loads(frame.payload[12:]) == {"mouth": {"size": 88}}


def test_motion_json():
    raw = p.encode_motion("aabbccddeeff", {"yawServo": {"angle": 45, "speed": 60}})
    frame = p.decode(raw)
    body = json.loads(frame.payload[12:])
    assert body["yawServo"]["angle"] == 45


def test_text_json_unicode():
    raw = p.encode_text("aabbccddeeff", "狗蛋", "大哥回来啦")
    frame = p.decode(raw)
    body = json.loads(frame.payload[12:])
    assert body == {"name": "狗蛋", "content": "大哥回来啦"}


def test_avatar_xy_autofill_firmware_quirk():
    # 固件 update_feature 要求 x/y 同时存在才 setPosition(实测发现) — 编码器需自动补全
    raw = p.encode_avatar("aabbccddeeff", {"leftEye": {"y": -3}})
    frame = p.decode(raw)
    assert json.loads(frame.payload[12:]) == {"leftEye": {"y": -3, "x": 0}}


def test_avatar_no_autofill_when_position_absent():
    raw = p.encode_avatar("aabbccddeeff", {"mouth": {"size": 50}})
    frame = p.decode(raw)
    assert json.loads(frame.payload[12:]) == {"mouth": {"size": 50}}
