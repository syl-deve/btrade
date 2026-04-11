#!/bin/bash
# ngrok 시작 후 현재 HTTPS 주소를 디스코드로 알림

sleep 5  # ngrok 완전히 뜰 때까지 대기

URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json;print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null)

if [ -n "$URL" ]; then
    source "$(dirname "$0")/.env"
    curl -s -X POST "$DISCORD_WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "{\"content\": \"BITRADE 주소: $URL\"}"
    echo "Discord 알림 전송 완료: $URL"
else
    echo "ngrok URL 가져오기 실패"
fi
