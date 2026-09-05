FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY sql ./sql
COPY config ./config
RUN python -m pip install --upgrade pip \
    && python -m pip install ".[aws,orchestration]"

USER app
CMD ["prefect", "worker", "start", "--pool", "comercial-andina-ecs"]
