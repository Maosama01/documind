# DocuMind web: build the static site, then serve it with nginx, which also
# forwards /api to the API container (nginx.conf). Built by docker-compose.yml
# (service "web"), or by hand: docker build -t documind-web frontend

FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.ts tsconfig.json ./
COPY public ./public
COPY src ./src
# Type-checks, then builds into dist/ (development-only code is dropped)
RUN npm run build

FROM nginx:1.30-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
