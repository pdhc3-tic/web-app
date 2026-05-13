# Backend (Django) com Docker

## Pré-requisitos

- Docker
- Docker Compose

## 1. Preparar ambiente

Na raiz do monorepo:

```bash
cp -n backend/.env.example backend/.env
cp -n frontend/.env.example frontend/.env.local
```

Preencha os obrigatórios:

- `backend/.env`: `DJANGO_SECRET_KEY`
- `frontend/.env.local`: `AUTH_SECRET`
- mantenha `NEXT_PUBLIC_API_URL=http://backend:8000` no frontend

## 2. Subir stack do zero

```bash
docker compose -f Docker-compose.yml down -v
docker compose -f Docker-compose.yml up --build -d
```

## 3. Migrations (recomendado)

O backend roda com usuário de app limitado (`app_user`, sem CREATE/DROP).  
Por isso, rode migrations com override temporário para `postgres`:

```bash
docker compose -f Docker-compose.yml exec \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  backend python manage.py migrate
```

Se necessário:

```bash
docker compose -f Docker-compose.yml exec \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  backend python manage.py makemigrations
```

## 4. Validar backend

```bash
docker compose -f Docker-compose.yml ps
curl -i http://localhost:8000/admin/login/
curl -i http://localhost:8000/api/v1/
```

## 5. Logs e parada

```bash
docker compose -f Docker-compose.yml logs -f backend db redis
docker compose -f Docker-compose.yml down
```
## 6. Rodar testes do backend

```bash
docker exec -it backend pytest -v
```