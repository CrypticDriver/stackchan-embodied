"""StackChan WS 二进制帧协议编解码。

帧格式（与 m5stack/StackChan server/internal/web_socket/web_socket.go 一致）:
    [1B msgType] [4B 大端 payload 长度] [payload]

App→server 的多数控制帧 payload 前 12 字节是目标设备 MAC（无冒号小写 hex），
server 据此路由到对应 StackChan 设备。
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from enum import IntEnum


class MsgType(IntEnum):
    OPUS = 0x01
    JPEG = 0x02
    CONTROL_AVATAR = 0x03
    CONTROL_MOTION = 0x04
    ON_CAMERA = 0x05
    OFF_CAMERA = 0x06
    TEXT_MESSAGE = 0x07
    REQUEST_CALL = 0x09
    REFUSE_CALL = 0x0A
    AGREE_CALL = 0x0B
    HANGUP_CALL = 0x0C
    UPDATE_DEVICE_NAME = 0x0D
    GET_DEVICE_NAME = 0x0E
    IN_CALL = 0x0F
    PING = 0x10
    PONG = 0x11
    ON_PHONE_SCREEN = 0x12
    OFF_PHONE_SCREEN = 0x13
    DANCE = 0x14
    GET_AVATAR_POSTURE = 0x15
    DEVICE_OFFLINE = 0x16
    DEVICE_ONLINE = 0x17
    ON_AUDIO = 0x18
    OFF_AUDIO = 0x19
    AIMED_TAKE_PHOTO = 0x1A


HEADER = struct.Struct(">BI")  # msgType + big-endian length


@dataclass(frozen=True)
class Frame:
    msg_type: MsgType
    payload: bytes

    def encode(self) -> bytes:
        return HEADER.pack(self.msg_type, len(self.payload)) + self.payload


def encode(msg_type: MsgType | int, payload: bytes = b"") -> bytes:
    return Frame(MsgType(msg_type), payload).encode()


def decode(data: bytes) -> Frame:
    if len(data) < HEADER.size:
        raise ValueError(f"frame too short: {len(data)} bytes")
    msg_type, length = HEADER.unpack_from(data)
    payload = data[HEADER.size:]
    if len(payload) != length:
        raise ValueError(f"length mismatch: header={length} actual={len(payload)}")
    return Frame(MsgType(msg_type), payload)


def normalize_mac(mac: str) -> bytes:
    """'AA:BB:CC:DD:EE:FF' / 'aabbccddeeff' → 12 字节小写 hex（server 路由键）。"""
    cleaned = mac.replace(":", "").replace("-", "").lower()
    if len(cleaned) != 12 or any(c not in "0123456789abcdef" for c in cleaned):
        raise ValueError(f"invalid MAC: {mac!r}")
    return cleaned.encode()


def encode_targeted(msg_type: MsgType | int, mac: str, data: bytes = b"") -> bytes:
    """App→server: payload = 12B MAC + data。"""
    return encode(msg_type, normalize_mac(mac) + data)


def encode_avatar(mac: str, avatar: dict) -> bytes:
    """表情控制 (0x03)。JSON 结构见固件 json_helper.cpp:
    {"leftEye"/"rightEye"/"mouth": {"x","y","rotation","weight","size"}}"""
    return encode_targeted(MsgType.CONTROL_AVATAR, mac, json.dumps(avatar).encode())


def encode_motion(mac: str, motion: dict) -> bytes:
    """动作控制 (0x04)。JSON 结构:
    {"yawServo"/"pitchServo": {"angle","speed"} | {"rotate"} | {"angle","spring":{...}}}"""
    return encode_targeted(MsgType.CONTROL_MOTION, mac, json.dumps(motion).encode())


def encode_text(mac: str, name: str, content: str) -> bytes:
    """文本消息 (0x07)，设备端渲染 {"name","content"}。"""
    return encode_targeted(
        MsgType.TEXT_MESSAGE, mac, json.dumps({"name": name, "content": content}, ensure_ascii=False).encode()
    )
