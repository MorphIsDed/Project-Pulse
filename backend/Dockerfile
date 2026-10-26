FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PROJECTPULSE_ENV=production
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend/ /app/
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data /backups && chown -R appuser:appuser /app /data /backups
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "flask --app wsgi init-db && exec gunicorn --bind=0.0.0.0:8000 --workers=2 --access-logfile=- --error-logfile=- wsgi:app"]
