# Pip Forex Screener — Railway / Docker
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Jakarta \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Railway Worker service: tidak butuh PORT / web server.
# scheduler.py jalan terus, scan tiap 30 mnt, kirim Telegram jam 07:00 & 19:30 WIB.
CMD ["python", "scheduler.py"]
