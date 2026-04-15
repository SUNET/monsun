FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-dev

COPY app/ app/
COPY static/ static/

EXPOSE 8081

CMD ["uv", "run", "python", "-m", "app.main"]
