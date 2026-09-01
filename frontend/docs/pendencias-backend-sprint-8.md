# Pendências de backend — sprint 8 (pós-audit)

*Compilado após o merge dos commits da sprint-8 em `frontend/sprint-8`
(commits `cceb2b2` até `36599a5`, em 31/08/2026). Revisado em 01/09/2026 com
os itens levantados no review de PR do responsável pelo projeto — os três
novos são os de número 7, 8 e 9.*

Nenhum item aqui é destrave imediato do frontend — o frontend já foi
entregue consumindo os endpoints/campos que existem hoje. Cada item
bloqueia um critério específico de uma issue e/ou destrava testes E2E.

---

## 1. `respondente_isnull` no `FormResponseFilter` — bloqueia critério de #180

*Estado atual:* NÃO EXISTE. O frontend já manda `?respondente_isnull=true`.

O checkbox "Apenas anônimas" existe no frontend (commit `9c28420`). O
critério é filtrar respostas com `respondente=NULL` no banco — o rótulo
"Anônimo" só existe no frontend, então `respondente__icontains="Anônimo"`
volta vazio.

Sem o filter no backend, o `respondente_isnull` que o frontend envia é
**ignorado silenciosamente** por django-filter (parâmetro desconhecido não
gera erro), e o checkbox "Apenas anônimas" retorna a lista completa.

**Fix sugerido** — `backend/apps/sgp/filters.py`, dentro de `FormResponseFilter`:

```python
respondente_isnull = django_filters.BooleanFilter(
    field_name="respondente", lookup_expr="isnull"
)
```

E acrescentar `"respondente_isnull"` em `Meta.fields`. Assim que existir, o
checkbox começa a funcionar sem mais mudança de frontend. Teste sugerido:
`FormResponseFilter({"respondente_isnull": "true"}, ...)` retorna só as
anônimas.

---

## 2. BE-25 (#187) — omitir `saude`/`cor_raca` por perfil — bloqueia #192 e coluna condicional do #191

*Estado atual:* endpoint retorna sempre `saude` e `cor_raca` para todos os perfis.

O frontend (commit `0a3144a`) usa **presença/ausência das chaves** como
sinal — quando o backend começar a omitir por perfil, a UI esconde
automaticamente sem mudança de código.

Enquanto BE-25 não sai, a matriz de permissão do frontend é inócua na
prática. Sem regressão visual (comportamento atual = "todo mundo vê",
igual antes), mas o critério da issue #192 (esconder para perfis sem
permissão) só é verificável depois de BE-25.

**Também bloqueia:** teste E2E do #192 (precisa de perfil sem permissão
para verificar que o campo some da UI).

**Cross-issue:** #191 tem o mesmo critério "colunas exibidas no arquivo
baixado refletem o que o backend retornou (sem tentar preencher no
frontend colunas omitidas por falta de permissão)". Quando #191 for
implementada, deve herdar o mesmo comportamento.

---

## 3. Endpoint admin de gerenciamento do token Power BI — bloqueia #143 inteira

*Estado atual:* endpoint público existe (`WorkPlanPowerBIView`,
`backend/apps/sgp/urls.py:82`); endpoint admin, não.

O critério da issue é uma tela restrita a Super Admin para:

- Ver a URL do endpoint público (`/api/v1/sgp/plano-trabalho/powerbi/`)
- Ver o token mascarado (`••••••3f2a`)
- Ver a data do último snapshot atualizado (`atualizado_em`)
- Regenerar o token (invalidando o anterior imediatamente)

Nada disso é exposto pelo backend hoje — o `POWER_BI_SERVICE_TOKEN` é uma
env var, não há endpoint para lê-lo/regerá-lo em runtime, e o cache do
snapshot não expõe timestamp de atualização.

**Pedido:** novo view admin, algo como:

```
GET  /api/v1/admin/power-bi-token/            → { mascarado, atualizado_em }
POST /api/v1/admin/power-bi-token/regenerar/  → { novo_token }
```

Restrito a `IsSuperAdmin`. Regeneração deve invalidar o token anterior
imediatamente — o `PowerBIServiceTokenAuthentication` pode passar a ler
de um model em vez de settings (decisão de vocês).

Sem esse admin, a tela do #143 **não sai do papel**. Zero código de
frontend possível até vocês liberarem o contrato.

---

