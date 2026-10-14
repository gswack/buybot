# ---- Build stage ----
FROM node:22-slim AS build
WORKDIR /app

# API base URL is baked into the bundle at build time. Default to same-origin
# "/api" so the browser calls the public VM, where Nginx proxies to the backend.
# Vite only exposes vars prefixed VITE_ and only reads them during the build.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Install dependencies (use lockfile for reproducible builds)
COPY package*.json ./
RUN npm ci

# Build the Vite app into /app/dist
COPY . .
RUN npm run build

# ---- Serve stage (Nginx: static site + /api reverse proxy) ----
FROM nginx:1.27-alpine AS serve

# Built static assets
COPY --from=build /app/dist /usr/share/nginx/html

# Config template; BACKEND_URL is substituted at container start.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Default backend target; override at `docker run` time with -e BACKEND_URL=...
# The nginx:alpine image auto-runs envsubst on /etc/nginx/templates/*.template
# into /etc/nginx/conf.d/ before starting, so ${BACKEND_URL} is filled in.
ENV BACKEND_URL=http://127.0.0.1:8000

EXPOSE 3000
# (base image's entrypoint handles envsubst + nginx start)
