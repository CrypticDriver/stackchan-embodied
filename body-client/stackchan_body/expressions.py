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

EXPRESSIONS: dict[str, dict] = {
    # 思考: 双眼抬向右上方"找答案", 右眼略眯出挑眉感, 嘴小幅右移微斜
    # 用途: M2 长任务进行中 / 狗蛋处理请求时
    "thinking": {
        "leftEye": {"x": 60, "y": -65, "weight": 85, "rotation": 0, "size": 0},
        "rightEye": {"x": 60, "y": -65, "weight": 65, "rotation": 0, "size": 0},
        "mouth": {"x": 25, "y": 4, "weight": 12, "rotation": 60},
    },
    # 得意: 月牙笑眼(155°)压成半眯, 嘴歪向一侧上挑 —— "看我干得漂亮吧"
    # 用途: 任务顺利完成 / 被夸时
    "smug": {
        "leftEye": {"x": 0, "y": 0, "weight": 60, "rotation": 1550, "size": 0},
        "rightEye": {"x": 0, "y": 0, "weight": 60, "rotation": 1550, "size": 0},
        "mouth": {"x": 28, "y": 6, "weight": 14, "rotation": -110},
    },
    # 委屈: 八字垂眼(外高内低 30°)+眼睛内聚下看, 小瘪嘴下移
    # 用途: 任务失败 / 被大哥说了 / 长时间没人理
    "aggrieved": {
        "leftEye": {"x": 15, "y": 60, "weight": 50, "rotation": 300, "size": 0},
        "rightEye": {"x": -15, "y": 60, "weight": 50, "rotation": 300, "size": 0},
        "mouth": {"x": 0, "y": 34, "weight": 8, "rotation": 0},
    },
    # 兴奋: 大瞳孔(+45)月牙眼 + 大张嘴 —— 汇报好消息
    # 用途: 大哥回家 / 任务全绿 / M2 完成播报
    "excited": {
        "leftEye": {"x": 0, "y": 0, "weight": 88, "rotation": 1550, "size": 45},
        "rightEye": {"x": 0, "y": 0, "weight": 88, "rotation": 1550, "size": 45},
        "mouth": {"x": 0, "y": 4, "weight": 55, "rotation": 0},
    },
    # 专注: 眼睑压半+瞳孔缩小聚焦, 抿直嘴 —— 监工模式
    # 用途: M2 盯 Happy session 时的常驻脸
    "focused": {
        "leftEye": {"x": 0, "y": 0, "weight": 58, "rotation": 0, "size": -30},
        "rightEye": {"x": 0, "y": 0, "weight": 58, "rotation": 0, "size": -30},
        "mouth": {"x": 0, "y": 0, "weight": 6, "rotation": 0},
    },
    # 惊讶: 瞳孔放大(+70) + 嘴张大 —— 出事了/意外情况
    # 用途: 任务报错 / 检测到异常
    "surprised": {
        "leftEye": {"x": 0, "y": 0, "weight": 100, "rotation": 0, "size": 70},
        "rightEye": {"x": 0, "y": 0, "weight": 100, "rotation": 0, "size": 70},
        "mouth": {"x": 0, "y": 0, "weight": 65, "rotation": 0},
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
