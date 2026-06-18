# Backend — Django REST Framework

API REST do PDHC construída com Django 6, Django REST Framework e Celery.

## Documentação

- [Throttling da API](docs/throttling.md)

## Banco de Dados

O PostgreSQL é inicializado com dois usuários:

| Usuário | Privilégios | Uso |
|---------|------------|-----|
| `postgres` | Superusuário | Migrations (`makemigrations`, `migrate`) |
| `app_user` | SELECT, INSERT, UPDATE, DELETE | Runtime da aplicação |

> O script `db/init/01_app_user.sql` cria o `app_user` automaticamente na primeira inicialização.

### Criar migrations

```bash
sudo docker compose exec \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  backend python manage.py makemigrations
```

### Executar migrations

```bash
sudo docker compose exec \
  -e DB_USER=postgres -e DB_PASSWORD=postgres \
  backend python manage.py migrate
```

## Testes

```bash
# Todos os testes
sudo docker compose exec backend pytest -v

# Módulo específico
sudo docker compose exec backend pytest apps/core/tests/test_organizations.py -v

# Com cobertura (se instalado)
sudo docker compose exec backend pytest --cov=apps -v
```

## Seed de Dados

Popula estados, territórios, municípios e perfis base:

```bash
sudo docker compose exec \
  -e DB_USER=postgres -e DB_PASSWORD=postgres \
  backend python manage.py seed_core
```

## Variáveis de Ambiente

Referência completa em [`.env.example`](.env.example):

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `DJANGO_SECRET_KEY` | ✅ | Chave secreta do Django |
| `DEBUG` | — | `True` para desenvolvimento |
| `DB_NAME` | — | Nome do banco (padrão: `app_db`) |
| `DB_USER` | — | Usuário do banco (padrão: `app_user`) |
| `DB_PASSWORD` | — | Senha do banco |
| `DB_HOST` | — | Host do banco (padrão: `db`) |
| `REDIS_HOST` | — | Host do Redis (padrão: `redis`) |
| `CORS_ALLOWED_ORIGINS` | — | Origins permitidos (padrão: `http://localhost:3000`) |
