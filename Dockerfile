# Python 3.11 슬림 이미지를 기반으로 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필수 라이브러리 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 파일 전체 복사
COPY . .

# 포트 개방 (대시보드용)
EXPOSE 8000

# 봇 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
