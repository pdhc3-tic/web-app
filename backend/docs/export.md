# Exportação do Plano de Trabalho e Integração Power BI

## Exportação de Respostas de Formulários da UPF

```http
GET /api/v1/sgp/upfs/{upf_pk}/formularios/exportar/?formato={csv|pdf}
```

Requer autenticação JWT e aplica o mesmo escopo territorial e os mesmos filtros da
listagem de formulários da UPF. Os parâmetros opcionais são `formulario_id`,
`data_inicio`, `data_fim` e `respondente`.

| Formato | Content-Type | Conteúdo |
|---|---|---|
| `csv` | `text/csv; charset=utf-8` | Uma linha por resposta, com ID, formulário, versão, data, respondente, status, origem e `respostas_json` serializado em JSON. |
| `pdf` | `application/pdf` | Uma seção por resposta, com metadados e as respostas renderizadas de forma estruturada (rótulo humanizado + valor por campo, grupos aninhados para objetos/listas de objetos e listas de valores simples exibidas em linha), seguindo as mesmas regras de apresentação da visualização completa (FE-17/BE-17). |

A partir da issue #205, o PDF não imprime mais `respostas_json` como JSON bruto:
`apps/sgp/services/form_response_render.py` percorre o dicionário recursivamente e
despacha por tipo de valor — `None`/ausente e listas ou objetos vazios viram "—";
booleano vira "Sim"/"Não"; lista cujos itens são todos primitivos vira uma linha
única com os valores separados por vírgula; lista contendo objetos vira um grupo
numerado ("Item 1", "Item 2", ...) com cada item renderizado recursivamente;
objeto não vazio vira uma subseção com o título derivado da chave; qualquer outro
valor é exibido como texto simples, sem formatação especial de data/moeda. Uma
resposta sem nenhum campo preenchido exibe a mensagem "Este formulário foi
submetido sem respostas registradas.", a mesma usada pelo modal de visualização
completa.

