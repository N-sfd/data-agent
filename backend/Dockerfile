FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libreoffice-writer-nogui \
        libreoffice-calc-nogui \
        libreoffice-impress-nogui \
    && rm -rf /var/lib/apt/lists/*

# Debian's tesseract-ocr package has moved its tessdata directory between
# releases (e.g. .../4.00/tessdata vs .../5/tessdata), and `python:3.12-slim`
# is an unpinned tag whose underlying Debian release can change between
# builds. A hardcoded TESSDATA_PREFIX silently breaks OCR the next time that
# happens (mupdf/tesseract fail with "Tesseract language initialisation
# failed" — the app then errors on every OCR page). Resolve the real
# directory at build time instead of guessing it.
RUN eng_data="$(find / -xdev -name 'eng.traineddata' 2>/dev/null | head -n1)" \
    && test -n "$eng_data" \
    && dirname "$eng_data" > /etc/tessdata_prefix \
    && echo "Resolved TESSDATA_PREFIX=$(cat /etc/tessdata_prefix)"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY migrations ./migrations

EXPOSE 8000

CMD ["sh", "-c", "export TESSDATA_PREFIX=$(cat /etc/tessdata_prefix); uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 75"]
