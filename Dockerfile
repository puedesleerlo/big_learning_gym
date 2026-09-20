FROM node:22-bookworm-slim AS web
WORKDIR /build/web
RUN corepack enable && corepack prepare pnpm@10.7.1 --activate
COPY packages/gym-frontend/ /build/packages/gym-frontend/
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm run build

FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY gym/ gym/
COPY config/ config/
COPY scripts/ scripts/
COPY --from=web /build/web/dist web/dist
COPY packages/ packages/
COPY frontend-kit/ frontend-kit/
COPY skills/build-gym-frontend/ skills/build-gym-frontend/
ENV PATH="/app/.venv/bin:$PATH" GYM_DATA_DIR=/app/data GYM_EMBEDDED_WORKER=0
RUN mkdir -p /app/data
EXPOSE 8787
CMD ["uvicorn", "gym.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8787"]
