#!/usr/bin/env bash
# 跑 Kimodo 关键帧补帧。需要先按 Kimodo 官方说明装好环境、下好权重（NVIDIA Open Model License）。
#   KIMODO_HOME=<放 hf/ 和 text_encoders/ 的目录> WORK_DIR=<工作目录> PYTHON=<kimodo venv 的 python> bash run_kimodo.sh <act>[,<act>...]
set -e
: "${KIMODO_HOME:?set KIMODO_HOME}"
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$KIMODO_HOME"
export CHECKPOINT_DIR=$KIMODO_HOME/hf/nvidia TEXT_ENCODERS_DIR=$KIMODO_HOME/text_encoders TEXT_ENCODER_MODE=local HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader || true
"${PYTHON:-python}" "$HERE/kimodo_inbetween.py" "$@"
