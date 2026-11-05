FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/claim2car
COPY requirements-api.txt requirements-database.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin claim2car
COPY app/ ./app/
COPY database/ ./database/
COPY contracts/ ./contracts/
COPY migrations/ ./migrations/
COPY authority_migrations/ ./authority_migrations/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3).read()"
CMD ["python", "-m", "uvicorn", "app.intake_api:create_intake_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
