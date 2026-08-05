FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CYBERFORGE_BIND=0.0.0.0
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY cyberforge_sidecar ./cyberforge_sidecar
EXPOSE 8788
CMD ["python", "-m", "cyberforge_sidecar"]
