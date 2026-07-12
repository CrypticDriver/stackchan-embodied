#!/usr/bin/env bash
# diag-boot.sh — 抓狗蛋"开机头几秒"日志, 确认本地人脸检测任务起没起。
#
# CoreS3 是原生 USB, 重启会断串口再重连, 普通抓法会错过开头。
# 本脚本循环重连串口: 你按机身 RESET 键(或拔插电)后, 它一连上就抓到开机日志。
#
# 用法 (Mac):
#   1) ls /dev/cu.usbmodem*  找串口
#   2) bash diag-boot.sh /dev/cu.usbmodemXXXX
#   3) 看到 "等待设备..." 后, 按狗蛋机身侧面的 RESET 键 (或拔一下 USB 再插)
#   4) 抓到 30 秒日志后自动停, 或随时 Ctrl-C
#
# 要确认的关键行 (脚本用 >>> 标出):
#   >>> HAL-FACE: init                         → 人脸检测任务已启动
#   >>> HAL-FACE: HumanFaceDetect model loaded → esp-dl 模型加载成功 (开机~6s)
#   >>> HAL-FACE: face APPEAR                   → 检测到人脸 (凑到镜头前时)
# 如果开机 10 秒后仍无任何 HAL-FACE 行 → 任务没起来 (要查)。

PORT="${1:-}"
if [ -z "$PORT" ]; then
  echo "用法: bash diag-boot.sh <串口>   (先 ls /dev/cu.usbmodem*)"
  exit 1
fi

if ! python3 -c 'import serial' 2>/dev/null; then
  echo "缺 pyserial: 运行  pip3 install pyserial  再重试"
  exit 1
fi

LOG="stackchan-boot-$(date +%Y%m%d-%H%M%S).log"
echo "======================================================================"
echo " 抓开机日志确认人脸检测。日志存到: $LOG"
echo " 现在【按狗蛋机身 RESET 键】(或拔 USB 再插), 脚本会自动抓到开机段。"
echo " 抓够 30 秒自动停, 或 Ctrl-C。同时【把脸凑到镜头前】看有没有 face APPEAR。"
echo "======================================================================"

python3 - "$PORT" "$LOG" <<'PY'
import sys, re, time
import serial
port, logpath = sys.argv[1], sys.argv[2]
KEYS = re.compile(r"HAL-FACE|face |model loaded|human_face|esp-dl|Camera|StackChanCamera|GrabForDetect")
deadline = None
buf = b""
print("等待设备... (按 RESET 键 / 拔插 USB)")
with open(logpath, "w", encoding="utf-8") as f:
    while True:
        try:
            s = serial.Serial(port, 115200, timeout=1)
        except Exception:
            time.sleep(0.3)
            continue
        print(f"[已连 {port}, 抓 30 秒]")
        deadline = time.time() + 30
        try:
            while time.time() < deadline:
                try:
                    chunk = s.read(256)
                except Exception:
                    break  # 串口断了(重启中), 回外层重连
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode(errors="replace").rstrip("\r")
                    f.write(line + "\n"); f.flush()
                    print((">>> " if KEYS.search(line) else "    ") + line)
        except KeyboardInterrupt:
            break
        finally:
            try: s.close()
            except Exception: pass
        if deadline and time.time() >= deadline:
            break
print(f"\n完整日志: {logpath}  (把它发回来)")
PY
