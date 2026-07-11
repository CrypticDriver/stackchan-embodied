"""语义闭环: body-client 编码 → (模拟 relay 剥 MAC 路由头) → 固件真实 json_helper 解析
→ 断言最终舵机/五官调用与 body-client API 意图一致。"""
import subprocess
import sys

sys.path.insert(0, "/home/ec2-user/worklog/stackchan/stackchan-embodied/body-client")
from stackchan_body import protocol as p

MAC = "cafe00112233"
FAILED = []


def firmware_parse(mode: str, frame: bytes) -> list[str]:
    """模拟 device 收帧: decode → payload 去掉 12B MAC(relay 已剥) → 固件解析。"""
    f = p.decode(frame)
    json_payload = f.payload[12:].decode()  # relay 在转发前剥 MAC, 设备只见 JSON
    out = subprocess.run(["./json_sim", mode, json_payload], capture_output=True, text=True)
    return [l for l in out.stdout.strip().split("\n") if l]


def check(name, got, expect):
    ok = got == expect
    print(("PASS" if ok else "FAIL"), name, "->", got)
    if not ok:
        FAILED.append((name, got, expect))


# ---- 表情: BodyClient.emotion() 语义 ----
check("emotion mouth size",
      firmware_parse("avatar", p.encode_avatar(MAC, {"mouth": {"size": 90}})),
      ["mouth.size(90)"])

check("emotion eyes+mouth compound",
      firmware_parse("avatar", p.encode_avatar(
          MAC, {"leftEye": {"x": -2, "y": 3, "weight": 60}, "rightEye": {"rotation": 15}, "mouth": {"size": 20}})),
      ["leftEye.pos(-2,3)", "leftEye.weight(60)", "rightEye.rot(15)", "mouth.size(20)"])

# ---- 动作: BodyClient.look()/spin() 语义 ----
check("look yaw+pitch with speed",
      firmware_parse("motion", p.encode_motion(MAC, {"yawServo": {"angle": 45, "speed": 50},
                                                     "pitchServo": {"angle": 30, "speed": 50}})),
      ["yaw.moveWithSpeed(45,50)", "pitch.moveWithSpeed(30,50)"])

check("look default spring",
      firmware_parse("motion", p.encode_motion(MAC, {"yawServo": {"angle": -60}})),
      ["yaw.move(-60)"])

check("look custom spring params",
      firmware_parse("motion", p.encode_motion(
          MAC, {"pitchServo": {"angle": 80, "spring": {"stiffness": 200.5, "damping": 30.5}}})),
      ["pitch.spring(80,200,30)"])

check("spin (360 rotate mode)",
      firmware_parse("motion", p.encode_motion(MAC, {"yawServo": {"rotate": 500}})),
      ["yaw.rotate(500)"])

check("rotate takes precedence over angle (firmware rule)",
      firmware_parse("motion", p.encode_motion(MAC, {"yawServo": {"rotate": 100, "angle": 45}})),
      ["yaw.rotate(100)"])

# ---- 防御性: 恶意/坏输入不产生动作 ----
check("garbage json -> no calls",
      firmware_parse("motion", p.encode_targeted(p.MsgType.CONTROL_MOTION, MAC, b"{not json")),
      [])

check("wrong types ignored (string angle)",
      firmware_parse("motion", p.encode_targeted(
          p.MsgType.CONTROL_MOTION, MAC, b'{"yawServo": {"angle": "45"}}')),
      [])

check("unicode text payload untouched by motion parser",
      firmware_parse("motion", p.encode_targeted(p.MsgType.CONTROL_MOTION, MAC, '{"其他": 1}'.encode())),
      [])

# ---- RGB 灯 (M5 机身 12 颗) ----
check("neon light color+duration",
      firmware_parse("neon", p.encode_targeted(
          p.MsgType.CONTROL_AVATAR, MAC,
          b'{"leftRgbColor": "#FF0000", "leftRgbDuration": 1.5, "rightRgbColor": "#00FF00"}')),
      ["leftRgb.duration(1500ms)", "leftRgb.color(#FF0000)", "rightRgb.color(#00FF00)"])

print()
if FAILED:
    print(f"{len(FAILED)} FAILED")
    sys.exit(1)
print("ALL SEMANTIC TESTS PASS — body-client 指令与固件解析语义一致")
