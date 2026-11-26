#!/bin/sh
set -e

# Só o servidor web publica estáticos (volume compartilhado com o nginx);
# worker, beat e migrate usam a mesma imagem e pulam esta etapa.
if [ "$1" = "gunicorn" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
