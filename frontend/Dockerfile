# Multistage build: vite build → nginx:alpine with conf + dist baked in.
# Build context is `frontend/`. TLS certs are bind-mounted at runtime
# (./frontend/tls:/etc/nginx/tls) — never baked into the image.
FROM node:24-alpine AS build
ARG VITE_SENTRY_DSN
ARG VITE_RELEASE
ARG VITE_GTM_ID
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN
ENV VITE_RELEASE=$VITE_RELEASE
ENV VITE_GTM_ID=$VITE_GTM_ID
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . ./
# sentry_auth_token is a BuildKit secret — never written to any layer
RUN --mount=type=secret,id=sentry_auth_token \
    SENTRY_AUTH_TOKEN=$(cat /run/secrets/sentry_auth_token 2>/dev/null || true) \
    npm run build

FROM nginx:1.30-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx_security_headers.conf /etc/nginx/security_headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 443
