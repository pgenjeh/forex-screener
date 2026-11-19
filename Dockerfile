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
# run_services.py jalan terus: scheduler (scan 30 mnt + Telegram 07:00 & 19:30 WIB)
# + bot.py (jawab /cek /xau /majors kapan saja).
CMD ["python", "run_services.py"]
