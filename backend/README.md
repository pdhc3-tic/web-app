# Backend — Django REST Framework

API REST do PDHC construída com Django 6, Django REST Framework e Celery.

## Documentação

- [Swagger / OpenAPI](#swagger--openapi)
- [Throttling da API](docs/throttling.md)
- [Política de Logging](docs/logging.md)
- [Storage Cloudflare R2](docs/storage-setup.md)
- [Integração Google Calendar](docs/google-calendar.md)
- [Exportação CSV/XSLX e PowerBI](docs/export.md)
- [Decisões de modelo de dados vs. requisitos](docs/decisoes-modelo-dados.md)

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

O schema só é útil para gerar tipos se descrever o que a view devolve de fato. O drf-spectacular não avisa nestes casos, e o tipo sai errado:

- **`SerializerMethodField`** sem type hint de retorno (`-> int | None`) ou `@extend_schema_field` sai como `string`.
- **`to_representation` sobrescrito** troca a forma da resposta sem o schema saber. Declare um serializer de resposta e use-o no `@extend_schema` (ex.: `UPFDetailRespostaSerializer`).
- **`@action`** herda o `serializer_class`, os filtros e a paginação do viewset. Declare `request`/`responses`, `filters=False` quando os filtros da listagem não se aplicam e `pagination_class=None` (ou o paginador real) no `@action` quando a lista não usa o do viewset.
- **`get_queryset`** que depende do usuário quebra na geração, que não tem usuário: devolva `Model.objects.none()` quando `getattr(self, "swagger_fake_view", False)`.

### Schema versionado (`schema.yml`)

O frontend gera os tipos da API a partir de `backend/schema.yml`. Por isso o arquivo é versionado e precisa estar sempre igual ao que o código gera.

> **Regra:** todo PR que muda request ou resposta de alguma rota (serializer, view, `@extend_schema`, filtro, paginação, choices) regenera o `schema.yml` e commita o arquivo junto, no mesmo PR.

```bash
sudo docker compose exec backend python manage.py spectacular --file schema.yml
```

Em conflito de merge no `schema.yml`, não resolva à mão: termine o merge do código e rode o comando acima de novo.

### Workflow `Schema OpenAPI` (gate no PR)

O workflow `.github/workflows/openapi-schema.yml` roda em todo PR para a `main` que toca `backend/`. Ele aparece no PR como **"Schema OpenAPI atualizado"** e executa só `apps/core/tests/test_openapi_schema.py`, sem banco nem Redis.

O check falha quando:

| Situação | Mensagem do teste | Como resolver |
|---|---|---|
| `schema.yml` commitado difere do gerado pelo código | `schema.yml desatualizado` | Regenerar com o comando acima e commitar |
| A geração emite warning ou erro em código fora do débito conhecido de SGD e SCA | Lista dos warnings novos | Corrigir a view ou o serializer (ver [Como manter](#como-manter)) |
| Um tipo que o frontend depende saiu errado (ex.: município sem `estado`) | `assert` do teste específico | Corrigir o schema da rota, não o teste |

O workflow é separado do `deploy.yml` de propósito. O pytest do deploy só roda no push para a `main`, ou seja, depois do merge, e um schema desatualizado travaria o deploy de produção. Aqui ele barra o PR antes do merge, com um nome próprio que deixa claro o que falhou.

O débito de SGD e SCA está listado em `FONTES_COM_DEBITO`, no teste. Ao zerar os warnings de um desses apps, tire-o da lista para que ele passe a ser cobrado também.

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

### Política de migrations

- Uma migration por issue, gerada com `makemigrations` sobre a `main` atualizada. Nada de migration de merge: quando duas branches criam migrations no mesmo app, a que entra depois faz rebase e renumera a sua.
- Branch curta e rebase obrigatório antes do merge. Com PRs empilhados, o rebase é feito sobre a branch de baixo e a numeração acompanha a ordem de entrada.
- `makemigrations --check --dry-run` roda no CI (`.github/workflows/deploy.yml`) e no `pytest` (`test_migrations_dados_iniciais.py`): model alterado sem migration derruba o build.
- Dados iniciais (catálogos, rubricas, Indicadores) ficam em data migration idempotente (`get_or_create`/`update_or_create`), que não sobrescreve o que a UGP ajustou.
- O histórico do `sgp` foi recriado em `0001_initial` (schema) e `0002_seed_dados_iniciais` (dados). Um banco de desenvolvimento criado antes disso, com o `sgp` em qualquer estado, precisa ser recriado (`docker compose down -v` e `migrate`); um banco que já estava com o schema completo aceita `migrate` direto.

## Testes

```bash
# Todos os testes
sudo docker compose exec backend pytest -v

# Módulo específico
sudo docker compose exec backend pytest apps/core/tests/test_organizations.py -v

# Com cobertura (se instalado)
sudo docker compose exec backend pytest --cov=apps -v

# Sem os testes de performance, só nesta execução
sudo docker compose exec -e SKIP_PERFORMANCE_TESTS=1 backend pytest -v

# Só os testes de performance
sudo docker compose exec backend pytest -m performance -v
```

Testes que medem tempo de resposta (e o de contagem de queries do painel de orçamento, que é intermitente) levam `@pytest.mark.performance`. Com `SKIP_PERFORMANCE_TESTS=1` eles são pulados e aparecem como `SKIPPED` no `-v`. O workflow de deploy roda assim, porque esses limites oscilam no runner compartilhado do GitHub. Para pular sempre no ambiente local, coloque `SKIP_PERFORMANCE_TESTS=1` no `backend/.env` e recrie o container (`sudo docker compose up -d backend`).

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

Os catálogos de culturas e espécies animais, as rubricas orçamentárias e o catálogo
inicial de Indicadores do SGP são populados automaticamente por data migration ao
executar `python manage.py migrate`.

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
| `FIELD_ENCRYPTION_KEY` | ✅ | Chave AES-256 (base64 de 32 bytes) para criptografia em repouso de campos sensíveis (`saude`, `cor_raca` de `MembroFamilia`) — gere com `openssl rand -base64 32`. Ver [`apps/core/crypto.py`](apps/core/crypto.py) |
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
