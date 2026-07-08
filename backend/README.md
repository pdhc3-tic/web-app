# Backend — Django REST Framework

API REST do PDHC construída com Django 6, Django REST Framework e Celery.

## Documentação

- [Swagger / OpenAPI](#swagger--openapi)
- [Throttling da API](docs/throttling.md)
- [Política de Logging](docs/logging.md)

## Swagger / OpenAPI

A documentação da API é gerada automaticamente com [drf-spectacular](https://drf-spectacular.readthedocs.io/).

### Acesso

Com o backend rodando em `localhost:8000`:

| URL | Descrição |
|-----|-----------|
| `http://localhost:8000/api/docs/swagger/` | Swagger UI (interativo) |
| `http://localhost:8000/api/docs/redoc/`   | Redoc (visualização estática) |
| `http://localhost:8000/api/docs/schema/`  | Schema OpenAPI cru (YAML) |

```bash
curl -s http://localhost:8000/api/docs/schema/ | head -30
```

### Como manter

Views que usam **ViewSet** com `serializer_class` e `queryset` são documentadas automaticamente — nenhuma ação necessária.

Views que **não** seguem esse padrão precisam de `@extend_schema`:

```python
from drf_spectacular.utils import extend_schema

@extend_schema(
    summary="Listar notificações do usuário",
    responses=NotificationSerializer(many=True),
)
class NotificationListView(ListAPIView):
    ...
```

Para views baseadas em função (`@api_view`):

```python
@extend_schema(
    request=LoginSerializer,
    responses={200: TokenResponseSerializer},
)
@api_view(["POST"])
def login_view(request):
    ...
```

Se um campo precisa de descrição extra no schema:

```python
class MeuSerializer(serializers.Serializer):
    campo = serializers.CharField(help_text="Descrição que aparece no Swagger")
```

> Comece adicionando `@extend_schema` nas function-based views de `apps/core/views.py` (login, logout, me, password-reset).

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
