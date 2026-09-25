# Pendências de backend — sprint 10

*Compilado em 23/09/2026, na branch `frontend/sprint-10b`, ao concluir as
pendências de frontend da issue #240 (exportação da listagem de UPFs) apontadas
na revisão do PR #261.*

*Os itens 4 e 5 foram acrescentados em 25/09/2026, ao avaliar se as issues #272
e #273 podiam ser atendidas depois do merge do PR #300. Nenhuma das duas pode:
as duas dependem de trabalho de backend antes de qualquer entrega que feche a
issue.*

*Os itens 6 a 10 foram acrescentados em 25/09/2026, ao implementar a issue #294
(aba "Demandas" na ficha da Atividade e criação de demanda), contra o backend
do SGD que entrou pelo PR #300. O frontend foi feito chamando a API no formato
correto; o que o backend ainda não atende está abaixo, e nada foi contornado no
cliente.*

*O documento da sprint anterior (`pendencias-backend-sprint-9.md`) continua
valendo para o que está lá — os itens dele **não foram reavaliados** nesta
compilação.*

---

## 1. `GET /api/v1/upfs/exportar/` não existe — bloqueia a #240 inteira

*Estado atual:* a rota cai no `retrieve` do `UPFViewSet` com `pk="exportar"`:

```
GET /api/v1/upfs/exportar/?formato=csv   → 404 {"detail":"Não encontrado."}
```

O `UPFViewSet` (`backend/apps/sgp/views/upf.py`) tem só as actions `mapa`,
`foto` e `historico`. O frontend está completo e testado contra respostas
simuladas: o botão "Exportar" da listagem manda os mesmos parâmetros da
listagem (gerados por `buildUpfsFilterParams`, fonte única para as duas
chamadas) e reage à resposta. Enquanto a rota não existir, o clique mostra o
toast "Não encontrado." — nada quebra, mas nenhum critério da issue é
verificável.

**Contrato que o frontend espera** (documentado em `frontend/app/lib/upfs.ts`,
seção "Exportação da listagem"):

```
GET /api/v1/upfs/exportar/?<filtros da listagem>&formato=csv
  200 text/csv          → até 1.000 registros: o arquivo direto
  202 application/json  → acima de 1.000: tarefa criada
                          {id, status, total, progresso, erro, arquivo_nome}
  400 {message}         → parâmetro desconhecido ou inválido

GET /api/v1/upfs/exportar/{id}/          → a tarefa, mesmo formato do 202
                                           status: pendente | processando | concluida | falhou
                                           progresso: 0–100 ou null
GET /api/v1/upfs/exportar/{id}/arquivo/  → o CSV da tarefa concluída
```

Quem decide entre síncrono e assíncrono é o **servidor**, que conhece o total
real no escopo do usuário — a tela não usa a contagem dela para escolher. Assim
o limite de 1.000 vale também para quem chamar a API direto. Um `404` no
polling é tratado como tarefa expirada ("gere o arquivo novamente").

Se preferirem outro formato, o ajuste no frontend é localizado
(`iniciarExportacaoUpfs`, `fetchExportacaoUpfs`, `baixarExportacaoUpfs`) — só
avisem antes, porque os E2E simulam exatamente o formato acima.

**Pedido**, pelos critérios da issue e pela revisão do PR #261:

- **Mesmos filtros da listagem.** Action `exportar` no `UPFViewSet`
  reaproveitando `self.filter_queryset(self.get_queryset())`, para herdar de
  graça o `UPFFilter` (`q`, `municipio`, `territorio`, `projeto`, `ativo`,
  `cadastrado_de`, `cadastrado_ate`), o default `ativo=True` do
  `filter_queryset` e o escopo de `upfs_acessiveis_ao_usuario`. Duplicar os
  filtros num serviço à parte é o que faria arquivo e tela divergirem.
- **Recusar parâmetro desconhecido com 400.** Hoje o django-filter descarta em
  silêncio — verificado nesta compilação:

  ```
  GET /api/v1/upfs/?limit=1            → count 38
  GET /api/v1/upfs/?limit=1&bairro=x   → count 38, 200
  ```

  Na listagem isso é inofensivo; numa exportação significa entregar a base
  inteira a quem pediu um recorte. É a mesma classe de risco registrada no
  item 6 da sprint 8.
- **Colunas:** Estado, Município, Território, Comunidade, titular, CPF e data
  de cadastro.
- **CPF e campos sensíveis** com a mesma regra das #187/#192, aplicada **no
  servidor**: esconder só na tela não protege um arquivo baixado.
- **Tarefa assíncrona** acima de 1.000 registros (Celery), guardando o arquivo
  gerado para o download posterior. A #239 pede o mesmo fluxo para a exportação
  consolidada de atividades — vale desenhar uma infraestrutura só para as duas.
