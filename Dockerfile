# ---- Stage 1: Frontend bauen ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Laufzeit (ein einziger Container: API + statisches Frontend) ----
FROM python:3.13-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MOSI_DATA_DIR=/data MOSI_STATIC_DIR=/app/static
# Tesseract (OCR) ist optional: --build-arg INSTALL_OCR=0 spart ca. 100 MB
ARG INSTALL_OCR=1
RUN if [ "$INSTALL_OCR" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
      && rm -rf /var/lib/apt/lists/*; fi
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /web/dist ./static
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin mosi && mkdir -p /data && chown mosi /data
USER mosi
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=4).status==200 else 1)"
# Ein Worker, keine Reload-/Hintergrundprozesse: Rechenlast entsteht nur bei Anfragen.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-server-header"]
