# syntax=docker/dockerfile:1

FROM node:22-slim AS builder

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

# Vite faz o replace de import.meta.env.VITE_* em tempo de build — não dá pra
# trocar a URL da API depois, em runtime. O workflow de deploy passa o valor
# real via --build-arg.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN pnpm build


FROM node:22-slim AS runtime

RUN corepack enable && npm install -g serve@14 \
    && groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

COPY --from=builder /app/dist ./dist

USER app

EXPOSE 8080

# -s: fallback pra index.html em rotas desconhecidas (SPA client-side
# routing do React Router) — sem isso, refresh em /p/:projectId/... dá 404.
CMD ["sh", "-c", "serve -s dist -l ${PORT:-8080}"]
