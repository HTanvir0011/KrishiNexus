# syntax=docker/dockerfile:1
# KrishiNexus OS frontend: Vite production build served by nginx, which proxies the API and /ws to the backend.
ARG NODE_VERSION=24
FROM node:${NODE_VERSION}-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# VITE_API_BASE stays unset so the app calls same-origin paths that nginx forwards.
RUN npm run build

FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -qO /dev/null http://127.0.0.1/ || exit 1
