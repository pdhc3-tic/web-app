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

*Os itens 11 a 14 foram acrescentados em 29/09/2026, ao implementar a issue
#296 (painel master-detail de Demandas e decisões por perfil). As decisões, o
preview de impacto e o alerta de rubrica já existem no backend; os itens abaixo
são o que faltou para fechar os critérios.*

*O documento da sprint anterior (`pendencias-backend-sprint-9.md`) continua
valendo para o que está lá — os itens dele **não foram reavaliados** nesta
compilação.*

---

## 1. `GET /api/v1/upfs/exportar/` não existe — bloqueia a #240 inteira

> **Resolvido em 30/09/2026 pelo PR #306.** O backend adotou outro formato
> para a exportação assíncrona — `GET/download/repetir` em
> `/api/v1/sgp/exportacoes/{id}/`, status `erro` em vez de `falhou`, campos
> `total_registros`/`nome_arquivo`/`expira_em` —, e o frontend foi adaptado a
> ele em 01/10/2026. O texto abaixo fica como registro do pedido.

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

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 9 da #373): `CORS_EXPOSE_HEADERS = ["Content-Disposition"]`: o nome do arquivo chega ao front.

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

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 10 da #373): o limite da exportação assíncrona de UPFs virou `UPF_EXPORT_ASYNC_THRESHOLD` (variável de ambiente, padrão 1.000). O E2E da #240 passa do limite com UPFs sintéticas criadas pela fixture.

> *Ainda aberto em 01/10/2026:* o PR #306 manteve o limite fixo
> (`UPF_EXPORT_SYNC_LIMIT = 1000` em `apps/sgp/services/upf_export.py`). Por
> isso os E2E do caminho assíncrono continuam com a resposta forjada.

O banco de demonstração tem **41 UPFs** (38 ativas). O critério "exportação
acima de 1.000 registros é assíncrona" não é reproduzível à mão em nenhum
ambiente que parta do seed.

Não é pedido de seed com mil famílias — isso pesaria em toda execução do CI.
**Pedido:** tornar o limite configurável (ex.: `UPF_EXPORT_ASYNC_THRESHOLD` em
`settings`, default 1.000), para que homologação e o teste manual possam
baixá-lo e exercitar o fluxo assíncrono com o seed atual.

---

## 4. `/api/v1/choices/` não publica metade das listas — bloqueia a #272

