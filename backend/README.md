# Backend — Django REST Framework

API REST do PDHC construída com Django 6, Django REST Framework e Celery.

## Documentação

- [Swagger / OpenAPI](#swagger--openapi)
- [Throttling da API](docs/throttling.md)
- [Política de Logging](docs/logging.md)
- [Storage Cloudflare R2](docs/storage-setup.md)
- [Integração Google Calendar](docs/google-calendar.md)
- [Exportação CSV/XSLX e PowerBI](docs/export.md)

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

Popula projetos base do SGP:

```bash
sudo docker compose exec \
  -e DB_USER=postgres -e DB_PASSWORD=postgres \
  backend python manage.py seed_sgp
```

Os catálogos de culturas e espécies animais do SGP são populados automaticamente
por data migration ao executar `python manage.py migrate`.

Em produção, os XLSX legados ficam em um diretório separado da aplicação na
VPS, configurado pela variável `SEED_DATA_DIR`. O deploy não monta os XLSX no
backend permanente. Em um container temporário, ele prepara um pacote privado
e determinístico (JSONL + `manifest.json` + `report.json`) e depois importa
somente esse pacote:

```bash
sudo docker compose -f docker-compose.prod.yml run --rm --no-deps \
  -v "$SEED_DATA_DIR:/seed-data:ro" \
  -v "$SEED_PACKAGE_DIR:/seed-package" \
  backend python manage.py prepare_seed \
  --source-dir /seed-data --output-dir /seed-package

sudo docker compose -f docker-compose.prod.yml run --rm --no-deps \
  -v "$SEED_PACKAGE_DIR:/seed-package:ro" \
  backend python manage.py seed_prod --package-dir /seed-package
```

O diretório dos XLSX deve ter permissões restritas e o pacote deve ficar fora do
checkout. O manifesto valida SHA-256 antes da importação. O comando é
idempotente, mantém o vínculo entre ID legado e objeto atual em
`SeedImportRecord`, e nunca apaga registros que estejam ausentes no pacote:
essas diferenças são apenas relatadas. Planilhas sem mapeamento direto e linhas
inválidas ficam em `report.json`.

Para validar localmente sem persistir:

```bash
SEED_DATA_DIR="$(realpath ../dados_seed)"
SEED_PACKAGE_DIR=/tmp/pdhc-seed-package
rm -rf "$SEED_PACKAGE_DIR" && mkdir -p "$SEED_PACKAGE_DIR"

docker compose run --rm --no-deps \
  -v "$SEED_DATA_DIR:/seed-data:ro" \
  -v "$SEED_PACKAGE_DIR:/seed-package" \
  backend python manage.py prepare_seed \
  --source-dir /seed-data --output-dir /seed-package
docker compose run --rm --no-deps \
  -v "$SEED_PACKAGE_DIR:/seed-package:ro" \
  backend python manage.py seed_prod \
  --package-dir /seed-package --dry-run
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
| `STORAGE_BACKEND` | — | `local` em desenvolvimento ou `r2` em produção |
| `MEDIA_URL` | — | Prefixo público do storage local |
| `MEDIA_ROOT` | — | Diretório usado pelo storage local |
| `R2_ACCESS_KEY_ID` | Quando `r2` | Access Key ID do Cloudflare R2 |
| `R2_SECRET_ACCESS_KEY` | Quando `r2` | Secret Access Key do Cloudflare R2 |
| `R2_BUCKET_NAME` | Quando `r2` | Nome do bucket R2 |
| `R2_ENDPOINT_URL` | Quando `r2` | Endpoint S3-compatible da conta R2 |
| `R2_PUBLIC_URL` | Quando `r2` | Domínio público/CNAME do bucket |
| `SEED_DATA_DIR` | Produção | Diretório privado com os XLSX legados |
| `SEED_PACKAGE_DIR` | — | Diretório privado do pacote normalizado |

## Storage De Arquivos

O upload de foto da UPF usa URL presignada para evitar que o backend receba o arquivo como proxy. Consulte [docs/storage-setup.md](docs/storage-setup.md) para criação do bucket, credenciais R2 e CORS.
