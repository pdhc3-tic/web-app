#!/bin/bash
set -euo pipefail

DEPLOY_PHASE="initialização"
trap 'status=$?; if [ "$status" -ne 0 ]; then printf "DEPLOY_FAILURE phase=%s exit_code=%s\n" "$DEPLOY_PHASE" "$status"; fi' EXIT

: "${VPS_APP_DIR:?VPS_APP_DIR precisa apontar para o diretório da aplicação na VPS}"
: "${SUPERUSER_EMAIL:?SUPERUSER_EMAIL precisa ser configurado}"
: "${SUPERUSER_NAME:?SUPERUSER_NAME precisa ser configurado}"
: "${SUPERUSER_PASSWORD:?SUPERUSER_PASSWORD precisa ser configurado}"
cd "$VPS_APP_DIR"

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

# Fonte da FIELD_ENCRYPTION_KEY: prioriza o valor vindo do secret
# FIELD_ENCRYPTION_KEY do GitHub Actions (backup durável, fora da VPS); se
# ele não estiver configurado ainda, gera localmente como fallback. Em
# qualquer caso, quem decide se o valor é GRAVADO é o ensure_secret logo
# abaixo — que só escreve se backend/.env ainda não tiver essa chave.
field_encryption_key_source() {
  if [ -n "${FIELD_ENCRYPTION_KEY:-}" ]; then
    printf '%s' "$FIELD_ENCRYPTION_KEY"
  else
    openssl rand -base64 32
  fi
}

DEPLOY_PHASE="configuração de ambiente"
echo "==> [1/11] Primeira configuração (.env)"

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "    backend/.env criado a partir do exemplo"
fi
ensure_secret backend/.env DJANGO_SECRET_KEY "openssl rand -hex 32"
# FIELD_ENCRYPTION_KEY criptografa em repouso os campos sensíveis de
# MembroFamilia (saude, cor_raca). NUNCA sobrescrever um valor já existente:
# trocar a chave torna os dados já gravados indecifráveis (perda de dado).
# ensure_secret só gera/grava quando o valor está vazio, então é seguro
# manter esta linha em todo deploy — mesmo que o secret do GitHub mude
# depois, o valor já gravado na VPS não é tocado.
ensure_secret backend/.env FIELD_ENCRYPTION_KEY field_encryption_key_source
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
: "${SEED_DATA_DIR:?SEED_DATA_DIR precisa apontar para o diretório dos XLSX na VPS}"
if [ ! -d "$SEED_DATA_DIR" ]; then
  echo "FALHA - diretório de seed não encontrado: $SEED_DATA_DIR"
  exit 1
fi
SEED_DATA_DIR="$(realpath "$SEED_DATA_DIR")"
case "$SEED_DATA_DIR" in
  "$VPS_APP_DIR"|"$VPS_APP_DIR"/*)
    echo "FALHA - dados de seed precisam ficar fora do diretório da aplicação: $SEED_DATA_DIR"
    exit 1
    ;;
esac
if find "$SEED_DATA_DIR" -maxdepth 1 -perm /007 -print -quit | grep -q .; then
  echo "FALHA - diretório ou arquivos de seed não podem ter permissões para grupo/outros."
  exit 1
fi
export SEED_DATA_DIR
SEED_PACKAGE_DIR="${SEED_PACKAGE_DIR:-$(dirname "$SEED_DATA_DIR")/pdhc-seed-package}"
case "$SEED_PACKAGE_DIR" in
  "$VPS_APP_DIR"|"$VPS_APP_DIR"/*)
    echo "FALHA - pacote de seed precisa ficar fora do diretório da aplicação: $SEED_PACKAGE_DIR"
    exit 1
    ;;
esac
mkdir -p "$SEED_PACKAGE_DIR"
chmod 700 "$SEED_PACKAGE_DIR"
export SEED_PACKAGE_DIR

PREV=$(git rev-parse HEAD)

DEPLOY_PHASE="atualização do código"
echo "==> [2/11] Atualizando código (branch main)"
git fetch origin main
git checkout main
git pull --ff-only origin main

DEPLOY_PHASE="build das imagens"
echo "==> [3/11] Build das imagens"
docker compose -f docker-compose.prod.yml build

DEPLOY_PHASE="validação da árvore de migrations"
echo "==> [4/11] Validando árvore de migrations"
if ! docker compose -f docker-compose.prod.yml run --rm --no-deps \
  --entrypoint python backend manage.py makemigrations --check --dry-run; then
  echo "FALHA - há migrations conflitantes ou alterações de modelos sem migration versionada."
  echo "Resolva o conflito localmente, gere uma merge migration revisada e faça o commit antes de tentar novamente."
  exit 1
fi

DEPLOY_PHASE="subida dos containers"
echo "==> [5/11] Subindo containers"
docker compose -f docker-compose.prod.yml up -d

DEPLOY_PHASE="aguardo do banco de dados"
echo "==> [6/11] Aguardando banco de dados ficar pronto"
docker compose -f docker-compose.prod.yml exec -T backend \
  sh -c 'until python -c "import socket; socket.create_connection((\"db\", 5432), 2).close()"; do sleep 2; done'

DEPLOY_PHASE="preparação do pacote de seed"
echo "==> [7/11] Preparando pacote normalizado de seed"
docker compose -f docker-compose.prod.yml run --rm --no-deps \
  -v "$SEED_DATA_DIR:/seed-data:ro" \
  -v "$SEED_PACKAGE_DIR:/seed-package" \
  backend python manage.py prepare_seed \
  --source-dir /seed-data \
  --output-dir /seed-package

DEPLOY_PHASE="aplicação das migrations"
echo "==> [8/11] Aplicando migrations (usuário postgres)"
docker compose -f docker-compose.prod.yml exec -T \
  -e DB_USER=postgres -e DB_PASSWORD="$POSTGRES_PASSWORD" \
  backend python manage.py migrate

DEPLOY_PHASE="provisionamento do superusuário"
echo "==> [9/11] Garantindo superusuário de produção"
docker compose -f docker-compose.prod.yml exec -T \
  -e SUPERUSER_EMAIL="$SUPERUSER_EMAIL" \
  -e SUPERUSER_NAME="$SUPERUSER_NAME" \
  -e SUPERUSER_PASSWORD="$SUPERUSER_PASSWORD" \
  backend python manage.py ensure_superuser

DEPLOY_PHASE="importação dos dados legados"
echo "==> [10/11] Importando dados legados"
docker compose -f docker-compose.prod.yml run --rm --no-deps \
  -v "$SEED_PACKAGE_DIR:/seed-package:ro" \
  backend python manage.py seed_prod \
  --package-dir /seed-package

DEPLOY_PHASE="health check"
echo "==> [11/11] Health check"
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
