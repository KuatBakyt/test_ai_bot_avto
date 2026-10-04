FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home app
COPY --chown=app:app . .
RUN DJANGO_SECRET_KEY=build-only-secret-at-least-32-characters DATABASE_URL=sqlite:///:memory: python manage.py collectstatic --noinput && mkdir -p /app/media && chown app:app /app/media
USER app
EXPOSE 8100
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8100", "--workers", "2", "--timeout", "90"]
