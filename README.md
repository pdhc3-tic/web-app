# PDHC — Plataforma Dom Helder Câmara III

Plataforma web para o projeto Dom Helder Camâra III(PDHC), conectando territórios, organizações da sociedade civil (OSCs) e beneficiários.

## Arquitetura

```
web-app/
├── backend/            # API REST — Django 6 + DRF + Celery
├── frontend/           # Interface web — Next.js (React)
├── Docker-compose.yml  # Orquestração dos serviços
└── README.md
```

### Serviços (Docker Compose)

| Serviço          | Tecnologia         | Porta  | Descrição                          |
|------------------|--------------------|---------|------------------------------------|
| **backend**      | Python 3.12 / Django 6 | `8000` | API REST + Django Admin         |
| **frontend**     | Node 20 / Next.js      | `3000` | Interface web SPA/SSR           |
| **db**           | PostgreSQL 18          | `5432` | Banco de dados relacional       |
| **redis**        | Redis 7.4              | `6379` | Cache + broker do Celery        |
| **celery_worker**| Celery                 | —      | Processamento assíncrono        |
| **celery_beat**  | Celery Beat            | —      | Tarefas agendadas (cron)        |

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) ≥ 24.0
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.20

---

## Quick Start

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio> pdhc3-tic
cd pdhc3-tic/web-app
```

### 2. Configurar variáveis de ambiente

```bash
cp -n backend/.env.example backend/.env
cp -n frontend/.env.example frontend/.env.local
```

Preencha os valores obrigatórios:

| Arquivo | Variável | Como gerar |
|---------|----------|------------|
| `backend/.env` | `DJANGO_SECRET_KEY` | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `backend/.env` | `FIELD_ENCRYPTION_KEY` | `openssl rand -base64 32` — chave AES-256 usada para criptografar em repouso os campos sensíveis de `MembroFamilia` (saúde, cor/raça). Sem ela, qualquer operação que crie/leia/edite membros falha com `ImproperlyConfigured`. |
| `frontend/.env.local` | `AUTH_SECRET` | `openssl rand -base64 32` |

> **Nota:** As demais variáveis já possuem valores padrão adequados para desenvolvimento local. Consulte os arquivos `.env.example` para referência completa.

### 3. Subir toda a stack

```bash
sudo docker compose up --build -d
```

### 4. Aplicar migrations

O backend usa um usuário de banco limitado (`app_user`). Para migrations, use o override com `postgres`:

```bash
sudo docker compose exec \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  backend python manage.py migrate
```

### 5. Popular dados iniciais (seed)

```bash
sudo docker compose exec \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  backend python manage.py seed_core
```

### 6. Criar superusuário (opcional)

```bash
sudo docker compose exec \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  backend python manage.py createsuperuser
```

### 7. Verificar

| Serviço | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API REST | http://localhost:8000/api/v1/ |
| Django Admin | http://localhost:8000/admin/ |

---

## Deploy em produção

Produção roda nos servidores do contrato de sustentação (`pdhc-app` com a stack
e `pdhc-db` só com o PostgreSQL 18), em `https://pdhc.ufersa.edu.br`. O compose,
o Caddy (TLS), os `.env`, os papéis do banco, os backups e o runbook ficam no
repositório **archelos-devops** (`deploy/pdhc/`). Este repositório entrega
imagens e não guarda nenhum `.env` de produção.

### Fluxo (`.github/workflows/deploy.yml`)

```text
push na main → testes (Postgres 18.7) → imagens no GHCR → deploy no pdhc-app
```

1. **Testes:** `makemigrations --check` e `pytest`.
2. **Imagens:** `ghcr.io/pdhc3-tic/web-app/{backend,frontend,nginx}:<sha>`, construídas
   uma vez. A mesma imagem de backend serve backend, worker, beat e migrate.
3. **Deploy:** o job entra no `pdhc-app` com uma chave que só executa
   `/opt/pdhc/bin/promover` e passa o sha e os digests construídos no próprio run.
   No servidor, o `promover`:
   - faz dump pré-deploy se houver migration;
   - roda `migrate` como `pdhc_owner` e `verificar_papel_rls` como `pdhc_app`;
   - sobe a versão nova e confere o health (`/api/v1/health/`);
   - volta para a versão anterior se o health falhar.

**Migrations precisam ser expand/contract.** A versão anterior roda por alguns
segundos contra o schema novo, e o rollback volta para ela: remova coluna ou
tabela só no release seguinte ao que parou de usá-la. Se o push trouxer
migration com `DROP TABLE`, `DROP COLUMN`, `RENAME` ou `SET NOT NULL`, o deploy
automático para (o Slack avisa). Ele só sai pelo workflow manual (**Run
workflow**), marcando a confirmação, depois do aviso aos usuários.

