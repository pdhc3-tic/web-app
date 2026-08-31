# Pendências de backend — sprint 8 (pós-audit)

*Compilado após o merge dos commits da sprint-8 em `frontend/sprint-8`
(commits `cceb2b2` até `36599a5`, em 31/08/2026).*

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

## 6. Bug UTC — resolvido, sem ação no backend

Reportado como o "bug UTC" na sessão de auditoria. Frontend fixado no
commit `cceb2b2` (issue 157) — helpers `localDayStartISO` /
`localDayEndISO` em `frontend/app/lib/datetime.ts` substituindo a
concatenação `T00:00:00Z` em `sync-events`, `users` e `upfs`. Backend
não precisou mexer — recebia UTC correto, o problema era o frontend
enviar UTC deslocado.

Registrado aqui para memória: se aparecer padrão semelhante em nova
tela, usar os helpers em vez de recriar a concatenação.

---

## Resumo — o que fica pendente no backend para o sprint 8

| # | Item | Bloqueia |
|---|---|---|
| 1 | `respondente_isnull` no `FormResponseFilter`                                | critério "Apenas anônimas" (#180) |
| 2 | BE-25 (#187) — omitir `saude`/`cor_raca` por perfil                          | critério de exibição condicional (#192) + coluna condicional do export de membros (#191) |
| 3 | Endpoint admin de token Power BI (`GET` + `POST /regenerar`)                 | tela inteira (#143) |
| 4 | Endpoint `GET /api/v1/sgp/upfs/{upf_pk}/membros/exportar/`                   | tela inteira (#191) |
| 5 | Seed com `FormResponse` + `MembroFamilia` com campos sensíveis               | destrave dos E2E de #178/#179/#180/#181/#192 |
