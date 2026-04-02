#!/bin/bash

echo "🚀 Bitrade 시스템 서비스 등록을 시작합니다..."

# 서비스 파일 생성
cat << 'EOF' | sudo tee /etc/systemd/system/bitrade.service > /dev/null
[Unit]
Description=Bitrade Auto Scalping Bot
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/btrade
# 만약 가상환경(.venv)을 사용 중이라면 아래 경로를 /home/ec2-user/btrade/.venv/bin/python 으로 변경하세요.
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5
StandardOutput=append:/home/ec2-user/btrade/trading.log
StandardError=append:/home/ec2-user/btrade/trading.log

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