- **Testes** em `apps/sgp/tests/test_upf_export.py`, conforme a tabela da
  issue: filtros aplicados, escopo territorial (ADT exporta só o seu), CPF
  mascarado por perfil e exportação grande assíncrona.

*Referência de padrão:* `services/workplan_export.py` e
`services/membro_export.py` — este último já tem um limite
(`MEMBROS_EXPORT_UPF_LIMIT`) e a exceção `ExportLimitExceeded`.

*Estado atual no frontend:* entregue no commit `ad9be91`. Fluxo síncrono e
assíncrono, faixa de progresso, conclusão, falha, download posterior que
sobrevive a reload e "Tentar novamente" com os filtros originais. 11 E2E em
`e2e/exportacao-upfs.spec.ts`, todos com o endpoint simulado. Quando a rota
existir, o teste de igualdade de filtros passa a valer contra o servidor real
sem mudança; os demais continuam necessários para os estados raros (falha,
expiração).

---

## 2. `CORS_EXPOSE_HEADERS` continua faltando — agora também na #240

*Item 7 da sprint 9, ainda aberto:* `backend/setup/settings.py:273` configura
`CORS_ALLOWED_ORIGINS`, mas não `CORS_EXPOSE_HEADERS`. Sem ele o navegador não
deixa o JavaScript ler o `Content-Disposition`, e o nome de arquivo que o
backend escolher é descartado.

A exportação de UPFs entra na mesma lista da do Plano de Trabalho e da de
membros: sem o header, o arquivo sai com o nome derivado no cliente
(`upfs_AAAA-MM-DD.csv`). Para o download de uma tarefa concluída o frontend
ainda usa o `arquivo_nome` da tarefa, então ali o efeito some.

**Pedido** — o mesmo da sprint 9, uma linha:

```python
CORS_EXPOSE_HEADERS = ["Content-Disposition"]
```

---

## 3. `seed_demo` não permite testar o caso "acima de 1.000"

O banco de demonstração tem **41 UPFs** (38 ativas). O critério "exportação
acima de 1.000 registros é assíncrona" não é reproduzível à mão em nenhum
ambiente que parta do seed.

Não é pedido de seed com mil famílias — isso pesaria em toda execução do CI.
**Pedido:** tornar o limite configurável (ex.: `UPF_EXPORT_ASYNC_THRESHOLD` em
`settings`, default 1.000), para que homologação e o teste manual possam
baixá-lo e exercitar o fluxo assíncrono com o seed atual.

---

## 4. `/api/v1/choices/` não publica metade das listas — bloqueia a #272

*Estado atual:* `SGPChoicesView` (`backend/apps/sgp/views/choices.py`) não mudou
desde o PR #288, em que o bloqueio já foi descrito. `constants.py` está igual
desde 26/08/2026.

A #272 pede que nenhuma lista de opções que exista no backend continue escrita
à mão no frontend, e que todos os formulários — inclusive `ProducaoSlideOver` e
os filtros — consumam o endpoint. Hoje ele entrega assim:

| Situação | Listas |
|---|---|
| Publicadas com rótulo | `genero`, `cor_raca`, `escolaridade`, `dispositivo`, `pct`, `posse_terra`, `situacao_moradia`, `tipo_moradia`, `material_construcao`, `energia`, `agua`, `grau_parentesco` |
| Publicada sem rótulo | `saude` — sai `{"value": v, "label": v}`, porque `SAUDE_CHOICES` é lista plana de strings; a tela mostraria `deficiencia_visual` em vez de "Deficiência visual" |
| Existem no backend, fora do endpoint | `SEGURIDADE_SOCIAL_CHOICES` (`constants.py`); `TIPO_ATIVIDADE_CHOICES`, `FORMA_ATUACAO_CHOICES`, `AMBITO_CHOICES`, `STATUS_CHOICES` (`models/activity.py`); `TIPO_CHOICES`, `SISTEMA_CRIACAO_CHOICES`, `TIPO_OUTRA_CHOICES` (`models/production.py`); `ODS_CHOICES` (`constants.py`); os `TIPO_CHOICES` de `upf_document.py` e `activity_document.py` |

O wizard de UPF já consome o endpoint. As 12 listas publicadas ainda têm cópia
local em `frontend/app/lib/choices.ts`, mas só como reserva para falha de rede;
as que o frontend usa **sem** alternativa no endpoint são as da terceira linha
da tabela, mais `SAUDE_OPTIONS`.

**Pedido:**

1. `SAUDE_CHOICES` e `SEGURIDADE_SOCIAL_CHOICES` como tuplas `(value, label)`
   em `constants.py`, no mesmo formato de `GENERO_CHOICES`.
2. `SGPChoicesView` publicando `saude` e `seguridade_social` pelas tuplas, e
   também as listas de atividade, produção, ODS e tipos de documento.
