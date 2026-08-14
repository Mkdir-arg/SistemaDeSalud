FROM python:3.12-slim

# Evita .pyc y fuerza salida sin buffer (logs en tiempo real).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Versión del cliente de Postgres. TIENE que coincidir con la del servidor.
#
# Debian trixie trae el 17 y el servidor de este compose es el 16: con esa
# combinación `pg_dump` escribe `SET transaction_timeout`, que el 16 no conoce, y
# el respaldo sale bien pero no se puede restaurar. O sea, un archivo con nombre
# de respaldo. Se pincha a propósito y `manage.py respaldar` avisa si no coincide.
ARG PG_MAJOR=16

# Dependencias del sistema mínimas para psycopg y compilación de ruedas.
#
# El cliente (pg_dump/psql) va en la imagen de la aplicación a propósito:
# `manage.py respaldar` no sólo saca el volcado, lo RESTAURA para verificarlo, y
# hacer eso desde otro contenedor sería una segunda cosa que configurar —y que
# alguien olvida de configurar—.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential libpq-dev curl ca-certificates gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
       -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends "postgresql-client-${PG_MAJOR}" \
    && apt-get purge -y curl gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python (capa cacheable).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la app.
COPY . .

# Estáticos del admin/DRF para que WhiteNoise los sirva.
RUN python manage.py collectstatic --noinput

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "cauce.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
