# Pendências de backend — sprint 9

*Compilado em 04/09/2026, na branch `frontend/sprint-9a`, ao fechar as issues
#133 (painel do Google Calendar), #143 (painel do Power BI) e #191 (exportação
de membros em CSV) contra o backend que já está na `main`. O documento da sprint anterior
(`pendencias-backend-sprint-8.md`) continua valendo para o que sobrou de lá — o
resumo no fim deste arquivo diz o que caiu e o que ficou.*

Os itens 1 a 5 e 7 **não bloqueiam entrega**: as telas de #133, #143 e #191
estão completas e verificadas contra os endpoints reais. Eles ou (a) completam
um critério hoje atendido pela metade, ou (b) transformam em E2E de verdade um
teste que só existe com a resposta fixada por stub.

**O item 6 é a exceção e é o mais importante daqui:** enquanto ele existir, o
critério da #192 não é demonstrável em runtime por ninguém — nem por teste, nem
à mão.

---

## 1. `GET /api/v1/admin/power-bi-token/` não diz desde quando o token vale

*Estado atual:* `PowerBITokenStatusSerializer`
(`backend/apps/core/serializers.py`) devolve `url_endpoint`,
`token_mascarado`, `atualizado_em` e `status_snapshot`.

O model `PowerBIToken` **já grava** `criado_em` e `criado_por`, e os dois
chegam ao frontend uma única vez — no retorno da regeneração, junto do valor em
claro. Quem recarrega a tela depois disso perde a informação: o painel mostra
`••••3f2a` sem nenhuma forma de responder "esse token é de quando?", que é
justamente a pergunta de quem administra rotação de segredo.

**Pedido** — acrescentar ao serializer do GET:

```python
criado_em = serializers.DateTimeField(allow_null=True)
criado_por = serializers.CharField(allow_null=True)  # e-mail ou nome de exibição
```

Custo: dois campos vindos de `PowerBIToken.ativo_atual()`, que a view já
carrega. Nenhum model novo, nenhuma migration. O frontend passa a exibir
"gerado há X dias por fulano" no card do token sem mais contrato.

---

## 2. `seed_demo` não cria dados para os painéis de integração

Dois buracos, de efeitos diferentes:

**`PowerBIToken`: nenhum.** O ambiente demo parte de "sem token" — foi o que a
API respondeu ao ser consultada hoje (`"token_mascarado": null`). A
consequência é que `e2e/power-bi.spec.ts` precisa **gerar** um token para
testar qualquer coisa, e a geração é irreversível por design: só o SHA-256 é
persistido (`PowerBIToken.gerar`), então não existe `finally` capaz de repor o
estado, como se faz em `acessos-sca.spec.ts` e `google-calendar.spec.ts`. É o
único spec da suíte que escreve sem poder desfazer.

**`GoogleCalendarSyncEvent`: nenhum.** O card de status da #133 só consegue
dizer "nunca sincronizado" contra o banco real. "Última sincronização há X
minutos", a contagem de falhas das últimas 24h e a mensagem do último erro —
três critérios de aceitação da issue — são exercitados interceptando
`/core/config/google-calendar/status/` com `page.route`.

**Pedido** — no `seed_demo`:

- 1 `PowerBIToken` ativo;
- `GoogleCalendarSyncEvent` cobrindo os quatro campos do endpoint agregado: um
  sucesso recente (dá o `estado` e a `ultima_sincronizacao`), uma falha mais
  antiga que o último sucesso (dá o `ultimo_erro` histórico), duas falhas
  dentro das 24h e uma fora dela (provam o corte da janela rolante).

Há uma proposta de implementação escrita nesta branch — não commitada, em
`backend/apps/sgp/management/commands/seed_demo.py`, no método `_integracoes`.
Ela resolve, de passagem, duas armadilhas que valem estar registradas:
`GoogleCalendarSyncEvent.ocorrido_em` é `auto_now_add`, então datas no passado
só entram por `UPDATE` depois do `create()`; e o `status_snapshot` do Power BI
vem do snapshot no Redis, não do banco — sem escrever o cache, a tela mostra
"sem snapshot" mesmo com token válido.

**Por quê:** o teste por stub prova a renderização, não a integração com o
contrato real. Se o backend renomear um campo do status, o stub continua verde
e a tela quebra em produção — é exatamente a classe de falha do item 3 abaixo.
Com dado no seed, os dois viram E2E de verdade e o stub fica só para os estados
raros (`atrasado`, `sem_snapshot`).

