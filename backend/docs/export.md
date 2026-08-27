# Exportação do Plano de Trabalho e Integração Power BI

## 1. Resumo

Foram implementadas a exportação do Plano de Trabalho em CSV/XLSX e uma API autenticada para consumo consolidado pelo Power BI. A solução aplica filtros e regras de escopo territorial na exportação, além de manter um snapshot em Redis atualizado periodicamente pelo Celery para reduzir o custo de leitura do conector BI.

## 2. Arquivos Modificados/Criados

| Arquivo | Alteração / Responsabilidade |
|---|---|
| `backend/apps/sgp/services/workplan_export.py` | Criado. Centraliza a montagem do dataset plano de Metas e Ações, filtros, RLS territorial, indicadores e colunas comuns a CSV, XLSX e Power BI. |
| `backend/apps/sgp/views/workplan.py` | Adiciona as views `WorkPlanExportView` e `WorkPlanPowerBIView`; gera respostas de download e expõe o snapshot para o Power BI. |
| `backend/apps/sgp/urls.py` | Registra as rotas de exportação do Plano de Trabalho e integração Power BI. |
| `backend/apps/sgp/serializers_workplan.py` | Adiciona `WorkPlanExportQuerySerializer` para validar formato e filtros de exportação. |
| `backend/apps/sgp/tasks.py` | Adiciona a tarefa Celery `export_to_power_bi` e a função compartilhada de atualização do snapshot. |
| `backend/apps/sgp/cache.py` | Adiciona chaves e helpers de Redis para leitura e escrita do snapshot Power BI. |
| `backend/apps/core/authentication.py` | Criado. Implementa autenticação exclusiva do Power BI via `Authorization: Token <token>`. |
| `backend/apps/core/throttling.py` | Adiciona `PowerBIServiceTokenThrottle`, limitado por identidade do token de serviço. |
| `backend/setup/settings.py` | Configura token/rate limit do Power BI, taxa DRF e agendamento horário do Celery Beat. |
| `backend/.env.example` | Documenta `POWER_BI_SERVICE_TOKEN` e `POWER_BI_RATE_LIMIT`. |
| `backend/requirements/base.txt` | Adiciona `openpyxl==3.1.5` para geração de arquivos XLSX. |
| `backend/apps/sgp/tests/test_workplan_exports.py` | Criado. Contém testes de exportação, filtros, RLS, Power BI, cache, autenticação, agendamento e desempenho. |

## 3. Arquitetura e Fluxo da Solução

### Dataset centralizado

O módulo `apps/sgp/services/workplan_export.py` é a fonte única do dataset exportável. Ele evita duplicação entre exportação manual e Power BI, retornando as colunas:

1. Meta
2. Ação
3. Tipo/Unidade
4. Quantidade planejada
5. Valor unitário
6. Valor total
7. Quantidade realizada
8. Percentual realizado
9. Status de execução
10. Semáforo

A consulta usa `select_related`, agregação com `Count`, filtros SQL e `Exists` para evitar consultas N+1 e preservar desempenho.

### Regras de escopo territorial

A exportação manual recebe o usuário JWT autenticado e aplica as mesmas regras de visibilidade do Plano de Trabalho:

| Perfil | Visibilidade |
|---|---|
| `super-admin` / `ugp` | Todas as Ações e atividades. |
| `articulador-estadual` | Ações com atividades em estados associados ao usuário. |
| `adt-acr` | Ações com atividades em territórios associados ao usuário. |
| Outros perfis | Acesso negado. |

A restrição é aplicada antes da agregação de atividades. Portanto, quando uma Ação possui atividades em vários territórios, o usuário vê somente a quantidade realizada dentro do território permitido.

### Exportação manual

A `WorkPlanExportView` valida os parâmetros, obtém as linhas pelo serviço compartilhado e gera:

- CSV UTF-8 com BOM, melhorando a abertura no Microsoft Excel.
- XLSX com `openpyxl` no modo `write_only=True`, reduzindo consumo de memória para datasets maiores.
- Nome de arquivo com data e hora da geração.

### Power BI

O endpoint Power BI possui autenticação própria, sem aceitar JWT de usuário:

1. O cliente envia `Authorization: Token <service_token>`.
2. `PowerBIServiceTokenAuthentication` compara o token recebido com `POWER_BI_SERVICE_TOKEN` usando `secrets.compare_digest`.
3. A API aplica limite de requisições por token.
4. A resposta é obtida do Redis.
5. Caso o Redis não possua snapshot, a primeira chamada recompõe o snapshot.
6. O Celery Beat atualiza o snapshot no início de cada hora.

### Padrões adotados

- Mudanças pequenas e isoladas por responsabilidade.
- Serviço reutilizável para consultas e transformação de dados.
- Configuração por variáveis de ambiente, sem segredos no código.
- Autenticação dedicada para integração máquina-a-máquina.
- Testes automatizados com `pytest`, factories existentes e cache local de testes.
- Uso de `HttpResponse` nativo para downloads de arquivos.

### Bibliotecas e APIs

| Biblioteca | Uso aplicado |
|---|---|
| Django 6 | `HttpResponse`, `Content-Disposition`, framework de cache Redis. |
| Django REST Framework 3.17 | `APIView`, `BaseAuthentication`, `SimpleRateThrottle`, permissões e validação de query params. |
| Celery 5.6 | `@shared_task` e agendamento periódico por `CELERY_BEAT_SCHEDULE`. |
| openpyxl | Criação de arquivos XLSX em modo `write_only`. |

## 4. Especificação de APIs / Endpoints

### 4.1 Exportar Plano de Trabalho

```http
GET /api/v1/sgp/plano-trabalho/exportar/
```
### Autenticação
Authorization: Bearer <jwt_usuario>

### Query parameters

