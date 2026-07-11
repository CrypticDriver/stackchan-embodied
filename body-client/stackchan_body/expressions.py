"""狗蛋专属表情预设库。

参数体系 = 固件 skins/default 五官参数（json_helper.cpp 解析）:
  眼: x/y ±100(物理±16px), weight 0-100(眼睑闭→开), rotation 0.1°, size ±100(瞳孔8→32px)
  嘴: x/y ±100, weight 0-100(90×6扁条→60×50圆角), rotation 0.1°

设计于 2026-07-11（渲染数学 1:1 模拟器逐帧调参 + 固件解析器语义验证）。
预览图: docs/goudan-expressions.png · 交互调参: docs/face-simulator.html

用法:
    from stackchan_body import BodyClient
    from stackchan_body.expressions import EXPRESSIONS, NEUTRAL
    await body.emotion(EXPRESSIONS["thinking"])
    await body.emotion(NEUTRAL)   # 回到待机脸
"""

from __future__ import annotations

# 回到待机脸（所有参数复位）
NEUTRAL: dict = {
    "leftEye": {"x": 0, "y": 0, "weight": 100, "rotation": 0, "size": 0},
    "rightEye": {"x": 0, "y": 0, "weight": 100, "rotation": 0, "size": 0},
    "mouth": {"x": 0, "y": 0, "weight": 0, "rotation": 0},
}

# v2 设计语言 (2026-07-11 风格探索后定稿): 不对称骨架 + 瞳孔表现力。
# 左右眼参数刻意不同 —— 对称的脸是图标, 不对称的脸才是生物。
EXPRESSIONS: dict[str, dict] = {
    # 思考: 左眼睁大看右上"找答案", 右眼眯起微斜出"琢磨"感, 嘴右移上斜
    # 用途: M2 长任务进行中 / 狗蛋处理请求时
    "thinking": {
        "leftEye": {"x": 70, "y": -75, "weight": 95, "rotation": 0, "size": 20},
        "rightEye": {"x": 45, "y": -50, "weight": 50, "rotation": 350, "size": 20},
        "mouth": {"x": 32, "y": 8, "weight": 14, "rotation": -100},
    },
    # 得意: 两边月牙眼弧度/开合不对称(痞气), 嘴大角度上挑歪向一侧
    # 用途: 任务顺利完成 / 被夸时
    "smug": {
        "leftEye": {"x": 0, "y": 0, "weight": 70, "rotation": -1600, "size": 15},
        "rightEye": {"x": 0, "y": 0, "weight": 38, "rotation": 1450, "size": 15},
        "mouth": {"x": 30, "y": 8, "weight": 16, "rotation": 190},
    },
    # 委屈: 八字垂眼两边角度略差+大瞳孔(泪眼汪汪), 倒扣撇嘴微斜
    # (mouth.rotation 135°-225° 区间 = goudan skin 撇嘴模式, 1710 = 撇嘴+9°斜)
    # 用途: 任务失败 / 被大哥说了 / 长时间没人理
    "aggrieved": {
        "leftEye": {"x": 18, "y": 68, "weight": 52, "rotation": -320, "size": 40},
        "rightEye": {"x": -18, "y": 68, "weight": 58, "rotation": 250, "size": 40},
        "mouth": {"x": 0, "y": 36, "weight": 7, "rotation": 1710},
    },
    # 兴奋: 双眼圆睁大瞳孔(左右略差)+大张嘴微歪 —— 汇报好消息
    # 用途: 大哥回家 / 任务全绿 / M2 完成播报
    "excited": {
        "leftEye": {"x": 0, "y": 0, "weight": 100, "rotation": -1500, "size": 60},
        "rightEye": {"x": 0, "y": 0, "weight": 88, "rotation": 1650, "size": 50},
        "mouth": {"x": 0, "y": 2, "weight": 62, "rotation": 40},
    },
    # 专注: 两眼眯起程度不同+反向微斜(锁定目标), 瞳孔缩小, 抿直嘴
    # 用途: M2 盯 Happy session 时的常驻脸
    "focused": {
        "leftEye": {"x": 0, "y": 0, "weight": 52, "rotation": -100, "size": -30},
        "rightEye": {"x": 0, "y": 0, "weight": 64, "rotation": -100, "size": -20},
        "mouth": {"x": -8, "y": 0, "weight": 6, "rotation": 0},
    },
    # 惊讶: 一眼瞳孔放到最大一眼半眯("?!"的错愕感), 嘴张大微歪
    # 用途: 任务报错 / 检测到异常
    "surprised": {
        "leftEye": {"x": 0, "y": 0, "weight": 100, "rotation": 0, "size": 85},
        "rightEye": {"x": 0, "y": 0, "weight": 75, "rotation": 250, "size": 55},
        "mouth": {"x": 10, "y": 0, "weight": 58, "rotation": -50},
    },
}

# M2 happy-watcher 事件 → 表情映射（RobotEvent.kind 直接查这里）
EVENT_EXPRESSION: dict[str, dict] = {
    "attention": EXPRESSIONS["surprised"],   # 等审批: 先惊讶抓注意
    "happy": EXPRESSIONS["excited"],         # 完成
    "pouty": EXPRESSIONS["aggrieved"],       # 失败
    "thinking": EXPRESSIONS["thinking"],     # 进行中
    "idle": NEUTRAL,
}
