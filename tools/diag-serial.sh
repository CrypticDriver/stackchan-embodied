#!/usr/bin/env bash
# diag-serial.sh — 抓狗蛋串口日志, 高亮状态机关键行, 用来坐实
# 「气泡挂整夜 + 再唤醒无法聊天只能重启」的根因。
#
# 用法 (Mac):
#   1) 插 USB 数据线, ls /dev/cu.usbmodem*  找到串口
#   2) bash diag-serial.sh /dev/cu.usbmodemXXXX
#   3) 照着屏幕提示复现: 正常聊一次 → 说"拜拜/晚安"结束 → 等 3~5 分钟(别说话)
#      → 再喊唤醒词试着聊天(此时通常卡死) → Ctrl-C → 把 .log 发回来
#
# 需要 pyserial (pip3 install pyserial)。脚本只读不写, 绝对安全。

PORT="${1:-}"
if [ -z "$PORT" ]; then
  echo "用法: bash diag-serial.sh <串口>   (先 ls /dev/cu.usbmodem*)"
  exit 1
fi

cat <<'GUIDE'
========================================================================
狗蛋对话卡死 · 串口诊断
========================================================================
设备状态数字对照 (串口会打印 "Wake word detected: xxx (state: N)"):
   3 = Idle(待机)   4 = Connecting(连接中)   5 = Listening(听)   6 = Speaking(说)

复现步骤 (照做, 全程别拔线):
  ① 正常唤醒聊一句, 确认能对话
  ② 说"拜拜"或"晚安"结束, 让它回一句
  ③ 【关键】静置 3~5 分钟别说话 (等跨区长连接被中间层掐断)
  ④ 再喊唤醒词, 试着说话 —— 这时通常卡死/没反应
  ⑤ Ctrl-C 停止, 把生成的 .log 文件整个发回来

我要在日志里找的证据 (脚本会用 >>> 标出来):
  • "Websocket disconnected"      → 设备到底有没有收到断开回调 (现象1根因)
  • "Channel timeout 120 seconds" → 通道判超时了
  • "Failed to receive server hello" / "Failed to connect" → 重连握手失败
  • "Wake word detected ... (state: N)" → 卡死时 N 是几 (非3=坐实卡在非Idle)
========================================================================
GUIDE
printf "按 Enter 开始抓日志 (Ctrl-C 结束)..."
read -r _

LOG="stackchan-diag-$(date +%Y%m%d-%H%M%S).log"

if command -v python3 >/dev/null 2>&1 && python3 -c 'import serial' 2>/dev/null; then
  python3 - "$PORT" "$LOG" <<'PY'
import sys, re
import serial
port, logpath = sys.argv[1], sys.argv[2]
KEYS = re.compile(r"Websocket disconnected|Channel timeout|Failed to (connect|receive)|"
                  r"Wake word detected|server hello|OpenAudioChannel|[Ee]rror|[Rr]econnect")
try:
    s = serial.Serial(port, 115200, timeout=1)
except Exception as e:
    print(f"打不开串口 {port}: {e}")
    print("确认没别的程序占着串口(Arduino IDE/另一个 monitor), 或换个 USB 口。")
    sys.exit(1)
print(f"[已连 {port} @115200, 日志存到 {logpath}, Ctrl-C 停止]")
buf = b""
with open(logpath, "w", encoding="utf-8") as f:
    try:
        while True:
            buf += s.read(256)
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode(errors="replace").rstrip("\r")
                f.write(line + "\n"); f.flush()
                if KEYS.search(line):
                    print(">>> " + line)   # 关键行标出来
                else:
                    print("    " + line)
    except KeyboardInterrupt:
        print(f"\n完整日志已存到: {logpath}  (把它发回来)")
PY
else
  echo "缺 pyserial: 运行  pip3 install pyserial  再重试"
  echo "(或者你装了 esp-idf 也可以直接: idf.py -p $PORT monitor)"
  exit 1
fi
