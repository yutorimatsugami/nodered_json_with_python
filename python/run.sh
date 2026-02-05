#!/bin/bash
# Patrol Service 起動スクリプト

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# venv がなければ作成
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# venv を有効化
source venv/bin/activate

# 依存関係インストール
pip install -q -r requirements.txt

# サービス起動
echo "Starting Patrol Service..."
python patrol_service.py
