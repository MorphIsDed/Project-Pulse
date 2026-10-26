FROM node:22-alpine AS frontend-build
WORKDIR /src
COPY frontend/package.json ./package.json
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /src/dist /srv
