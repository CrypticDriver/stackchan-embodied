"""连接鉴权 token 生成。

server 端校验逻辑 (web_socket.go GetMac):
    Authorization: base64( RSA-OAEP-SHA256_encrypt(server_pub, "mac|<nonce>|unix_ts") )
    parts[0]=MAC(12 hex), parts[2]=时间戳, 窗口 ±10 秒 → 客户端必须 NTP 校时。
"""

from __future__ import annotations

import base64
import secrets
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def load_public_key(pem_path: str):
    with open(pem_path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


def make_token(mac_12hex: str, server_public_key, now: int | None = None) -> str:
    ts = now if now is not None else int(time.time())
    plain = f"{mac_12hex}|{secrets.token_hex(4)}|{ts}".encode()
    cipher = server_public_key.encrypt(
        plain,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return base64.b64encode(cipher).decode()
