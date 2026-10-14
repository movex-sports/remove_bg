FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REMBG_MODEL=u2netp \
    OMP_NUM_THREADS=1 \
    U2NET_HOME=/models

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

ARG REMBG_MODEL=u2netp
RUN mkdir -p "${U2NET_HOME}" \
    && python -c "from rembg import new_session; new_session('${REMBG_MODEL}')"

COPY main.py .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
