FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# xgboost needs the OpenMP runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
ENV FLASK_ENV=production
EXPOSE 8000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --workers ${WEB_CONCURRENCY:-2} --timeout 120 app:app"]
