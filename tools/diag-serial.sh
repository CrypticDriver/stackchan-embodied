#!/usr/bin/env bash
# diag-serial.sh — 抓狗蛋串口日志, 高亮状态机关键行, 用来坐实
# 「气泡挂整夜 + 再唤醒无法聊天只能重启」的根因。
#
# 用法 (Mac):
#   1) 插 USB 数据线, ls /dev/cu.usbmodem*  找到串口
#   2) bash diag-serial.sh /dev/cu.usbmodemXXXX
#   3) 照着屏幕提示复现: 正常聊一次 → 说"拜拜/晚安"结束 → 等 3~5 分钟(别说话)
#      → 再喊唤醒词试着聊天(此时通常卡死) → 把整段日志发回来
#
# 需要 esptool (pip3 install esptool) 或 idf.py。脚本只读不写, 绝对安全。

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
  ⑤ Ctrl-C 停止, 把从头到尾的日志整段发回来

我要在日志里找的证据:
  • "Websocket disconnected"      → 设备到底有没有收到断开回调 (现象1根因)
  • "Channel timeout 120 seconds" → 通道判超时了
  • "Failed to receive server hello" / "Failed to connect" → 重连握手失败
  • "Wake word detected ... (state: N)" → 卡死时 N 是几 (4=坐实卡Connecting)
========================================================================
按 Enter 开始抓日志 (Ctrl-C 结束)...
GUIDE
read -r _

# 高亮关键行 (grep 不过滤, 只染色, 完整日志仍全部打印)
HL='Websocket disconnected|Channel timeout|Failed to (connect|receive)|Wake word detected|SetDeviceState|error|Error|Reconnect|OpenAudioChannel|server hello'

run_monitor() {
  if command -v idf.py >/dev/null 2>&1 && [ -f sdkconfig ]; then
    idf.py -p "$PORT" monitor
  elif command -v esptool >/dev/null 2>&1 || python3 -c 'import serial' 2>/dev/null; then
    python3 - "$PORT" <<'PY'
import sys, serial
p = sys.argv[1]
s = serial.Serial(p, 115200, timeout=1)
print(f"[已连 {p} @115200, Ctrl-C 停止]")
buf = b""
while True:
    buf += s.read(256)
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        print(line.decode(errors="replace"))
PY
  else
    echo "缺工具: 装 esptool (pip3 install esptool pyserial) 或用 idf.py monitor"
    exit 1
  fi
}

# tee 存一份到文件, 方便回传
LOG="stackchan-diag-$(date +%Y%m%d-%H%M%S).log"
run_monitor | tee "$LOG" | grep --line-buffered -E --color=always "$HL|"
echo "完整日志已存到: $LOG  (把它发回来)"
