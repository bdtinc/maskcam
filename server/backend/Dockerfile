FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7

RUN python -m pip install --upgrade pip

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

ENV PYTHONPATH=/app
COPY ./app ./app/
