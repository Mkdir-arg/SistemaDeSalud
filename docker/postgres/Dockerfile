# PostgreSQL 16 con WAL-G y restic para el respaldo continuo (#172, AUD-017).
#
# Es la misma base que usa el compose (`postgres:16-alpine`) a propósito: pasar
# a una imagen Debian cambia musl por glibc, y con eso las colaciones; los
# índices de texto de una base ya creada quedarían inválidos.
#
# Solo la usa `docker-compose.respaldo.yml`. El compose base, dev, demo y CI
# siguen con la imagen oficial sin cambios.
FROM postgres:16-alpine

# WAL-G no publica binario para musl: los de la release están compilados en
# Ubuntu contra glibc (solo enlazan libc y libm; libsodium va adentro). Alpine
# los corre con `gcompat`, la capa de compatibilidad de glibc del propio
# repositorio de Alpine. La alternativa sin gcompat es compilar WAL-G desde el
# código del tag en una etapa previa (ver el runbook); el ensayo de
# restauración se hizo con esta combinación.
#
# La suma es la que la release publica en `<archivo>.sha256`, copiada acá: si
# el archivo cambia en origen, el build falla en lugar de instalar otra cosa.
ARG WALG_VERSION=v3.0.9
ARG WALG_SHA256_AMD64=4f03ee4679db7f660bfd1b2b8291ac5df247cd2ec48074b60c112f4897299f24
ARG WALG_SHA256_ARM64=20191a37ad091a880c25f4cc907e6f0deb7f12bdd8a53fd62dbc7fcbf2eac712
ARG TARGETARCH

RUN set -eu; \
    apk add --no-cache gcompat; \
    case "${TARGETARCH:-amd64}" in \
      amd64) arq=amd64; suma="$WALG_SHA256_AMD64" ;; \
      arm64) arq=aarch64; suma="$WALG_SHA256_ARM64" ;; \
      *) echo "Arquitectura sin binario de WAL-G: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    archivo="wal-g-pg-22.04-${arq}.tar.gz"; \
    wget -q -O "/tmp/${archivo}" \
      "https://github.com/wal-g/wal-g/releases/download/${WALG_VERSION}/${archivo}"; \
    echo "${suma}  /tmp/${archivo}" | sha256sum -c -; \
    tar -xzf "/tmp/${archivo}" -C /tmp; \
    install -m 0755 "/tmp/wal-g-pg-22.04-${arq}" /usr/local/bin/wal-g; \
    rm -f "/tmp/${archivo}" "/tmp/wal-g-pg-22.04-${arq}"; \
    wal-g --version

# restic para media y facturas, copiado de la imagen oficial fijada por digest
# (0.19.1). Va en esta imagen y no en la suya porque el job necesita `psql`
# para dejar el latido; es un binario estático y no depende de la libc.
COPY --from=restic/restic:0.19.1@sha256:136600b6ff6843d61d355f7f71f460a166429f35de6fd11b568fece3c9a4d510 \
     /usr/bin/restic /usr/local/bin/restic

COPY iniciar-db.sh respaldo-continuo.sh /usr/local/bin/
# El checkout de Windows puede entregar CRLF; el shebang tiene que ser LF.
RUN sed -i 's/\r$//' /usr/local/bin/iniciar-db.sh /usr/local/bin/respaldo-continuo.sh \
    && chmod 0755 /usr/local/bin/iniciar-db.sh /usr/local/bin/respaldo-continuo.sh \
    && restic version

ENTRYPOINT ["iniciar-db.sh"]
CMD ["postgres"]