> **Resolvido em 07/10/2026 pelo PR #326:** o endpoint publica as 25 listas do
> SGP com rótulo e tem teste de contrato. O frontend passou a consumir só ele
> (#272, 08/10/2026). **Sobra uma lacuna:** as categorias do catálogo de
> culturas e de espécies (`Cultura.CATEGORIA_CHOICES`,
> `EspecieAnimal.CATEGORIA_CHOICES`) não estão no endpoint e o catálogo devolve
> só o valor cru (`"graos"`), então o rótulo ainda é traduzido no frontend
> (`app/lib/producao.ts`). **Pedido:** publicar `cultura_categoria` e
> `especie_categoria` em `CHOICES_PUBLICADOS`, ou devolver `categoria_display`
> no serializer do catálogo.
>
> **Revisão do PR #341 (Pedro, 20/10/2026):** a #272 foi considerada atendida
> para os formulários migrados ao `SgpChoicesProvider`. A lacuna das categorias
> fica registrada aqui como a exceção da fonte única: até o backend publicá-las,
> `app/lib/producao.ts` continua espelhando esses rótulos.

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

> **Resolvido no backend pelo PR #332 (BE-5)**, com o filtro `?atividade=`;
> o PR #339 acrescentou `?activity=` como alias. A aba usa `?atividade=`
> desde 17/10/2026, e o E2E "não lista a demanda de outra atividade" deixou
> de ser `test.fixme`.

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

> **Resolvido no backend em 30/09/2026 pelo PR #307**: o Plano de Trabalho
> ganhou Submeta e Indicador, e o `contexto` da demanda traz a cadeia
> completa (`submeta_*`, `indicador_*`). O formulário de nova demanda ainda
> não a mostra porque lê o detalhe da ATIVIDADE, que segue sem esses campos —
> ver o item 8.

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

> **Resolvido no backend pelo PR #328** (conferido em 29/10/2026 na `main`): o detalhe da atividade traz `territorio` e a Meta da Ação.

> *Em andamento em 08/10/2026:* o PR #328 (aberto) aninha `territorio` e
> `acao.meta`/`submeta`/`indicador` no detalhe. O frontend já espera esses
> nomes e mostra a cadeia completa assim que o PR entrar.

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

*Atualização de 01/10/2026:* com o PR #307, o `contexto` da demanda já sai
completo (Ação → Submeta → Meta → Indicador). Para o formulário de **nova**
demanda mostrar a mesma cadeia antes de a demanda existir, o detalhe da
atividade precisa aninhar, além do território e da Meta, `acao.submeta`
(`numero`, `titulo`) e `acao.indicador` (`codigo`, `nome`, `unidade_medida`) —
os mesmos campos que `DemandContextoSerializer` já lê.

---

## 9. `ActivityFilter` sem busca textual e com `status` de um valor só

> **Resolvido no backend pelo PR #328** (conferido em 29/10/2026 na `main`): `status` é `MultipleChoiceFilter` e `q` busca pelo título.

> *Em andamento em 08/10/2026:* o PR #328 (aberto) traz status múltiplo e
> busca nas atividades.

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

> **Resolvido no backend pelo PR #325** (conferido em 29/10/2026): a criação de demanda respeita o escopo territorial do solicitante.

> *Em andamento em 08/10/2026:* o PR #325 (aberto) faz a criação de demanda
> respeitar o escopo territorial do solicitante.

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

---

## 11. A linha do tempo da demanda não é exposta — `ApprovalStep` sem endpoint

> **Resolvido em 07/10/2026 pelo PR #327:** `DemandSerializer.etapas`, no
> formato que o frontend esperava. A linha do tempo mostra as decisões.

Toda decisão grava um `ApprovalStep` (`apps/sgd/models/approval_step.py`:
etapa, ação, responsável, justificativa, excedente, data), mas nenhum
serializer ou rota o devolve. A #296 pede a timeline de status no painel.

*Estado atual no frontend:* a aba "Linha do tempo" mostra a criação e o status
atual (que vêm da própria demanda) e, no lugar das decisões, "O histórico de
decisões ainda não é enviado pela API". O tipo `EtapaDemanda` em
`app/lib/demandas.ts` descreve o que a tela espera; o E2E correspondente está
como `test.fixme`.

**Pedido** — aninhar no `DemandSerializer`:

```python
etapas = ApprovalStepSerializer(many=True, read_only=True)
# campos: id, etapa, etapa_display, acao, acao_display,
#         responsavel_nome (source="responsavel.nome"), justificativa,
#         excedente_autorizado, criado_em
```

---

## 12. O `DemandSerializer` traz só o id do solicitante

> **Resolvido em 07/10/2026 pelo PR #327** (`solicitante_nome`).

A coluna "Solicitante" do painel e o detalhe mostram `Usuário #13`: o
serializer devolve `solicitante` como id, e `/api/v1/users/` é restrito ao
Super Admin, então nenhum aprovador consegue resolver o nome.

**Pedido:** `solicitante_nome = serializers.CharField(source="solicitante.nome")`.
O tipo `Demanda.solicitante_nome` já está declarado no frontend.

---

## 13. Fila "Aguardando minha ação": `status` de um valor só e sem contagem

> **Resolvido no backend em 20/10/2026 pelo PR #339**: `status` repetido
> devolve a união, e `?aguardando_minha_acao=true` lista a fila do perfil pela
> mesma regra da contagem. A fila do painel passou a usar esse filtro.

> *Parcialmente resolvido em 07/10/2026 pelo PR #327:* a rota
> `aguardando-minha-acao/contagem/` devolve `{total, status}` com a regra de
> cada perfil no backend — o badge e a contagem usam ela, e o frontend deixou
> de espelhar a regra. **Continua aberto:** a listagem ainda lê um só
> `status`, então a LISTA da fila da FGD (Autorizada + Em atendimento) segue
> só com as Em atendimento.

A fila de cada perfil é a lista filtrada pelos status que cabem a ele decidir
(Articulador: Submetida; UGP: Pré-autorizada; FGD: Autorizada **e** Em
atendimento), e a mesma consulta alimenta o badge "N pendentes" da sidebar.

- `DemandViewSet.list` lê `status` com `query_params.get`, que fica só com o
  **último** valor. A FGD manda `?status=autorizada&status=em_atendimento` e
  recebe só as Em atendimento: as Autorizadas, que esperam o "Iniciar
  atendimento", ficam fora da fila e do badge.
- A regra "o que cabe a cada perfil" fica espelhada no front
  (`STATUS_AGUARDANDO`, em `app/lib/demandas.ts`), a partir do que
  `apps/sgd/services/approval.py` já usa para escolher quem notificar.
- O badge baixa a lista inteira (não paginada) só para contar.

**Pedido:**

- aceitar `status` repetido (`getlist`);
- de preferência, um filtro próprio — `?aguardando_minha_acao=true` — com a
  regra no backend, e uma rota de contagem
  (`GET /api/v1/sgd/demandas/aguardando-minha-acao/contagem/` → `{"total": N}`)
  para o badge;
- paginar a listagem.

---

## 14. Cancelar demanda autorizada não é permitido — decisão de regra

> **Resolvido no backend em 20/10/2026 pelo PR #339**: UGP e Super Admin
> cancelam uma demanda Autorizada pelo `POST .../cancelar/`, com
> `justificativa` obrigatória; as reservas são liberadas e a etapa
> "Cancelamento" entra na linha do tempo. O botão "Cancelar demanda" está no
> painel, com o `ConfirmationDrawer`. O PR registra que a regra ainda aguarda
> confirmação da coordenação.

A #296 pede que "cancelar demanda autorizada" use o `ConfirmationDrawer`, com
justificativa obrigatória. No backend, `pode_cancelar`
(`apps/sgd/services/approval.py`) só deixa **o próprio solicitante** cancelar,
e só até Pré-autorizada (`STATUS_CANCELAVEIS_PELO_SOLICITANTE`). Não existe
caminho para cancelar uma demanda Autorizada, nem para um aprovador cancelar.

*Estado atual no frontend:* o `ConfirmationDrawer` existe
(`app/components/ui/ConfirmationDrawer`) e já é usado na ação de alto impacto
disponível — **Recusar** (UGP). O E2E de cancelar autorizada está como
`test.fixme`.

**Pedido:** definir, com a coordenação, quem cancela uma demanda Autorizada (e
com que efeito na reserva de saldo); quando existir, o botão entra no painel
com o mesmo drawer.

---

## 15. Risco de glosa da importação Arlo não é exposto (#298)

> **Resolvido no backend pelo PR #375** (item 1 da #367): a importação devolve `divergencias`, com `risco_glosa` e a diferença com sinal. A tela mostra as divergências no acompanhamento e no histórico, com a glosa destacada; o E2E deixou de ser `fixme`.

> **Reforçado na revisão do PR #341 (Pedro, 20/10/2026):** a #298 não pode
> ser considerada concluída sem este item. As divergências precisam aparecer
> logo após a importação **e** no detalhe da operação no histórico. Se a parte
> do requisito sobre pagamentos abaixo do autorizado for mantida, a resposta
> deve permitir identificar também esses casos.

A importação do retorno do Arlo grava um `GlosaRisk` para cada pagamento acima
do valor autorizado (`apps/sgd/services/arlo_import.py`), mas **nenhum
endpoint devolve esses registros**. Eles também não entram no
`ArloImportSerializer` e não aparecem no BE-5 (PR #332). A #298 pede
que, após a importação, as demandas com divergência entre autorizado e pago
apareçam destacadas, em especial o risco de glosa.

*Estado atual no frontend:* a tela `/sgd/arlo` mostra o resumo e os erros por
linha da importação, mas não destaca nenhuma divergência. O front não calcula
a divergência por conta própria. O E2E do destaque está como `test.fixme`.

**Pedido:** devolver as divergências da operação. Pode ser um campo
`divergencias` no `ArloImportSerializer` (lista de
`{demanda_id, demanda_titulo, solicitacao_id, valor_autorizado, valor_pago, excedente}`),
ou `GET /api/v1/sgd/arlo/{id}/divergencias/`. Se a regra também valer para
pagamentos abaixo do autorizado, incluir esses casos com o sinal do valor.

---

## 16. Importação Arlo sempre falha no ambiente Docker local (#298)

> **Resolvido no backend pelo PR #375** (item 2 da #367): `celery_worker` e `celery_beat` montam `./backend` como o `backend`, e o arquivo ausente grava uma mensagem legível.

> **Bloqueio apontado na revisão do PR #341 (Pedro, 20/10/2026):** sem o
> armazenamento compartilhado, o upload é confirmado e a task depois marca a
> importação como **Falhou**. Isso bloqueia o fluxo operacional da #298 mesmo
> depois do item 15. Os E2E de importação (`frontend/e2e/arlo.spec.ts`) passam
> aqui só com um ajuste local de volumes no `docker-compose.yml`, que não vai
> para o repositório. Precisam ser rodados de novo com a correção do backend.
>
> *O que o frontend já fez:* quando a importação falha, a tela diz que a
> planilha não pôde ser processada e que nenhuma demanda foi alterada, e pede
> para enviar de novo. O texto gravado pelo backend aparece como "Detalhe
> técnico" (E2E da planilha sem as colunas obrigatórias). A troca da mensagem
> no backend continua pedida, porque hoje esse detalhe é só um caminho de
> arquivo.

No `docker-compose.yml`, o `celery_worker` não monta `./backend:/app`, ao
contrário do `backend`. Com `STORAGE_BACKEND=local`, o backend grava a
planilha enviada no próprio disco (`media/arlo/importacoes/…`). A task
`process_arlo_import` roda no worker, não acha o arquivo e marca a operação como
**Falhou**. O worker também roda o código da imagem construída, e não o da branch.

A mensagem gravada em `erros_json` é só o `str()` da `StorageObjectNotFound`,
ou seja, o caminho do arquivo (`arlo/importacoes/<uuid>.csv`). Para quem opera,
não explica o que aconteceu.

**Pedido:**

- montar o código e a pasta `media` no `celery_worker` e no `celery_beat`,
  como no `backend`, ou um volume `media` compartilhado entre eles;
- trocar a mensagem por algo legível, como "O arquivo enviado não foi
  encontrado no armazenamento. Envie a planilha novamente.".

---

## 17. Opções dos campos das solicitações do SGD fora do `/api/v1/choices/` — bloqueia a #295

> **Resolvido no backend** (conferido em 29/10/2026 na `main`): o `/choices/` publica `solicitacao_tipo` e as sete listas dos campos (`beneficiario_vinculo`, `meio_transporte`, `classe`, `urgencia`, `tipo_veiculo`, `tipo_material`, `tipo_refeicao`), que o formulário da #295 já consome.

A #295 exige que todos os selects do formulário de solicitação usem a fonte
única de choices da #272, sem nenhum `enum` duplicado no frontend. No backend,
as opções dos 6 tipos de solicitação existem só como conjuntos internos de
validação, **sem rótulo**, em `apps/sgd/services/demand_request.py`:
`_VINCULO_CHOICES`, `_MEIO_TRANSPORTE_CHOICES`, `_CLASSE_CHOICES`,
`_URGENCIA_CHOICES`, `_TIPO_VEICULO_CHOICES`, `_TIPO_MATERIAL_CHOICES` e
`_TIPO_REFEICAO_CHOICES`. Nenhum deles é publicado em `CHOICES_PUBLICADOS`.

**Pedido:** transformar esses conjuntos em `TextChoices` com rótulo e
publicá-los no `/api/v1/choices/`, junto com o próprio tipo de solicitação
(`diarias`, `passagem`, `veiculo`, `material_grafico`, `alimentacao`,
`equipamento`).

---

## 19. Auditoria da demanda só é visível ao Super Admin — divergente da #322

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 4 da #373): quem vê a demanda vê a trilha; o IP sai só para o Super Admin.

*Compilado em 21/10/2026, ao implementar a issue #322 (aba de auditoria no
painel master-detail de demandas).*

A #322 pede, em critério de aceitação, "acesso restrito conforme a mesma
política de quem pode visualizar a demanda (RLS já aplicada)". O endpoint
`GET /api/v1/sgd/demandas/{id}/auditoria/` (BE-7, PR do `DemandViewSet.auditoria`)
já aplica o escopo de leitura pelo `get_queryset` para resolver a demanda, mas
em cima disso adiciona a permissão `IsSuperAdmin` — a trilha devolve o IP de
quem agiu, e o backend decidiu que esse dado pessoal não cabe ao aprovador.

```python
if self.action == "auditoria":
    return [IsAuthenticatedActiveAccess(), IsSuperAdmin()]
```

*Estado atual no frontend:* a aba "Auditoria" só aparece para Super Admin
(`useIsSuperAdmin`). Articulador, UGP e FGD veem o painel sem a aba — a
política atual do backend seria 403 para eles. A diferenciação visual, o
"carregar mais" e os quatro E2E da issue cobrem o caminho do Super Admin.

**Pedido** — alinhar com a coordenação qual regra vale:

- se a trilha completa (com IP) é mesmo só do Super Admin, atualizar o
  critério da #322 para refletir isso;
- se o aprovador deve ver a trilha, decidir se o IP sai da resposta para esses
  perfis (`DemandAuditEntrySerializer` com `fields` dinâmico), ou se o campo
  fica para o Super Admin apenas. Nesse cenário o frontend libera a aba para
  os decisores (`perfisDecisoresSgd`).

---

## 18. Mapeamento Arlo ↔ SGD: sem catálogo de campos e sem preview — bloqueia parte da #320

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 7 da #373): `GET .../arlo-mapping/campos/` e `GET .../arlo-mapping/preview/?direcao=exportacao`. A tela da #320 usa as duas rotas, sem catálogo copiado no front.

O CRUD do BE-9 (`/api/v1/sgd/config/arlo-mapping/`) permite listar, editar,
apagar e reordenar, mas a #320 pede mais duas coisas que a API não oferece:

1. **Catálogo dos campos.** `campo_sgd` é texto livre na API. A lista de campos
   válidos por direção, os obrigatórios e os formatos permitidos de cada um
   (`CAMPOS`, `CAMPOS_*_OBRIGATORIOS`, `formatos_permitidos` em
   `apps/sgd/services/arlo_mapping.py`) não é exposta e não tem rótulo. Sem
   ela, o front não monta o "criar coluna" e mostraria nomes internos como
   `valor_autorizado`.
2. **Preview da exportação.** A issue pede uma linha do CSV de exemplo com o
   mapeamento corrente. Montá-la no front exigiria copiar a formatação de data
   e moeda (`formatar_valor`) e reconstruir campos que a API de demandas não
   devolve (submeta, indicador).

**Pedido:**

- `GET /api/v1/sgd/config/arlo-mapping/campos/` →
  `{exportacao: [{campo, label, obrigatorio, formatos: [{value, label}]}], importacao: […]}`;
- `GET /api/v1/sgd/config/arlo-mapping/preview/?direcao=exportacao` →
  `{colunas: [...], linha: [...]}` com uma demanda autorizada real, ou um
  registro fictício quando não houver nenhuma.

*Estado atual no frontend:* a #320 aguarda essas duas rotas para ser feita
inteira, por decisão do time de não entregar a tela pela metade.

---

## 22. Pedidos de recurso extra sem filtro por demanda (#321)

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 2 da #373): `GET /sgd/remanejamentos/?demanda=`.

*Compilado em 22/10/2026, ao implementar a issue #321 (fluxo "Solicitar recurso
extra" e Fila de Remanejamentos). Numerado a partir do 22 porque os itens 20 e
21 do relatório de pendências das issues #294 a #302 (o do PR #343) já usam esses
números.*

A #321 pede que a aprovação do recurso extra apareça na demanda bloqueada, com
"indicação clara de que a demanda pode ser resubmetida". O pedido guarda a
demanda em `BudgetIncreaseRequest.demanda_id`, mas
`GET /api/v1/sgd/remanejamentos/` só filtra por `status`: não há como pedir os
pedidos de UMA demanda.

*Estado atual no frontend:* o painel da demanda (só para o solicitante, em
Rascunho ou Devolvida) chama `GET /sgd/remanejamentos/?status=todos&demanda={id}`
e mostra o pedido mais recente. Até o filtro existir, o parâmetro é ignorado e a
lista traz **todos** os pedidos do solicitante: com pedidos em mais de uma
demanda, o aviso pode ser o de outra demanda dele. Nada é filtrado no cliente.

**Pedido:** aceitar `?demanda={id}` na listagem (`demanda_id` é texto no
modelo; comparar com o id como string).

---

## 23. O bloqueio na submissão não informa o valor faltante (#321) — na #373 (item 16)

> **Ainda aberto em 29/10/2026.** O `INSUFFICIENT_BALANCE` da #349 (PR #370)
> trouxe `disponivel` e `solicitado`, mas os dois são da solicitação barrada,
> não da rubrica: com mais de uma solicitação na mesma rubrica, ou em Devolvida
> com reservas ativas (o front não sabe quais), `solicitado − disponivel` não é
> o que o pedido de recurso extra registra. A #359 já lê `valor_faltante` em
> cada item de `solicitacoes_bloqueadas` e o mostra preenchido no fluxo guiado;
> sem o campo, mantém "calculado pelo sistema ao registrar o pedido".

*Compilado em 22/10/2026, ao implementar a issue #321.*

A #321 pede que o fluxo guiado confirme "o valor faltante antes de enviar". O
backend calcula esse valor (`_deficit_individual` em
`apps/sgd/services/recurso_extra.py`) e o usa quando `valor_solicitado` não é
enviado, mas não o expõe antes do envio: o 400 da submissão
(`solicitacoes_bloqueadas`, e no PR #343 também `code` e `solicitacao_id`) traz
só a trava, o motivo em texto e a ação sugerida.

Calcular no front exigiria repetir a regra (solicitações sem reserva ativa
menos o saldo do limite, que pode estar negativo depois de um excedente
autorizado).

*Estado atual no frontend:* o fluxo mostra o motivo do bloqueio, envia sem
`valor_solicitado` e exibe o valor que o pedido registrou no passo final.

**Pedido:** incluir `valor_faltante` em cada item de `solicitacoes_bloqueadas`
quando a trava for a individual, ou numa rota de consulta
(`GET /sgd/demandas/{id}/recurso-extra/preview/?rubrica=`).

---

## 24. Notificações do SGD somem do sino e apontam para produção (#321)

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 3 da #373): notificação in-app nasce entregue, o sino ordena com as sem data por último e o link local aponta para o frontend local.

O caminho natural do solicitante até um pedido devolvido ou decidido é a
notificação (`notificar_recurso_extra_devolvido` e `_decidido`, com link para
`/sgd/remanejamentos/{id}`). No teste da #321 ela não aparece no sino, por dois
motivos:

1. **Ordem da lista.** `GET /api/v1/notifications/me/` ordena por
   `-enviado_em`, mas `_notificar` (`apps/sgd/services/notifications.py`) só cria
   o registro, e quem preenche `enviado_em` é a task de e-mail
   (`apps/core/tasks/notifications.py`). As in-app ficam com `status=pendente` e
   `enviado_em` nulo. O ADT do seed tem 75 assim, e sem data a ordem é
   indefinida: a notificação nova não cai na primeira página do sino.
   `Notification` também não tem data de criação para servir de critério.
   Pelo mesmo motivo, o sino não mostra **quando** a notificação chegou: o
   horário ("há 5 minutos") vem de `enviado_em`, que chega `null`.
2. **Link de produção.** O link é montado com `FRONTEND_BASE_URL`, que fora de
   produção cai no padrão `https://pdhc.ufersa.edu.br`. No ambiente local, o
   clique sai do sistema.

*Estado atual no frontend:* o sino mostra o que a API devolve, na ordem dela.
Para chegar ao pedido, o teste usa o link direto.

**Pedido:** marcar as in-app como entregues (`enviado_em` e `status`) ao
criá-las, ou ordenar por `-pk` / uma data de criação nova; e definir
`FRONTEND_BASE_URL` no `.env.example` e no `docker-compose.yml` para o
ambiente local.

---

## 25. O nome do arquivo exportado não chega ao front (#297)

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 9 da #373): `CORS_EXPOSE_HEADERS = ["Content-Disposition"]`.

`GET /api/v1/sgd/demandas/exportar/` manda o nome no `Content-Disposition`
(`demandas_<data_hora>.<formato>`), mas o `setup/settings.py` não define
`CORS_EXPOSE_HEADERS`. Com front e API em origens diferentes, como no ambiente
local (3000 → 8080), o navegador esconde esse cabeçalho do `fetch`. O arquivo
baixa com o nome padrão do front (`demandas_AAAA-MM-DD.<formato>`). O mesmo
vale para as outras exportações que dependem do nome vindo do backend.

**Pedido:** `CORS_EXPOSE_HEADERS = ["Content-Disposition"]`.

*Estado atual no frontend:* `baixarExportacaoDemandas` já lê o cabeçalho e cai
para o nome padrão quando ele não chega; nada muda no front quando o backend
expuser o cabeçalho.

---

## 26. Filtros de solicitante e responsável sem lista para os perfis de gestão (#297)

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 6 da #373): `GET /sgd/opcoes/usuarios/?papel=solicitante|responsavel`.

O painel de execução filtra por `solicitante` e `responsavel_etapa_atual` (ids
de usuário do `DemandFilter`), mas não há rota que liste esses usuários para
todos os perfis de gestão:

- `GET /api/v1/users/` é só do Super Admin;
- `GET /api/v1/sgp/tecnicos/` não serve: solicitante é usuário com perfil
  ADT/ACR, sem precisar de cadastro de técnico (no seed, a tabela de técnicos
  está vazia), e a FGD recebe 403 (fora do `ROLES_COM_ESCOPO`).

**Pedido:** `GET /api/v1/sgd/opcoes/usuarios/?papel=<papel>`, aberta aos
perfis de gestão do SGD (Super Admin, UGP, FGD, Articulador Estadual), com
resposta sem paginação:

```json
[{ "id": 4, "nome": "Ewerton Bandeira" }]
```

- `papel=solicitante`: usuários que podem solicitar demandas (perfil ADT/ACR)
  e que o perfil logado enxerga — o `id` é o que o filtro `solicitante` do
  `DemandFilter` recebe;
- `papel=responsavel`: usuários que podem estar na etapa atual de uma
  demanda (Articulador Estadual, UGP, FGD) — o `id` é o que o filtro
  `responsavel_etapa_atual` recebe;
- ordenada por `nome`.

*Estado atual no frontend:* os dois filtros já chamam essa rota
(`fetchOpcoesUsuarios` em `app/lib/execucaoSgd.ts`). Enquanto ela não existe,
o select mostra "Não foi possível carregar a lista."; quando o backend a
publicar com esse contrato, a lista aparece sem mudança no front.

---

## 27. O solicitante não vê o valor das diárias antes de salvar (#295)

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 1 da #373): `GET /sgd/config/diarias/simular/`, com a mesma regra do salvamento. O E2E da #295 confere o total em tempo real.

*Compilado em 24/10/2026, ao implementar a issue #295 (formulário de
solicitação de recurso).*

A #295 pede o "cálculo de valor total exibido em tempo real" na solicitação de
diárias (nº de diárias × valor por diária, recalculado ao mudar as datas). O
backend calcula esse valor em `_validar_diaria`, mas só ao gravar a
solicitação. O valor da diária fica em `SystemConfig("sgd_valor_diaria_padrao")`,
que só o Super Admin e a UGP leem (`IsSuperAdminOrUGPReadOnly`). O ADT, que
preenche o formulário, recebe 403.

Calcular no front exigiria repetir a contagem de diárias, que a SGD-REF-BE-12
(#358) vai trocar pela regra federal, com meia diária e faixa de destino.

O mesmo vale para o ambiente local: `sgd_valor_diaria_padrao` nasce `"0"` na
migration `sgd.0002`, e com ele o backend recusa TODA solicitação de diária
("Valor de diária não configurado"). O `seed_demo` passou a definir um valor de
teste (R$ 300,00).

**Pedido:** publicar a rota de simulação que a #358 já prevê, aberta a quem
cria demanda, com este contrato:

```
GET /api/v1/sgd/config/diarias/simular/?municipio_destino_id=&data_inicio=&data_fim=
```

```json
{
  "faixa_destino": { "id": 4, "nome": "Demais localidades" },
  "valor_por_diaria": "300.00",
  "numero_diarias": "2.5",
  "valor_total": "750.00"
}
```

- `data_inicio` e `data_fim` em `AAAA-MM-DD`, como no `campos_json`;
- os nomes dos campos são os que a #358 manda gravar em `campos_json`;
- `numero_diarias` é decimal, por causa da meia diária;
- sem valor vigente, 400 com a mensagem para o usuário (a tela a mostra).

Antes da #358, a mesma rota pode responder com a regra de hoje (`max(dias, 1)`
× `sgd_valor_diaria_padrao`) e uma faixa única.

*Estado atual no frontend:* o formulário de diárias já chama essa rota
(`simularDiarias` em `app/lib/solicitacoes.ts`) assim que destino e datas
estão preenchidos. Enquanto ela não existe, o quadro "Valor das diárias" mostra
o erro e avisa que o total é calculado ao salvar; o cartão da solicitação salva
mostra o valor que o backend calculou. O E2E do total em tempo real está como
`fixme` em `e2e/montar-demanda.spec.ts`.

---

## 28. Eventos do recurso extra fora da trilha de auditoria da demanda (#322)

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 5 da #373): eventos do recurso extra na trilha da demanda, com `tipo: "recurso_extra"`.

*Compilado em 24/10/2026, na revisão da #322.*

A trilha de `GET /api/v1/sgd/demandas/{id}/auditoria/` junta os eventos da
demanda (`ENTIDADE_DEMANDA`) e as movimentações de saldo
(`ENTIDADE_MOVIMENTACAO_SALDO`). Os eventos do recurso extra da demanda
(pedido, parecer, devolução, decisão e o aumento do limite individual) são
registrados em outras entidades e não aparecem nela. Quem audita a demanda não
vê que o limite subiu por um pedido aprovado, nem quem aprovou.

**Pedido:** incluir na trilha os eventos `recurso_extra.*` e o
`aumento_limite` dos pedidos daquela demanda, como já se faz com as
movimentações de saldo (`valores_novos__demanda`).

*Estado atual no frontend:* a aba Auditoria mostra o que a rota devolve; nada
muda no front quando os eventos entrarem, além de um ícone para o tipo novo.