3. O teste de contrato que a própria issue pede
   (`test_choices_expoe_todas_as_constantes`): hoje `test_choices.py` confere
   uma lista de chaves escrita à mão, então uma constante nova que não entre no
   endpoint passa sem ninguém perceber.

*O que o frontend pode fazer antes disso*, sem fechar a issue: trocar o
fallback silencioso de `fetchSgpChoices` por um erro visível e cachear o
endpoint pelo TanStack Query. Não vale desmontar os fallbacks das listas que o
endpoint não publica — o select ficaria vazio.

---

## 5. O schema OpenAPI não descreve o JSON que a API devolve — bloqueia a #273

*Estado atual:* `drf-spectacular` está instalado e configurado
(`DEFAULT_SCHEMA_CLASS` e `SPECTACULAR_SETTINGS` em `settings.py`, rota em
`setup/urls.py`). `manage.py spectacular --validate` gera o schema inteiro
(10.479 linhas), com **63 avisos e 23 erros**.

A #273 quer gerar os tipos do frontend a partir desse schema, para que uma
mudança de payload no backend vire erro de compilação. Isso só funciona se o
schema for fiel à resposta. Hoje não é — comparação feita em 25/09/2026, com a
mesma UPF e a mesma atividade do banco de demonstração:

| Campo | Schema | Resposta real da API |
|---|---|---|
| `UPFDetail.municipio` | `integer` | `{id, nome, estado: {id, sigla, nome}}` |
| `UPFDetail.membros` | `string` | lista de membros |
| `ActivityDetail.acao` | `integer` | `{id, numero, descricao}` |
| `ActivityDetail.tecnico_responsavel` | `integer` | `{id, nome, email}` |
| `ActivityDetail.fotos` | ausente | lista |
| `MembroList.idade` | `string` | número |

Tipos gerados deste schema estariam **errados**, e o código de hoje — que lê
`municipio.nome` — nem compilaria contra eles. A "prova de valor" da issue
(reverter o bug do Estado e ver o build quebrar) também não fecha: o schema
modela `municipio` como número.

*Registro:* o bug original da issue — o Estado vazio na ficha da UPF — já está
corrigido na API, que agora aninha o `estado` dentro de `municipio`. Só o
schema não sabe disso.

**Causas, com o pedido de cada uma:**

1. **Respostas reescritas em `to_representation`** — em
   `apps/sgp/serializers/upf.py`, `apps/sgp/serializers/activity.py`,
   `apps/core/serializers.py` e `apps/sgd/serializers/demand_request.py`. O
   schema descreve os campos declarados (o id cru), não o objeto que sai.
   *Pedido:* serializers de leitura que declarem a forma real, ou
   `@extend_schema(responses=...)` apontando para eles.
2. **`SerializerMethodField` sem tipo** — cerca de 40 avisos
   "unable to resolve type hint" (`get_idade`, `get_membros`, `get_perfis`,
   `get_territorios`, `get_cpf`…); sem tipo, o spectacular assume `string`.
   *Pedido:* type hint no método ou `@extend_schema_field`.
3. **22 views sem serializer** ("unable to guess serializer"), com a resposta
   sem tipo no schema. Entre elas várias que o frontend consome:
   `SGPChoicesView`, `WorkPlanDashboardView`, `GoogleCalendarStatusView`,
   `GoogleCalendarConfigView`, `SaldoConsultaView`, `MembroExportView`, `me`,
   `unread_count`. *Pedido:* `@extend_schema(responses=...)` em cada uma.
4. **Componente duplicado** — dois serializers geram o nome `EstadoNested`
   (um deles via `SaldoConsultaSerializer`). *Pedido:* renomear um dos dois.

Para reproduzir: `python manage.py spectacular --file /tmp/schema.yml --validate`
dentro do container do backend.

*O que o frontend pode fazer antes disso*, sem fechar a issue: montar a geração
com `openapi-typescript`, o gate de CI e a documentação no README. Migrar os
arquivos de `lib/` — o grosso da issue — só depois que o schema bater com a
resposta.

---

## 6. `GET /api/v1/sgd/demandas/` não filtra por atividade — a aba mostra demandas de outras atividades

*Estado atual:* `DemandViewSet.list` (`backend/apps/sgd/views/demand.py`) só lê
`?status=`. O frontend manda `?activity={id}` na aba "Demandas" da ficha da
atividade; o backend ignora o parâmetro e devolve **todas** as demandas visíveis
ao usuário. Na prática, a aba de uma atividade lista demandas da vizinha.

*Estado atual no frontend:* a aba mostra o que a API devolve, sem filtrar no
cliente. O E2E `demandas.spec.ts` prova que o parâmetro é enviado; a asserção
"não lista a demanda de outra atividade" está como `test.fixme` até o filtro
existir.