| Parâmetro	| Obrigatório	| Tipo	| Descrição |
|  :---|:---| :--- | :--- |
| ```formato```	| Sim	| ```csv``` ou ```xlsx```	| Formato do arquivo gerado. |
| ```meta_id```	| Não	| inteiro positivo	| Filtra por Meta. |
| ```territorio_id```	| Não	| inteiro positivo	| Filtra por território. |
| ```periodo_inicio```	| Não	| ```YYYY-MM-DD```	| Data inicial do período. |
| ```periodo_fim```	| Não	| ```YYYY-MM-DD```	| Data final do período. |

Não há body para esta requisição.

### Exemplo CSV
```http 
GET /api/v1/sgp/plano-trabalho/exportar/?formato=csv&meta_id=1&periodo_inicio=2026-01-01&periodo_fim=2026-12-31
```
Authorization: Bearer <jwt_usuario>

### Exemplo XLSX
```http
GET /api/v1/sgp/plano-trabalho/exportar/?formato=xlsx
```
Authorization: Bearer <jwt_usuario>

### Resposta de sucesso

| Formato | Status | Content-Type |
| :---    | :---  | :---         |
| ```CSV```	| ```200 OK```	| ```text/csv; charset=utf-8``` |
| ```XLSX```|	```200 OK```	| ```application/vnd. openxmlformats-officedocument.spreadsheetml.sheet``` |

Exemplo de header de download:
```http 
Content-Disposition: attachment filename="plano_trabalho_2026-08-21_14-30-00.csv"
```
### Respostas de erro

| Cenário	| Status |
| :--- | :--- |
| JWT ausente ou inválido	| ```401 Unauthorized``` |
| Usuário sem permissão para o Plano de Trabalho	| ```403 Forbidden``` |
| ```formato``` ausente ou inválido	| ```400 Bad Request``` |
| ```meta_id``` ou ```territorio_id``` inválidos	| ```400 Bad Request``` |
| ```periodo_inicio``` posterior a ```periodo_fim```	| ```400 Bad Request``` |

### Exemplo:
```json
{
  "formato": [
    "\"pdf\" is not a valid choice."
  ]
}
```

> **Atenção:** como a resposta de exportação usa `HttpResponse` nativo, clientes devem omitir o header `Accept` ou usar `Accept: */*`. O envio explícito de `Accept: text/csv` pode resultar em `406 Not Acceptable` pela negociação padrão de renderers do DRF.

### 4.2 Dataset Power BI
```http
GET /api/v1/sgp/plano-trabalho/powerbi/
```
### Autenticação
```http
Authorization: Token <POWER_BI_SERVICE_TOKEN>
```
Não há body ou parâmetros de query.

### Resposta de sucesso
```json
Status: 200 OK
```
```json
{
  "atualizado_em": "2026-08-21T14:00:00-03:00",
  "resultados": [
    {
      "meta": "1 - Meta de exemplo",
      "acao": "1.1 - Ação de exemplo",
      "tipo_unidade": "Seminário",
      "quantidade_planejada": "16.00",
      "valor_unitario": "8175.00",
      "valor_total": "130800.00",
      "quantidade_realizada": "4",
      "percentual_realizado": "25.00",
      "status_execucao": "no_prazo",
      "semaforo": "amarelo"
    }
  ]
}
```
### Respostas de erro
| Cenário	| Status |
| :--- | :--- |
| Header ```Authorization``` ausente	| ```401 Unauthorized``` |
| Token inválido	| ```401 Unauthorized``` |
| JWT enviado no formato ```Bearer```	| ```401 Unauthorized``` |
| Mais de 100 requisições por hora no mesmo token	| ```429 Too Many Requests``` |
<br>

# 5. Instruções para Testes
### Variáveis de ambiente
Adicione ao arquivo ```backend/.env```:
```http
POWER_BI_SERVICE_TOKEN=gere-um-token-longo-e-aleatorio
POWER_BI_RATE_LIMIT=100/hour
```
Exemplo para gerar um token:
```python
openssl rand -hex 32
```
O valor configurado em ```POWER_BI_SERVICE_TOKEN``` deve ser usado pelo cliente Power BI ou Insomnia: <br>
```http
Authorization: Token <valor-gerado>
```

### Instalar dependências e reconstruir backend
```http
docker compose up --build -d backend
```
A reconstrução é necessária para instalar ```openpyxl```.

### Executar migrations
```python
docker compose exec \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  backend python manage.py migrate
```

### Executar testes automatizados
```http
docker compose exec backend pytest apps/sgp/tests/test_workplan_exports.py -q
```
Para executar todos os testes do módulo SGP:
```http
docker compose exec backend pytest apps/sgp/tests -q
```
### Executar Celery e Celery Beat
A atualização horária depende de ambos os serviços:
```http
docker compose up -d celery_worker celery_beat
```
A tarefa registrada é:
```sgp.tasks.export_to_power_bi``` <br>
Ela é executada no minuto ```0``` de cada hora.

### Validar manualmente o snapshot
No Django shell:
```shell
docker compose exec backend python manage.py shell
from apps.sgp.tasks import export_to_power_bi

snapshot = export_to_power_bi()
print(snapshot["atualizado_em"])
print(len(snapshot["resultados"]))
```

### Validar com Insomnia
1. Obtenha um JWT por ```POST /api/v1/auth/login/```.
2. Execute a exportação CSV/XLSX com ```Authorization: Bearer <jwt>```.
3. Remova o header ```Accept``` ou use ```Accept: */*``` nos downloads.
4. Execute o endpoint Power BI com ```Authorization: Token <service_token>```.
5. Teste token ausente, token inválido e JWT enviado como ```Bearer```.
6. Use um usuário ```adt-acr``` com território A e confirme que o CSV não contém dados do território B.