---

## 3. Nomes divergentes entre o contrato pedido e o entregue — já resolvido no frontend

*Registro, não pedido.* O item 3 do documento da sprint 8 pediu:

```
GET  /api/v1/admin/power-bi-token/            → { mascarado, atualizado_em }
POST /api/v1/admin/power-bi-token/regenerar/  → { novo_token }
```

A PR #215 entregou, com outros nomes e mais informação:

```
GET  → { url_endpoint, token_mascarado (anulável), atualizado_em, status_snapshot }
POST → { token, token_mascarado, criado_em }
```

As diferenças são **melhorias** — `status_snapshot` calculado no servidor
resolve o AC-2 melhor do que o cálculo local que o frontend fazia. O frontend
foi alinhado ao que existe nesta sprint. Nada a fazer no backend; fica
registrado porque quem ler os dois documentos veria a contradição.

**O que fica de lição:** o frontend lê JSON, não valida schema. Um campo
renomeado não gera erro — vira `undefined`. Foi literalmente o que aconteceu
aqui: a tela desestruturava `novo_token`, e como o backend manda `token`, o
diálogo de exibição única abria **vazio** e o token recém-gerado se perdia para
sempre, sem uma linha de erro em tela. Só apareceu numa leitura lado a lado do
serializer com o cliente.

Onde o frontend já se protege disso, vale como referência:
`fetchGoogleCalendarStatus` (`app/lib/integracoes.ts`) valida o `estado`
recebido e grita no console quando a resposta sai do contrato, em vez de
degradar em silêncio.

---

## 4. Atividades com falha de sincronização não são filtráveis

*Estado atual:* `Activity.google_calendar_sync_status` (`ok`/`pendente`/`erro`)
existe no model e aparece na ficha da atividade, mas **não** está no
`ActivityFilter` (`backend/apps/sgp/filters.py:132`, `Meta.fields`).

O painel da #133 agora avisa "2 falha(s) registrada(s) nas últimas 24 horas".
O próximo clique natural — *quais* atividades falharam — não existe: não há
como listar as atividades em `erro`, nem pela API nem pela tela.

**Pedido** — acrescentar ao `ActivityFilter`:

```python
google_calendar_sync_status = django_filters.ChoiceFilter(
    choices=GOOGLE_CALENDAR_SYNC_STATUS_CHOICES  # já definido em models/activity.py
)
```

e a chave em `Meta.fields`. Prioridade baixa: não bloqueia critério nenhum da
#133, o aviso agregado atende o que a issue pede. É o que falta para o aviso
ser acionável.

---

## 5. Observação sobre o throttle do conector Power BI — sem pedido de mudança

`PowerBIServiceTokenThrottle.get_cache_key`
(`backend/apps/core/throttling.py:79`) monta a chave com `request.auth`, que a
autenticação preenche com a **string constante** `"power-bi-service"`. Ou seja:
o limite de `POWER_BI_RATE_LIMIT` (100/hora no default) é um balde único, não um
balde por token.

Como o model garante no máximo um token ativo
(`uniq_power_bi_token_ativo`), na prática dá no mesmo — não é bug. Duas
consequências que valem estar escritas:

- o `POWER_BI_SERVICE_TOKEN` de emergência (canal secundário em
  `PowerBIServiceTokenAuthentication`) divide a cota com o token da tela;
- rodar `e2e/power-bi.spec.ts` contra um ambiente compartilhado consome a cota
  do conector real daquele ambiente. São 4 chamadas por execução; em
  homologação, convém saber disso antes.

---

## 6. Nenhum perfil pode ter acesso ao SGP sem ler Saúde/Cor-Raça

*Estado atual:* os dois conjuntos são **idênticos**.

```python
# backend/apps/sgp/views/__init__.py:67
UPF_ACCESS_ROLES = ("super-admin", "ugp", "articulador-estadual", "adt-acr")

# backend/apps/core/sensitive_fields.py:21
SENSITIVE_FIELD_ROLES = {
    "saude":    {"super-admin", "ugp", "articulador-estadual", "adt-acr"},
    "cor_raca": {"super-admin", "ugp", "articulador-estadual", "adt-acr"},
}
```

Consequência: **não existe, nem pode existir, usuário que abra a ficha de uma
UPF e não leia os campos sensíveis.** Quem está fora da matriz está fora do
módulo. Verificado com o único perfil seedado de fora, o `fgd`:

