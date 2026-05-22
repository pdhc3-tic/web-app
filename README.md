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