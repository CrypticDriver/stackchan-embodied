#!/usr/bin/env python3
"""CI 校验: face-simulator.html 的狗蛋预设必须与 expressions.py 逐字一致。
用法: python tools/check_simulator_sync.py  (repo 根目录)"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "body-client"))
from stackchan_body.expressions import EXPRESSIONS  # noqa: E402

html = (Path(__file__).parent.parent / "docs/face-simulator.html").read_text()
block = re.search(r"const P = \{(.+?)\n\};", html, re.S).group(1)

MAP = {"leftEye": "l", "rightEye": "r", "mouth": "m"}
KEYS = {"x": "x", "y": "y", "weight": "w", "rotation": "r", "size": "s"}


def parse_preset(name: str) -> dict:
    m = re.search(rf"{name}:\s*\{{(.+?)\}},", block)
    if not m:
        sys.exit(f"preset {name} missing from HTML")
    kv = {}
    for pair in m.group(1).split(","):
        if ":" in pair:
            k, v = pair.split(":")
            kv[k.strip()] = int(v)
    return kv


ok = True
for name, expr in EXPRESSIONS.items():
    html_p = parse_preset("g_" + name)
    for feat, params in expr.items():
        for k, v in params.items():
            hk = MAP[feat] + KEYS[k]
            default = {"w": 100 if feat != "mouth" else 0}.get(KEYS[k], 0)
            if html_p.get(hk, default) != v:
                ok = False
                print(f"MISMATCH {name}.{feat}.{k}: py={v} html[{hk}]={html_p.get(hk, default)}")

print("HTML <-> expressions.py:", "in sync" if ok else "OUT OF SYNC")
sys.exit(0 if ok else 1)
