#!/usr/bin/env bash
# 一键部署狗蛋语音栈 + brain-router + LiteLLM 辅脑 (幂等)。
#
# 前提: 已 cp deploy/env.example ../.env-stack 并填好; 本机能访问 OpenClaw gateway。
# 不做的事: CloudFront/ALB 云资源 (见 deploy/uswest/README.md 照抄) 和固件 (见 docs/flash-guide.html)。
#
# 用法: ./scripts/deploy.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO/../.env-stack"
VENV="$REPO/../xiaozhi-venv"
XZ_SRC="$REPO/../xiaozhi-esp32-server"
USER_NAME="$(whoami)"

[ -f "$ENV_FILE" ] || { echo "缺 $ENV_FILE — 先 cp deploy/env.example 并填写"; exit 1; }
set -a; . "$ENV_FILE"; set +a

echo "== 1/5 拉取 xiaozhi-esp32-server 源码 =="
[ -d "$XZ_SRC" ] || git clone --depth 1 https://github.com/xinnan-tech/xiaozhi-esp32-server "$XZ_SRC"
XZ="$XZ_SRC/main/xiaozhi-server"

echo "== 2/5 Python venv + 依赖 (CPU torch) =="
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" -q install --upgrade pip
  "$VENV/bin/pip" -q install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
  grep -v '^torch' "$XZ/requirements.txt" > /tmp/reqs.txt
  "$VENV/bin/pip" -q install -r /tmp/reqs.txt
  "$VENV/bin/pip" -q install "litellm[proxy]" boto3 aiohttp
fi

echo "== 3/5 语音模型 (SenseVoiceSmall) =="
MODEL="$XZ/models/SenseVoiceSmall/model.pt"
if [ ! -f "$MODEL" ]; then
  mkdir -p "$(dirname "$MODEL")"
  curl -fsSL -o "$MODEL" "https://modelscope.cn/models/iic/SenseVoiceSmall/resolve/master/model.pt"
fi
command -v ffmpeg >/dev/null || echo "  ⚠️ 缺 ffmpeg, 请自行安装 (ASR/TTS 需要)"

echo "== 4/5 配置注入 (占位符 → 真实值) =="
mkdir -p "$XZ/data"
sed -e "s#__OPENCLAW_TOKEN__#$OPENCLAW_TOKEN#g" \
    -e "s#__LITELLM_KEY__#$LITELLM_MASTER_KEY#g" \
    -e "s#da8daz4hvc7q8.cloudfront.net#$PUBLIC_DOMAIN#g" \
    -e "s#zh-CN-YunxiaNeural#${TTS_VOICE:-zh-CN-YunxiaNeural}#g" \
    "$REPO/deploy/xiaozhi-server/data/.config.yaml" > "$XZ/data/.config.yaml"
chmod 600 "$XZ/data/.config.yaml"
cp "$REPO/deploy/xiaozhi-server/goudan_push.py" "$REPO/deploy/xiaozhi-server/run_with_push.py" "$XZ/"
cp "$REPO/deploy/xiaozhi-server/check_work.py" "$XZ/plugins_func/functions/" 2>/dev/null || true
cp "$REPO/deploy/brain-router/brain_router.py" "$REPO/../brain_router.py"
cat > "$REPO/deploy/litellm/config.local.yaml" <<YAML
model_list:
  - model_name: stackchan-brain
    litellm_params: { model: bedrock/$BEDROCK_MODEL, aws_region_name: $BEDROCK_REGION }
litellm_settings: { drop_params: true }
general_settings: { disable_spend_logs: true }
YAML

echo "== 5/5 systemd 服务 =="
render_unit(){  # $1=name $2=exec $3=workdir
  sudo tee "/etc/systemd/system/$1.service" >/dev/null <<UNIT
[Unit]
After=network-online.target
[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$3
EnvironmentFile=$ENV_FILE
ExecStart=$2
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
}
render_unit stackchan-litellm "$VENV/bin/litellm --config $REPO/deploy/litellm/config.local.yaml --host 127.0.0.1 --port 4000" "$REPO"
render_unit stackchan-brainrouter "$VENV/bin/python $REPO/../brain_router.py" "$REPO/.."
render_unit stackchan-xiaozhi "$VENV/bin/python run_with_push.py" "$XZ"
sudo systemctl daemon-reload
sudo systemctl enable --now stackchan-litellm stackchan-brainrouter stackchan-xiaozhi

echo "== 完成。健康检查: =="
"$REPO/scripts/health-check.sh"
echo
echo "接下来: ①配 CloudFront→ALB (deploy/uswest/README.md) ②刷固件 (docs/flash-guide.html)"