**Pedido:** aceitar `activity` na listagem (e, de passagem, paginar — hoje a
lista vem inteira):

```python
activity_param = request.query_params.get("activity")
if activity_param:
    qs = qs.filter(activity_id=activity_param)
```

*Relacionado à #273:* o `DemandViewSet` é um `ViewSet` sem serializer
declarado, então o schema OpenAPI não descreve nenhuma das suas rotas. Os tipos
do SGD no frontend (`app/lib/demandas.ts`) estão escritos à mão por isso — a
#294 pedia os tipos gerados.

---

## 7. Submeta e Indicador não existem no modelo do SGP

A #294 pede que o formulário mostre a cadeia **Ação → Submeta → Meta →
Indicador** do Plano de Trabalho. O próprio backend registra, em
`DemandContextoSerializer` (`apps/sgd/serializers/demand.py`), que o SGP modela
só dois níveis: Ação e Meta.

*Estado atual no frontend:* o contexto herdado mostra Ação e Meta; Submeta e
Indicador não aparecem.

**Pedido:** decisão de modelo, com a coordenação — criar os dois níveis no
Plano de Trabalho, ou ajustar o requisito do SGD. Não é campo que falte num
serializer: o dado não existe.

---

## 8. O detalhe da atividade não traz o nome do território nem a Meta da Ação

O formulário de nova demanda mostra o contexto herdado **antes** de a demanda
existir, então a fonte é `GET /api/v1/sgp/atividades/{id}/`. Esse detalhe traz
só `territorio_id` (sem nome) e `acao: {id, numero, descricao}` (sem a Meta).

*Estado atual no frontend:* Território e Meta aparecem como "Não disponível".
Os tipos já esperam os campos (`territorio?: {id, nome}` e
`acao.meta?: {id, numero, titulo}` em `app/lib/atividades.ts`) — quando o
backend os enviar, a tela passa a mostrá-los sem mudança.

**Pedido** — em `ActivityDetailSerializer.to_representation`, no padrão dos
outros aninhados:

```python
territory = instance.municipio.territory
data["territorio"] = {"id": territory.pk, "nome": territory.nome} if territory else None
data["acao"]["meta"] = {
    "id": instance.acao.meta_id,
    "numero": instance.acao.meta.numero,
    "titulo": instance.acao.meta.titulo,
}
```

---

## 9. `ActivityFilter` sem busca textual e com `status` de um valor só

O campo "Atividade" do formulário (caminho alternativo, pelo SGD) busca no
servidor as atividades do solicitante que aceitam demanda:

```
GET /api/v1/sgp/atividades/?tecnico_id={eu}&status=planejado&status=agendado&q={texto}
```

Verificado em 25/09/2026, com o ADT do Território RN:

```
?tecnico_id=13&status=planejado                    → 1 (a planejada)
?tecnico_id=13&status=planejado&status=agendado    → 0 (só vale o último status)
?tecnico_id=13&status=planejado&q=zzzz             → 1 (q ignorado)
```

*Estado atual no frontend:* o contrato acima é enviado como está. Hoje a busca
traz só as Agendadas e o texto digitado não estreita a lista. Nada é filtrado no
cliente para compensar.

**Pedido** — no `ActivityFilter` (`apps/sgp/filters.py`):

- `status` como `MultipleChoiceFilter` (aceitar o parâmetro repetido);
- `q` por título, no padrão do `UPFFilter.filter_q`:
  `queryset.filter(titulo__icontains=value)`.

---

## 10. Criar demanda não confere o escopo da atividade — falha de segurança

`DemandViewSet.create` resolve a atividade com
`get_object_or_404(Activity, pk=activity_id)`, **sem** o recorte territorial. O
`IsADTInTerritory` só confere o perfil no `create` — o `has_object_permission`
nunca roda, porque o viewset não chama `get_object`.

Verificado em 25/09/2026 com o ADT do Território RN e a atividade 95 (Serra
Talhada, PE):

```
GET  /api/v1/sgp/atividades/95/                        → 404 (fora do escopo dele)
POST /api/v1/sgd/demandas/  {"activity_id": 95, ...}   → 201 (demanda criada)
```

Ou seja: qualquer ADT abre demanda — pedido de recurso — em atividade de outro
território, bastando saber o id. O mesmo vale para a criação inline:
`criar_activity_inline` não confere se o município e a Ação estão no escopo do
solicitante.

*Estado atual no frontend:* a tela só oferece as atividades do próprio usuário
e os municípios dos territórios dele. Isso é afordância, não proteção.

**Pedido:** resolver a atividade pelo mesmo queryset com recorte que o
`ActivityViewSet` usa (e o município da criação inline pelos territórios do
usuário), devolvendo 404/403 fora do escopo. Teste sugerido: ADT de um
território cria demanda em atividade de outro → 404.
