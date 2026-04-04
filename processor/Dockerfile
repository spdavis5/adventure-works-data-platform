FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Copy application code.
COPY . .

CMD ["uv", "run", "python", "main.py"]
