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
| **db**           | PostgreSQL 16          | `5432` | Banco de dados relacional       |
| **redis**        | Redis 7                | `6379` | Cache + broker do Celery        |
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

O deploy é executado pelo GitHub Actions na branch `main`. O workflow roda os
testes e a verificação de migrations em um ambiente CI e, somente se passarem,
conecta na VPS por SSH e executa `deploy.sh`. Na VPS, o script faz `git pull`,
build das imagens, valida novamente as migrations, prepara o pacote de seed,
aplica as migrations, importa os dados e executa o health check.

### Secrets do GitHub Actions

Configure em **Settings → Secrets and variables → Actions → Repository secrets**:

| Secret | Uso |
|--------|-----|
| `VPS_HOST` | Host ou IP da VPS; também entra em `ALLOWED_HOSTS` |
| `VPS_USER` | Usuário SSH usado pelo deploy |
| `VPS_PORT` | Porta SSH |
| `SSH_PRIVATE_KEY` | Chave privada correspondente à chave autorizada na VPS |
| `VPS_APP_DIR` | Caminho absoluto do checkout na VPS |
| `POSTGRES_PASSWORD` | Senha administrativa do PostgreSQL |
| `SEED_DATA_DIR` | Caminho absoluto dos XLSX privados na VPS |
| `SUPERUSER_EMAIL` | E-mail do administrador inicial |
| `SUPERUSER_NAME` | Nome do administrador inicial |
| `SUPERUSER_PASSWORD` | Senha do administrador inicial |
| `SLACK_WEBHOOK_URL` | Webhook usado nas notificações de sucesso e falha |

O workflow não versiona nem transporta os XLSX. O `SEED_DATA_DIR` é apenas
enviado ao script remoto. Não coloque valores de secrets em arquivos do
repositório ou nos logs.

### Preparação da VPS

O usuário SSH precisa ter Docker, o plugin Docker Compose, Git, `curl`,
`openssl`, `realpath` e `find`, além de permissão para executar Docker
(normalmente, estar no grupo `docker`). O repositório deve estar clonado em
`VPS_APP_DIR`, na branch `main`, e `deploy.sh` deve ser executável:

```bash
chmod +x deploy.sh
git checkout main
```

Mantenha os dados legados fora do checkout, por exemplo:

```text
/srv/pdhc/dados_seed/
├── Comunidades (1).xlsx
├── Culturas e Animais.xlsx
├── Municípios (1).xlsx
└── SGP.xlsx
```

O diretório e os arquivos devem ser acessíveis somente pelo usuário do deploy
(sem permissões para grupo ou outros). O pacote normalizado será criado
automaticamente em `../pdhc-seed-package`, também fora da aplicação, com
permissões restritas. Veja o formato e o relatório em
[`backend/README.md`](backend/README.md#seed-de-dados).

Na primeira execução, o script cria `backend/.env` e `frontend/.env.local` a
partir dos exemplos e gera `DJANGO_SECRET_KEY` e `AUTH_SECRET` se estiverem
vazios. Revise os demais valores de produção, especialmente `ALLOWED_HOSTS`,
`CORS_ALLOWED_ORIGINS`, storage R2 e `NEXT_PUBLIC_API_URL` no `.env` da raiz.
O `DB_PASSWORD` de `backend/.env` precisa corresponder à senha do usuário
`app_user` criado no PostgreSQL; a instalação inicial usa `app_pass` conforme
`backend/db/init/01_app_user.sql`. O `POSTGRES_PASSWORD` deve permanecer
compatível com a senha administrativa já existente no volume do banco.
As credenciais `SUPERUSER_*` são usadas somente na primeira criação; se o
superusuário já existir, o deploy preserva a senha atual.

### Política de migrations e seed

Conflitos de migrations devem ser resolvidos localmente, com uma merge
migration revisada e versionada. A VPS **não** executa
`makemigrations --merge`; o deploy aborta se
`makemigrations --check --dry-run` detectar divergências.

O seed segue o fluxo:

```text
XLSX privado → prepare_seed → pacote JSONL + manifest/report → seed_prod → PostgreSQL
```

O pacote é validado por SHA-256 antes da importação. A importação é idempotente,
preserva a identidade legada em `SeedImportRecord` e apenas relata registros
existentes no banco que não estão nas planilhas; não remove nem inativa esses
registros automaticamente.

### Falhas e notificações

Deploys são serializados para impedir duas atualizações simultâneas. Em caso de
falha nos testes ou no deploy remoto, o Slack recebe a etapa, o commit, as
últimas linhas do log e um link para o workflow. Falhas de migration ou seed
interrompem o deploy; falhas no health check acionam o rollback do código
anterior.

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