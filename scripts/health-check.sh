#!/usr/bin/env bash
# 狗蛋各组件健康检查。绿=OK 红=异常。可跨区跑 (探本机 + us-west ALB)。
set -uo pipefail

G="\033[32m✓\033[0m"; R="\033[31m✗\033[0m"; Y="\033[33m•\033[0m"
ok(){ echo -e " $G $1"; }; bad(){ echo -e " $R $1"; }; warn(){ echo -e " $Y $1"; }

echo "== systemd 服务 (本机) =="
for u in stackchan-xiaozhi stackchan-brainrouter stackchan-litellm \
         stackchan-watcher stackchan-console stackchan-goserver; do
  if systemctl list-unit-files "$u.service" >/dev/null 2>&1 && \
     [ -f "/etc/systemd/system/$u.service" ]; then
    state=$(systemctl is-active "$u" 2>/dev/null)
    [ "$state" = active ] && ok "$u" || bad "$u ($state)"
  fi
done

echo "== loopback 端点 =="
for probe in "4001:/health:brain-router" "4000:/health/liveliness:litellm" \
             "9101:/goudan/devices:body 端点" "9100:/console/api/health:控制台"; do
  port=${probe%%:*}; rest=${probe#*:}; path=${rest%%:*}; name=${rest#*:}
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 5 "http://127.0.0.1:$port$path" 2>/dev/null)
  [ "$code" = 200 ] && ok "$name ($port)" || warn "$name ($port) → $code"
done

echo "== OpenClaw 大脑 =="
if [ -n "${OPENCLAW_URL:-}" ]; then
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 6 "${OPENCLAW_URL%/chat/completions}/models" \
         -H "Authorization: Bearer ${OPENCLAW_TOKEN:-}" 2>/dev/null)
  [ "$code" = 200 ] && ok "OpenClaw gateway" || bad "OpenClaw gateway → $code"
fi

echo "== 设备接入 (经 CloudFront) =="
if [ -n "${PUBLIC_DOMAIN:-}" ]; then
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 8 -X POST "https://$PUBLIC_DOMAIN/xiaozhi/ota/" \
         -H "Device-Id: healthcheck" -H "Client-Id: hc" -H "Content-Type: application/json" -d '{}' 2>/dev/null)
  [ "$code" = 200 ] && ok "OTA via CloudFront" || bad "OTA via CloudFront → $code"
fi

echo "完成。"