```
GET /api/v1/upfs/                         → {"detail":"Você não tem acesso ao módulo SGP."}
GET /api/v1/sgp/upfs/80/membros/exportar/ → 404 (a UPF não entra no queryset dele)
```

Isto **não é falta de usuário no seed** — foi assim que o item 5 da sprint 8
descreveu o sintoma, e por isso vale corrigir o registro. Nenhum usuário novo
resolve enquanto as duas matrizes coincidirem.

**O que atinge:**

- **#192 (ocultar Saúde e Cor/Raça por perfil)** — aqui o critério *é* a
  diferença de comportamento entre perfis. Não há como demonstrá-la, nem por
  E2E nem manualmente: o recorte existe no código e é inalcançável em runtime.
  Este é o item a resolver **antes** de tentar fechar a #192.
- **#191, segundo teste** — o E2E do frontend fixa a resposta sem a coluna
  (`membros.spec.ts`, "arquivo sem a coluna de Saúde"), e a omissão em si já
  está provada no backend por
  `test_membro_export.py::test_usuario_sem_permissao_de_saude_recebe_csv_sem_a_coluna`
  — que precisa de `monkeypatch.setitem(sf.SENSITIVE_FIELD_ROLES, ...)`, ou
  seja, esbarra na mesma parede. A #191 fecha assim; a #192 não.

**Pedido:** decidir a política. O candidato natural é tirar o `adt-acr` de uma
das duas chaves (ou de ambas) — é o perfil de campo, e o único dos quatro que
não é coordenação. Mas é decisão de vocês com a coordenação do PDHC, não
sugestão técnica do frontend: o comentário na própria matriz diz que ela deve
ser ajustada "conforme a política de acesso do PDHC evoluir".

---

## 7. `Content-Disposition` não é exposto via CORS

*Estado atual:* `CORS_ALLOWED_ORIGINS` está configurado em
`backend/setup/settings.py:273`, mas não há `CORS_EXPOSE_HEADERS`.

Sem isso o navegador **não deixa o JavaScript ler o `Content-Disposition`**,
mesmo quando o Django o envia. Toda exportação da aplicação cai no nome
derivado no cliente, e o nome que o backend escolheu é descartado. Já vale para
a exportação do Plano de Trabalho (está comentado em `e2e/exportacao.spec.ts`)
e agora para a de membros (#191).

O efeito visível é pequeno — muda só o separador entre data e hora
(`membros_upf_41_2026-09-04-17-38-40.csv` do cliente contra
`..._2026-09-04_17-38-40.csv` do servidor) —, mas a duplicação de regra de
nomeação é permanente enquanto isso não mudar.

**Pedido** — uma linha em `settings.py`:

```python
CORS_EXPOSE_HEADERS = ["Content-Disposition"]
```

O frontend não precisa mudar: `exportarMembrosCsv` e o export do Plano de
Trabalho já leem o header e só usam o fallback quando ele não vem.

---

## Resumo — situação do documento da sprint 8

| # (sprint 8) | Item | Situação em 04/09/2026 |
|---|---|---|
| 1 | `respondente_isnull` no `FormResponseFilter` | **Resolvido** — PR #214 na `main` |
| 2 | BE-25 (#187), omitir `saude`/`cor_raca` por perfil | **Resolvido** — PR #213 na `main` |
| 3 | Admin do token Power BI | **Resolvido** — PR #215 na `main`; nomes divergentes tratados no item 3 acima |
| 4 | `GET .../membros/exportar/` | **Resolvido** — PR #213 na `main` |
| 5 | Seed sem `FormResponse` / `MembroFamilia` sensível | **Parcial** — o seed passou a criar `FormResponse`; os `test.fixme` de `formularios.spec.ts` não foram reavaliados nesta sprint. Some-se a isto o item 2 acima |
| 6 | Bug UTC | **Resolvido** nas duas pontas — PR #212 |
| 7 | UGP fora do `ConflictLogViewSet` | **Resolvido** — PR #213 na `main` |
| 8 | `GET /api/v1/sca/tecnicos/` | **Resolvido** — PR #217 na `main` |
| 9 | `GET .../formularios/opcoes/` | **Resolvido** — PR #214 na `main` |

A BE-4 (status agregado do Google Calendar), que travava os testes da #133,
entrou pela PR #216 (issue #210) e não constava daquele documento.