**Limitação conhecida e comportamento documentado**: o SGP ainda não persiste um
schema/definição versionada dos formulários do SGF (`apps/sgf` não possui modelos
hoje). Por isso, tanto o PDF quanto o modal FE-17 exibem as chaves de
`respostas_json` como rótulos **humanizados** (ex.: `renda_familiar` → "Renda
familiar"), e não como os rótulos reais de pergunta/opção definidos no formulário
original; campos de seleção mostram o valor armazenado, não um rótulo de opção
resolvido. `formulario_nome` e `formulario_versao` são sempre o snapshot gravado em
`FormResponse` no momento do preenchimento — nunca resolvidos dinamicamente a
partir de uma definição externa — portanto não existe hoje um cenário de
"definição da versão original indisponível" a tratar; isso fica pendente de uma
futura definição de schema versionado do SGF.

A ordem das seções/campos no PDF segue a ordem das chaves em `respostas_json`
conforme armazenada no banco (a mesma usada pela visualização completa). O
Postgres `jsonb` não garante preservar a ordem de inserção original do JSON
recebido, mas como as duas visualizações leem o mesmo valor persistido, elas
permanecem consistentes entre si.

A exportação em CSV não foi alterada por essa issue: `respostas_json` continua
embutido, serializado em JSON, na coluna "Respostas".

`formato` ausente ou diferente de `csv` e `pdf` retorna `400 Bad Request`.

## Exportação de Membros (Issue #186)

```http
GET /api/v1/sgp/upfs/{upf_pk}/membros/exportar/
GET /api/v1/sgp/membros/exportar/?territorio_id=&municipio=&projeto=
```

Requer autenticação JWT. A primeira rota exporta os membros de uma única UPF,
respeitando o mesmo escopo territorial de acesso à UPF (`upfs_acessiveis_ao_usuario`).
A segunda exporta membros de múltiplas UPFs dentro do escopo territorial do
usuário — um relatório demográfico agregado —, com os filtros opcionais
`territorio_id`, `municipio` e `projeto` (IDs inteiros).

Resposta: CSV UTF-8 com BOM (`text/csv; charset=utf-8`), uma linha por membro,
com `Content-Disposition: attachment`. Colunas: ID, UPF, nome completo,
parentesco, data de nascimento, idade, gênero, CPF, município, território e
projeto.

**Campos sensíveis.** As colunas `Cor/Raça` e `Condições de saúde` só aparecem
no CSV se o perfil do usuário autenticado tiver permissão de leitura sobre
esses campos (mesma matriz da Issue #187, `apps.core.sensitive_fields`).
Perfis sem permissão recebem o CSV **sem essas colunas** — nunca com valores
vazios ou mascarados, para não sugerir a um perfil sem permissão que o dado
existe.

**Limite da exportação agregada.** Restrita a
`apps.sgp.services.membro_export.MEMBROS_EXPORT_UPF_LIMIT` (500) UPFs por
exportação. Acima disso, a API responde `400 Bad Request` pedindo para
restringir por `territorio_id`, `municipio` ou `projeto`, em vez de truncar o
resultado silenciosamente — um relatório demográfico incompleto sem aviso
seria pior do que um erro explícito.

| Cenário | Status |
| :--- | :--- |
| JWT ausente ou inválido | `401 Unauthorized` |
| UPF fora do escopo do usuário (rota por UPF) | `404 Not Found` |
| `territorio_id`/`municipio`/`projeto` inválidos | `400 Bad Request` |
| Escopo territorial acima do limite de UPFs (rota agregada) | `400 Bad Request` |

## Exportação de Atividades

```http
GET /api/v1/sgp/atividades/exportar/?formato={csv|xlsx}&periodo_inicio=&periodo_fim=&territorio_id=&acao_id=
```

Download direto, no escopo territorial do usuário (mesma regra da listagem de
atividades). `periodo_inicio`/`periodo_fim` recortam por `data_inicio` da
atividade, e `periodo_inicio` posterior a `periodo_fim` retorna `400`. Colunas:
ID, título, tipo, status, data de início e de fim, estado, município, território,
comunidade, Meta, Ação, técnico responsável, UPFs participantes, participantes e
atrasada (mesma regra do campo `atrasada` da API). Dataset em
`apps/sgp/services/activity_export.py`.

## Exportação de UPFs

```http
GET /api/v1/upfs/exportar/?formato={csv|xlsx}&<filtros da listagem>
```

Aceita **exatamente** os filtros de `GET /api/v1/upfs/` (os declarados em
`UPFFilter`: `q`, `municipio`, `territorio`, `projeto`, `comunidade`, `ativo`,
`cadastrado_de`, `cadastrado_ate`), com o mesmo padrão de só UPFs ativas quando
`ativo` não é informado. `ativa` é aceito como sinônimo de `ativo` (ver
"Débito técnico" abaixo); se os dois vierem, vale `ativo`. Qualquer outro
parâmetro retorna `400` com `{"code": "parametro_desconhecido", "parametros": [...]}`
— o django-filter ignoraria o parâmetro e o arquivo sairia com a base inteira.

Colunas: Estado, Município, Território, Comunidade, Titular, CPF e Data de
cadastro. O CPF sai completo para Super Admin e UGP e mascarado
(`123.***.***-45`) para os demais perfis (`CPF_COMPLETO_ROLES` em
`apps/core/sensitive_fields.py`). Saúde e Cor/Raça não fazem parte do arquivo.

Até `UPF_EXPORT_SYNC_LIMIT` (1.000) registros a resposta é o arquivo. Acima
disso a API cria uma exportação assíncrona e responde `202` com o mesmo corpo de
`GET /api/v1/sgp/exportacoes/{id}/`.

## Exportação assíncrona

```http
POST /api/v1/sgp/exportacoes/              {"tipo": "plano_trabalho|atividades|upfs", "formato": "csv|xlsx", "filtros": {...}}
GET  /api/v1/sgp/exportacoes/{id}/
GET  /api/v1/sgp/exportacoes/{id}/download/
POST /api/v1/sgp/exportacoes/{id}/repetir/
```

`filtros` aceita os mesmos parâmetros da rota síncrona de cada tipo, validados
na criação. O `POST` responde `202` com `{id, status: "pendente", ...}` e a task
`sgp.tasks.processar_exportacao` gera o arquivo no worker, no escopo do
solicitante no momento da execução. O status passa por
`pendente → processando → concluida | erro`, com `progresso` de 0 a 100 e `erro`
preenchido quando falha.

| Situação | Resposta |
| :--- | :--- |
| Exportação de outro usuário | `404 Not Found` |
| `download` antes de concluir | `409` com `code: exportacao_nao_concluida` e o `status` atual |
| `download` depois de expirar | `410` com `code: exportacao_expirada` |
| `repetir` fora do status `erro` | `409` com `code: exportacao_nao_repetivel` |

O arquivo gerado fica no próprio registro (`ExportJob.conteudo`) e vale 24 h:
backend e worker rodam em containers que não compartilham disco, então gravar em
`MEDIA_ROOT` deixaria o download sem acesso ao arquivo. A task
`sgp.tasks.limpar_exportacoes_expiradas` (Celery Beat, a cada hora) apaga as
exportações expiradas e as que ficaram mais de 7 dias sem gerar arquivo.

### Débito técnico

| Item | Situação | Saída |
| :--- | :--- | :--- |
| Alias `ativa` → `ativo` em `GET /api/v1/upfs/exportar/` e no `filtros` de `tipo=upfs` | O campo da UPF foi renomeado de `ativa` para `ativo` (migration `0031_upf_ativa_para_ativo`), mas o front (`frontend/app/lib/upfs.ts`, `buildUpfsFilterParams`) ainda envia `ativa`, na exportação e na listagem. Na listagem o parâmetro é ignorado em silêncio e vale o padrão de só ativas, então as opções "inativas" e "todas" da tela não têm efeito. | O front passa a enviar `ativo`; depois disso, remover `ALIASES_DE_FILTRO` de `apps/sgp/services/upf_export.py` e os testes `test_ativa_e_aceito_como_sinonimo_de_ativo` e `test_ativo_prevalece_sobre_ativa`. |

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
