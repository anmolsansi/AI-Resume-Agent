FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data
COPY output ./output

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.web_app:app", "--host", "0.0.0.0", "--port", "8000"]
