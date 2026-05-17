#!/bin/bash

echo "🚀 Bitrade 시스템 서비스 등록을 시작합니다..."

CURRENT_USER=$(whoami)
CURRENT_DIR=$(pwd)

# 가상환경 파이썬 경로 탐색
if [ -f "${CURRENT_DIR}/.venv/bin/python" ]; then
    PYTHON_PATH="${CURRENT_DIR}/.venv/bin/python"
    echo "ℹ️ 가상환경(.venv) 파이썬을 사용합니다: ${PYTHON_PATH}"
else
    PYTHON_PATH="/usr/bin/python3"
    echo "ℹ️ 시스템 파이썬을 사용합니다: ${PYTHON_PATH}"
fi

# 서비스 파일 생성
cat << EOF | sudo tee /etc/systemd/system/bitrade.service > /dev/null
[Unit]
Description=Bitrade Auto Scalping Bot
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${CURRENT_DIR}
ExecStart=${PYTHON_PATH} main.py
Restart=always
RestartSec=5
StandardOutput=append:${CURRENT_DIR}/trading.log
StandardError=append:${CURRENT_DIR}/trading.log

[Install]
WantedBy=multi-user.target
EOF

echo "✅ 서비스 파일 생성 완료 (/etc/systemd/system/bitrade.service)"

# 시스템 데몬 리로드 및 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl enable bitrade
sudo systemctl restart bitrade

echo ""
echo "🎉 서비스 등록 및 백그라운드 실행이 완료되었습니다!"
echo "--------------------------------------------------------"
echo "📊 실시간 로그 확인 명령어: sudo journalctl -u bitrade -f -n 50"
echo "🛑 봇 중지 명령어: sudo systemctl stop bitrade"
echo "▶️ 봇 시작 명령어: sudo systemctl start bitrade"
echo "🔄 봇 재시작 명령어: sudo systemctl restart bitrade"
echo "--------------------------------------------------------"