### Secrets

No environment **`production`**, restrito à branch `main`, e nunca como secret de
repositório:

| Secret | Uso |
|--------|-----|
| `PDHC_DEPLOY_SSH_KEY` | Chave privada do usuário `deploy` (comando único no servidor) |
| `PDHC_DEPLOY_KNOWN_HOSTS` | Linha do `known_hosts` do `pdhc-app` |
| `PDHC_DEPLOY_HOST` | Endereço SSH do `pdhc-app` |

O `SLACK_WEBHOOK_URL` continua como secret do repositório. O push no GHCR usa o
`GITHUB_TOKEN`. Os secrets do deploy antigo devem ser apagados: `VPS_*`,
`SSH_PRIVATE_KEY`, `POSTGRES_PASSWORD`, `SEED_DATA_DIR`, `SUPERUSER_*` e,
principalmente, `FIELD_ENCRYPTION_KEY`.

### `FIELD_ENCRYPTION_KEY`

A chave cifra `saude`/`cor_raca` de `MembroFamilia` e o CPF de beneficiário.
**Trocá-la ou perdê-la apaga esses dados de vez.** Ela vive só no `.env` do
servidor e no cofre da Archelos Dev: nunca no GitHub, num dump ou em log.
`python manage.py verificar_criptografia` confere, só com contagens, se todo
valor cifrado do banco decifra com a chave em uso. É o teste do ensaio de
restauração.

### Mídia

`STORAGE_BACKEND=local`: os arquivos ficam num volume do `pdhc-app` e **não têm
rota pública**. A API devolve URLs assinadas com validade
(`/api/v1/storage/local-download/`). O Django confere a assinatura e o nginx
entrega o arquivo pela location interna `/protected-media/` (`X-Accel-Redirect`).

### Seed e primeiro superusuário

Rodam uma vez só, pelo runbook do archelos-devops, fora do deploy:

```text
XLSX privado → prepare_seed → pacote JSONL + manifest/report → seed_prod → PostgreSQL
```

O pacote é validado por SHA-256 antes da importação. A importação é
idempotente, preserva a identidade legada em `SeedImportRecord` e só relata os
registros do banco que não estão nas planilhas. Ela não remove nem inativa
esses registros. Veja o formato em
[`backend/README.md`](backend/README.md#seed-de-dados). Os XLSX têm dado pessoal
e não entram no git nem na imagem (`backend/.dockerignore`).

### O que o PR precisa avisar

O compose de produção é mantido no archelos-devops. Um PR que crie **serviço,
fila do Celery, comando de operação ou variável de ambiente** descreve a
mudança numa seção "Operação", para que ela seja replicada lá antes do merge.

### Testar as imagens de produção localmente

`docker-compose.prod.yml` sobe as imagens `Dockerfile.prod` com nginx, URL
assinada, front standalone e healthchecks, como em produção, mas com banco
local. As instruções estão no cabeçalho do arquivo.

### Notificações

O Slack recebe só a etapa, o commit e o link do run. As linhas de log não vão,
porque podem carregar dado pessoal.

---

## Comandos Úteis

### Logs

```bash
# Todos os serviços
sudo docker compose logs -f

# Serviço específico
sudo docker compose logs -f backend
```

### Testes

```bash
# Backend (pytest)
sudo docker compose exec backend pytest -v

# Testes de um módulo específico
sudo docker compose exec backend pytest apps/core/tests/test_[modulo].py -v
```

### Migrations

```bash
# Gerar novas migrations
sudo docker compose exec \
  -e DB_USER=postgres -e DB_PASSWORD=postgres \
  backend python manage.py makemigrations

# Aplicar migrations
sudo docker compose exec \
  -e DB_USER=postgres -e DB_PASSWORD=postgres \
  backend python manage.py migrate
```

### Parar / Reiniciar

```bash
# Parar todos os serviços
sudo docker compose down

# Parar e remover volumes (reset completo do banco)
sudo docker compose down -v

# Rebuild e restart
sudo docker compose up --build -d
```

### Instalar dependência no backend

```bash
# Adicione ao requirements/base.txt, depois:
sudo docker compose up --build -d backend
```

---

## Estrutura do Backend

Consulte o [README do backend](backend/README.md) para detalhes sobre a arquitetura de apps, models, permissões e API.

## Estrutura do Frontend

Consulte o [README do frontend](frontend/README.md) para detalhes sobre pages, componentes e autenticação.

---

## Convenções do Projeto

- **Branches**: `backend/issue<N>` ou `frontend/issue<N>`
- **API prefix**: `/api/v1/`
- **Autenticação**: JWT via `Authorization: Bearer <token>`
- **Testes**: pytest + factory_boy (backend)