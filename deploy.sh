#!/bin/bash
set -euo pipefail

cd "$APP_DIR"

set_env() {
  local file=$1 key=$2 value=$3
  if grep -q "^$key=" "$file"; then
    sed -i "s|^$key=.*|$key=$value|" "$file"
  else
    echo "$key=$value" >> "$file"
  fi
}

ensure_secret() {
  local file=$1 key=$2 gen=$3 val
  val=$(grep "^$key=" "$file" | head -n1 | cut -d= -f2-)
  if [ -z "$val" ]; then
    set_env "$file" "$key" "$($gen)"
    echo "    $key gerado em $file"
  fi
}

echo "==> [1/7] Primeira configuração (.env)"

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "    backend/.env criado a partir do exemplo"
fi
ensure_secret backend/.env DJANGO_SECRET_KEY "openssl rand -hex 32"
set_env backend/.env DEBUG False
set_env backend/.env ALLOWED_HOSTS "$VPS_HOST,localhost,127.0.0.1,backend"
set_env backend/.env POSTGRES_PASSWORD "${POSTGRES_PASSWORD:-postgres}"

if [ ! -f frontend/.env.local ]; then
  cp frontend/.env.production.example frontend/.env.local
  echo "    frontend/.env.local criado a partir do exemplo de produção"
fi
ensure_secret frontend/.env.local AUTH_SECRET "openssl rand -base64 32"

if [ ! -f .env ]; then
  printf 'NEXT_PUBLIC_API_URL=\n' > .env
  echo "    .env (raiz) criado com NEXT_PUBLIC_API_URL vazio (mesma origem)"
fi
set -a; source .env; set +a

PREV=$(git rev-parse HEAD)

echo "==> [2/7] Atualizando código (branch main)"
git fetch origin main
git checkout main
git pull --ff-only origin main

echo "==> [3/7] Build das imagens"
docker compose -f docker-compose.prod.yml build

echo "==> [4/7] Subindo containers"
docker compose -f docker-compose.prod.yml up -d

echo "==> [5/7] Aguardando banco de dados ficar pronto"
docker compose -f docker-compose.prod.yml exec -T backend \
  sh -c 'until python -c "import socket; socket.create_connection((\"db\", 5432), 2).close()"; do sleep 2; done'

echo "==> [6/7] Aplicando migrations (usuário postgres)"
docker compose -f docker-compose.prod.yml exec -T \
  -e DB_USER=postgres -e DB_PASSWORD="$POSTGRES_PASSWORD" \
  backend python manage.py migrate

echo "==> [7/7] Health check"
if curl -fsS http://localhost/ >/dev/null; then
  echo "OK - aplicação respondeu"
else
  echo "FALHA - aplicação não respondeu. Fazendo rollback para $PREV"
  git checkout "$PREV"
  docker compose -f docker-compose.prod.yml build
  docker compose -f docker-compose.prod.yml up -d
  exit 1
fi

docker compose -f docker-compose.prod.yml ps
