# --- Etapa de build: compila la SPA con Vite ---
FROM node:20-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# A dónde apunta la SPA para hablar con la API.
#
# Vite INCRUSTA `import.meta.env.*` en el bundle durante el build: definir esto
# en el entorno del contenedor que sirve los estáticos no tiene ningún efecto, ya
# es tarde. Por eso entra como build arg y no como variable de ejecución.
#
# Vacío por defecto a propósito: así el cliente cae en `/api` relativo, que es lo
# que sirve cuando nginx y Django están detrás del mismo dominio (docker
# compose). Se pasa con valor cuando el frontend y la API viven en dominios
# distintos —un servicio por dominio, como en Railway—, donde una ruta relativa
# le pegaría al propio nginx y devolvería el index.html.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# --- Etapa final: nginx sirve los estáticos ---
FROM nginx:1.27-alpine

# Cuál de las dos configuraciones se usa.
#
# `nginx.conf` (default) proxea /api, /admin y /static al servicio `backend`: es
# la de docker compose, donde todo vive detrás del mismo dominio.
#
# `nginx.railway.conf` sirve sólo los estáticos, para cuando el frontend se
# despliega solo y la API está en otro dominio. Ahí el proxy no puede existir:
# nginx resuelve los destinos de `proxy_pass` al cargar la config y no arrancaría.
ARG NGINX_CONF=nginx.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
