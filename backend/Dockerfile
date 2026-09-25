FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python retrain_model.py

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "if [ \"$AUTO_CREATE_TABLES\" = \"true\" ]; then flask db upgrade; fi; if [ \"$RUN_MIGRATIONS\" = \"true\" ]; then flask db upgrade; fi; gunicorn --bind 0.0.0.0:$PORT --workers ${WEB_CONCURRENCY:-2} --timeout 120 app:app"]
