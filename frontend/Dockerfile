# syntax=docker/dockerfile:1
#
# IMPORTANT: build context must be the REPO ROOT, not frontend/.
# This is an npm-workspaces monorepo — package-lock.json lives at the root,
# so `npm ci` needs both root and frontend package.json files visible in the
# build context. docker-compose.yml sets `context: .` + `dockerfile:
# frontend/Dockerfile` for this service; if building manually, run from the
# repo root: `docker build -f frontend/Dockerfile -t intelligrade-frontend .`

# ============================================================
# Dependencies (root-scoped: only the frontend workspace's deps)
# ============================================================
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY frontend/package.json ./frontend/package.json
# Root devDependencies (husky, commitlint) aren't part of this scoped
# install. That's fine — the root "prepare" script is guarded (`husky ||
# true` in package.json) specifically so a scoped `npm ci` like this one
# doesn't abort just because husky isn't present. Do NOT add
# --ignore-scripts here: frontend deps (e.g. esbuild, via vite) rely on
# their own install-time scripts to fetch platform-specific native binaries.
RUN npm ci --workspace=frontend

# ============================================================
# Development image (Vite dev server, hot reload)
# ============================================================
FROM node:20-alpine AS development
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./frontend/
WORKDIR /app/frontend
EXPOSE 5173
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:5173/ || exit 1
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ============================================================
# Build
#
# Module 08: Vite bakes `import.meta.env.VITE_*` into the static bundle at
# BUILD time, not runtime — unlike the backend's env vars (read fresh on
# every container start), changing `VITE_API_BASE_URL` for a different
# deployment target means rebuilding this image with a different
# `--build-arg`, not just changing an env var on the running container.
# `docker-compose.prod.yml` passes this via `build.args`; a manual build
# needs `--build-arg VITE_API_BASE_URL=https://api.example.com/api/v1`.
# ============================================================
FROM deps AS build
WORKDIR /app
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_APP_NAME=IntelliGrade
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_APP_NAME=${VITE_APP_NAME}
COPY frontend/ ./frontend/
RUN npm run build --workspace=frontend

# ============================================================
# Production image (static files served by nginx)
#
# Module 08: `nginxinc/nginx-unprivileged` (the nginx project's own
# non-root variant — runs entirely as the unprivileged `nginx` user,
# including the master process, by listening on 8080 instead of 80) rather
# than hand-rolling a `USER`/chown setup on top of the standard root-owned
# image. The top-level reverse proxy (see `nginx/` at the repo root) is
# what actually terminates port 80/443 and forwards to this container's
# 8080 — this image never needs a privileged port itself.
# ============================================================
FROM nginxinc/nginx-unprivileged:1.31-alpine AS production
COPY --from=build /app/frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8080/ || exit 1

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