## 4. Endpoint `GET /api/v1/sgp/upfs/{upf_pk}/membros/exportar/` — bloqueia #191 inteira

*Estado atual:* NÃO EXISTE. Só há export de respostas de formulários (BE-20,
`apps/sgp/views/form_responses.py::export`) e de plano de trabalho (BE-9,
`apps/sgp/views/workplan.py::WorkPlanExportView`).

O critério da issue é botão "Exportar CSV" na aba Membros da ficha da UPF.
Sem endpoint, o frontend não tem por onde chamar.

**Pedido:** endpoint dedicado no `MembroFamiliaViewSet` (ou análogo):

```
GET /api/v1/sgp/upfs/{upf_pk}/membros/exportar/
```

Sem `?formato=` — o critério pede só CSV. Colunas: todas as visíveis na
listagem. **Respeitando a matriz de BE-25 (#187)** — cross-issue com o
item 2 acima.

Nome do arquivo via `Content-Disposition: attachment; filename="..."`,
mesmo padrão do BE-20 e do BE-9.

Sem esse endpoint, a tela do #191 **não sai do papel**. Zero código de
frontend possível até vocês liberarem o contrato.

---

## 5. Débito de testes E2E — bloqueado por seed

Os E2E das issues 178, 179, 180, 181 e 192 dependem de dados que o
`seed_demo` **não cria hoje**:

- `FormResponse` populado (nenhuma resposta no seed → 6 E2E como
  `test.fixme` em `frontend/e2e/formularios.spec.ts`);
- Perfis de teste sem permissão de Saúde/Cor-Raça, e `MembroFamilia` com
  esses campos populados (nenhum no seed → 0 E2E de #192).

Não é bloqueador do frontend, mas até o seed cobrir esses dois cenários,
o CI vai continuar com o `test.fixme` documentando "depende de
FormResponse no seed_demo" e as suítes de #192 nem existem.

**Sugestão:** na próxima rodada do seed, incluir:

- 3–5 `FormResponse` — mix de `submetido`/`rascunho`, alguns com
  `respondente=NULL` (anônimos), datas relativas a `timezone.now()`
  (para o filtro de período);
- 1–2 `MembroFamilia` com `saude`/`cor_raca` preenchidos, para exercitar
  a matriz de permissão quando BE-25 sair;
- (Bônus) 1–2 usuários de teste sem permissão de Saúde/Cor-Raça, para os
  E2E de #192.

---

## 6. Bug UTC — resolvido nas duas pontas

O frontend foi corrigido no commit `cceb2b2` (issue 157), trocando a
concatenação `T00:00:00Z` pelos helpers `localDayStartISO` / `localDayEndISO`.

Depois disso a **PR #212 (mergeada em 01/09/2026)** atacou a mesma classe de bug
pelo lado do backend: os filtros de data passaram a receber o `YYYY-MM-DD` cru e
a recortar o dia no `TIME_ZONE` do servidor, com renomeação dos parâmetros.

O frontend foi adaptado junto: `data_inicio`/`data_fim` no log de sincronização,
`ultimo_acesso_de`/`ultimo_acesso_ate` em usuários e
`cadastrado_de`/`cadastrado_ate` em UPFs, sem mais conversão para ISO em UTC
nesses três pontos. Os helpers continuam existindo para outros usos.

Fica o registro do risco, caso apareça mudança parecida: o django-filter
descarta parâmetro desconhecido **em silêncio**, sem 400. Uma renomeação de
parâmetro que entre sem o frontend correspondente não gera erro na tela — o
filtro simplesmente deixa de filtrar, e a lista completa passa por resultado.

---

## 7. UGP ainda lê e resolve conflitos de sincronização — bloqueia o aceite de #158

*Estado atual:* `ConflictLogViewSet.get_queryset` (`backend/apps/sca/views.py:308`)
devolve o queryset **inteiro** para o perfil `ugp`, e a action `resolver`
(`:331`) também o autoriza.

O aceite limita a revisão de conflitos a Articulador Estadual e Super Admin. O
frontend já foi ajustado: `canReviewSyncConflicts` não inclui mais a UGP, o
item de menu some e as rotas `/sca/conflitos` e `/sca/conflitos/{id}` caem no
403 da tela. Isso é **afordância, não recorte** — um usuário UGP com o token na
mão continua lendo e resolvendo conflitos direto na API.

**Fix sugerido** — em `get_queryset`, tirar `ugp` do ramo que retorna tudo, e em
`resolver` trocar o `elif not (super-admin or ugp)` por só `super-admin`.
Cuidado: a UGP continua com acesso legítimo ao restante do SCA
(`SyncDeviceListView` e `SyncEventViewSet` usam `IsSuperAdminOrUGPReadOnly`) —
o recorte é só nos conflitos.

**Teste sugerido:** `GET /api/v1/sca/conflicts/` autenticado como `ugp` deve
responder 403 (ou lista vazia, se preferirem manter o padrão de queryset
vazio dos demais perfis).

---

## 8. Fonte de técnicos para o filtro do log de sincronização — atendida pela PR #217

*Estado atual:* endpoint proposto em `backend/fonte-tecnicos` (PR #217, aberta),
ainda **não mergeado**: `GET /api/v1/sca/tecnicos/`, não paginado, com
`IsSuperAdminOrUGPReadOnly` e cobrindo quem tem dispositivo **ou** evento.

É exatamente o contrato que faltava. O frontend já consome esse endereço e cai
num fallback enquanto ele responde 404: percorre **todas** as páginas de
`/sca/devices/` seguindo `next`, em vez de supor que uma resposta é a lista
completa — o `?limit=500` anterior era silenciosamente reduzido a 100 pelo
`SCAPagination.max_limit`, então nem a listagem de dispositivos vinha inteira.

O fallback continua sem o técnico que não tem dispositivo; só o endpoint resolve
esse caso. Assim que a #217 entrar na main, o caminho dedicado passa a valer
sozinho, sem mais mudança de frontend.

**Ação:** mergear a #217.

---

## 9. Formulários distintos por UPF — atendida pela PR #214

*Estado atual:* endpoint proposto em `backend/filtros-formularios` (PR #214,
aberta), ainda **não mergeado**:
`GET /api/v1/sgp/upfs/{upf_pk}/formularios/opcoes/`, não paginado, devolvendo
`{formulario_id, formulario_nome, formulario_versao}` distintos da UPF.

Não confundir com a BE-18 (`/api/v1/sgp/formularios-disponiveis/`), que lista o
que está publicado para **novo** preenchimento — um formulário despublicado sai
de lá e continua no histórico da família.

O frontend já consome o endereço novo e cai num fallback enquanto ele responde
404: percorre **todas** as páginas da listagem de respostas, seguindo `next`, e
deduplica por `formulario_id`. A varredura anterior mandava um `page_size=200` e
tratava a primeira resposta como completa — o que deixava de fora formulário
cuja primeira resposta ficasse além do corte.

A mesma PR traz o `respondente_isnull` do item 1 deste documento.

**Ação:** mergear a #214 — ela fecha os itens 1 e 9 de uma vez.

---

## Resumo — o que fica pendente no backend para o sprint 8

| # | Item | Bloqueia |
|---|---|---|
| 1 | `respondente_isnull` — **pronto na PR #214**, falta mergear                   | critério "Apenas anônimas" (#180) |
| 2 | BE-25 (#187) — **pronto na PR #213**, falta mergear                            | exibição condicional (#192) + coluna condicional do export (#191) |
| 3 | Admin de token Power BI — **pronto na PR #215**, falta mergear                 | tela inteira (#143) |
| 4 | `GET .../membros/exportar/` — **pronto na PR #213**, falta mergear             | tela inteira (#191) |
| 5 | Seed com `FormResponse` + `MembroFamilia` com campos sensíveis               | destrave dos E2E de #178/#179/#180/#181/#192 |
| 7 | `ugp` fora do `ConflictLogViewSet` — **pronto na PR #213**, falta mergear      | recorte real de acesso aos conflitos (#158) |
| 8 | `GET /api/v1/sca/tecnicos/` — **pronto na PR #217**, falta mergear            | técnico sem dispositivo no select do log (#157) |
| 9 | `GET .../formularios/opcoes/` — **pronto na PR #214**, falta mergear           | opções completas do select da aba Formulários (#180) |

Situação em 01/09/2026: só o item 6 (bug UTC, PR #212) chegou à `main`. Todos
os demais têm PR aberta — #213 cobre os itens 2, 4 e 7; #214 cobre 1 e 9; #215
cobre o 3; #217 cobre o 8. Nenhuma está mergeada, e o frontend segue com o
comportamento provisório documentado em cada seção até que entrem.

O item 5 (seed) é o único sem PR correspondente.
