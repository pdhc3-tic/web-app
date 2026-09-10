# Pendências de backend — sprint 9

*Compilado em 04/09/2026, na branch `frontend/sprint-9a`, ao fechar as issues
#133 (painel do Google Calendar), #143 (painel do Power BI) e #191 (exportação
de membros em CSV) contra o backend que já está na `main`. O documento da sprint anterior
(`pendencias-backend-sprint-8.md`) continua valendo para o que sobrou de lá — o
resumo no fim deste arquivo diz o que caiu e o que ficou.*

*O item 10 foi acrescentado em 08/09/2026, na branch `frontend/sprint-9c`, ao
fechar a issue #234.*

*Os itens 11 a 14 foram acrescentados em 09/09/2026, na mesma branch, ao
corrigir os apontamentos de revisão das issues #232 e #233. Nenhum deles bloqueia
a entrega — o frontend contorna os quatro —, mas os quatro deixam um critério de
aceitação sendo cumprido pela metade ou por dedução.*

Os itens 1 a 5, 7 e 10 **não bloqueiam entrega**: as telas de #133, #143 e #191
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

## 8. `GET /api/v1/metas/` devolve as Metas fora de ordem

*Acrescentado em 07/09/2026, ao testar a #230 (Painel de Orçamento) na
`frontend/sprint-9c`.*

`WorkPlanMetaViewSet` declara `ordering = ["numero"]`, e o próprio model
`WorkPlanMeta` declara `Meta.ordering = ["numero"]`. Mesmo assim a lista sai
embaralhada. São duas causas somadas:

1. `get_queryset` faz
   `annotate(_valor_total=Sum(F("acoes__quantidade_planejada") * F("acoes__valor_unitario")))`.
   O `annotate` com agregação **derruba o `ORDER BY`** do model — a SQL gerada
   não tem cláusula de ordenação nenhuma.
2. `filter_backends = [DjangoFilterBackend]` não inclui `OrderingFilter`, então
   o `ordering = ["numero"]` do viewset nunca é aplicado e o `?ordering=numero`
   que o frontend já envia é ignorado em silêncio.

No banco de demonstração o efeito é direto — a ordem devolvida é
`[4, 7, 5, 6, 2, 1, 3]`:

```python
>>> qs = WorkPlanMeta.objects.annotate(_valor_total=Sum(...)).all()
>>> list(qs.values_list("numero", flat=True))
[4, 7, 5, 6, 2, 1, 3]
>>> list(WorkPlanMeta.objects.all().values_list("numero", flat=True))
[1, 2, 3, 4, 5, 6, 7]
```

Isso vaza para **toda** tela que lista Metas, não só o painel de orçamento.

**Pedido** — qualquer um dos dois resolve:

```python
# (a) reafirmar a ordenação depois do annotate
return filter_workplan_metas_for_user(qs, user).order_by("numero")

# (b) registrar o backend de ordenação, que também faz o `?ordering=` funcionar
filter_backends = [DjangoFilterBackend, OrderingFilter]
```

*Contornado no frontend:* `metaOptions` em
`app/(protected)/sgp/orcamento/page.tsx` ordena por `numero` no cliente. É
defensivo e deve continuar mesmo depois da correção — mas as outras telas que
listam Metas não têm esse contorno.

---

## 9. `seed_demo` grava `State.nome` igual à sigla

*Acrescentado em 07/09/2026, mesma verificação da #230.*

Os sete estados do seed têm `nome == sigla`:

```python
>>> list(State.objects.values_list("sigla", "nome"))
[('AL', 'AL'), ('BA', 'BA'), ('MA', 'MA'), ('MG', 'MG'), ('PB', 'PB'), ('PE', 'PE'), ('RN', 'RN')]
```

Qualquer rótulo no padrão `{nome} ({sigla})` — usado por `fetchStateOptions` e
`fetchStateSiglaOptions`, e daí pelos selects de várias telas — sai como
`PE (PE)` em vez de `Pernambuco (PE)`. Não é bug de frontend e não aparece com
dados reais, mas atrapalha a revisão visual de qualquer tela com filtro de
estado.

**Pedido** — preencher `nome` com o nome por extenso na criação dos `State` do
`seed_demo`.

---

## 10. Sair de "Adiada" não exige nova data — a regra existe só no cliente

*Levantado em 08/09/2026, ao implementar a issue #234 (fluxo guiado de
transição de status) na branch `frontend/sprint-9c`.*

O contexto da #234 afirma que o backend já implementa *"nova data obrigatória
para sair de 'Adiada'"*. **Não implementa.** `ActivityDetailSerializer.validate`
cobre as outras três regras da máquina de estados — transição permitida,
justificativa obrigatória em `nao_realizada`/`cancelada` e bloqueio de
`concluido` sem evidência —, mas não há nenhuma validação ligando
`adiada → agendado` a uma data nova. Uma busca por `adiada` em
`backend/apps/sgp/` só encontra o rótulo do choice, a entrada em
`STATUS_TRANSITIONS` e o seed.

*Verificado na API*, contra a atividade 100 (`status="adiada"`):

```
PATCH /api/v1/sgp/atividades/100/   {"status": "agendado"}
→ 200 OK      # sem data nova, sem reclamação
```

*Estado atual no frontend:* o diálogo de transição
(`TransicaoStatusDialog.tsx`) exige a nova data e bloqueia o envio sem ela,
atendendo ao critério da issue. Mas a regra vale **apenas nesta tela** — o app
de campo (SCA), o Django admin ou um `curl` reagendam sem data e a atividade
volta a "Agendado" mantendo a data que já passou. É exatamente o que a #231
estabeleceu que não deve acontecer: *"a validação do servidor continua sendo a
autoridade; a do cliente é conveniência, nunca substituto"*.

**Pedido** — acrescentar a `ActivityDetailSerializer.validate`, junto das
regras que já moram lá:

```python
# Reagendar exige data nova: sem isto a atividade volta a "agendado"
# carregando a data que já passou, e nasce atrasada.
if (
    self.instance is not None
    and self.instance.status == "adiada"
    and novo_status == "agendado"
    and "data_inicio" not in attrs
):
    raise serializers.ValidationError({
        "data_inicio": (
            "Informe a nova data de início ao reagendar uma atividade adiada."
        ),
        "code": "VALIDATION_ERROR",
    })
```

Custo: um bloco no `validate` que já existe. Nenhum model novo, nenhuma
migration. Quando entrar, a exigência do cliente deixa de ser a única barreira
e o teste 3 de `atividade-status.spec.ts` passa a cobrir uma regra real — hoje
ele prova só o comportamento da UI.

---

## 11. `parceiros_organizacoes` chega como ids crus, e quem mais lê a ficha não pode resolvê-los

*Levantado em 09/09/2026, ao corrigir os apontamentos de revisão da issue #233
na branch `frontend/sprint-9c`.*

`ActivityDetailSerializer.to_representation` enriquece `acao`,
`tecnico_responsavel`, `equipe_adicional`, `upfs_participantes`,
`membros_participantes`, `fotos` e `documentos` — todos saem com nome. **Menos
`parceiros_organizacoes`**, que continua sendo o `PrimaryKeyRelatedField` cru:

```json
"parceiros_organizacoes": [3, 17],
"parceiros_livres": "Sindicato dos Trabalhadores Rurais de Serra Talhada"
```

Resolver esses ids por fora não é opção para quem mais abre a ficha:
`OrganizationViewSet.get_permissions` libera `list`/`retrieve` apenas a
`IsSuperAdmin | IsUGP | IsArticuladorEstadual`. O ADT/ACR — o técnico de campo,
autor da maioria das atividades — recebe **403** ao tentar `GET
/api/v1/organizations/`.

*Estado atual no frontend:* a ficha imprime `parceiros_livres` inteiro e, para o
M2M, declara a quantidade ("2 organizações parceiras cadastradas"). É o máximo
honesto com o payload de hoje: números de banco na tela não ajudam ninguém, e
omitir o vínculo esconderia informação real.

**Pedido** — uma linha em `to_representation`, no mesmo padrão de
`equipe_adicional`:

```python
data["parceiros_organizacoes"] = [
    {"id": o.pk, "nome": o.nome}
    for o in instance.parceiros_organizacoes.all()
]
```

Custo: nenhum model novo, nenhuma migration, nenhuma permissão mexida — o dado
já está no `prefetch`. Quando entrar, a ficha passa a listar os parceiros pelo
nome e o critério "ficha completa" da #233 fecha de verdade.

---

## 12. `MembroListSerializer` não devolve a UPF do membro

*Mesmo levantamento do item 11.*

O critério da #233 pede *"participantes (UPFs e membros) com link para as
respectivas fichas"*. O membro não tem rota própria — a dele é a aba de membros
da UPF (`/sgp/upfs/{id}/#membros`) —, mas o payload não diz **qual** UPF:

```python
# apps/sgp/serializers.py, MembroListSerializer.Meta.fields
["id", "nome_completo", "data_nascimento", "idade", "grau_parentesco", ...]
```

Sem `upf`, o frontend não tem como montar o link a partir do detalhe da
atividade. E o membro só é alcançável aninhado (`/sgp/upfs/{upf_pk}/membros/`),
então nem uma busca por id resolve.

*Estado atual no frontend:* a ficha resolve o vínculo por dedução. Com **uma**
UPF participante o link sai de graça — `ActivityDetailSerializer.validate`
recusa membro que não pertença às UPFs selecionadas, então o vínculo é garantido
pelo próprio contrato. Com mais de uma, a ficha cruza com `listMembros` de cada
UPF participante: **N requisições** só para descobrir a que já estava no banco.
Falhando o cruzamento, a linha volta a ser texto simples — melhor sem link do
que apontando para a ficha errada.

**Pedido** — `"upf"` em `MembroListSerializer.Meta.fields` (o FK já existe no
model e é usado em `validate_membros_participantes`). Elimina as N requisições e
torna o link determinístico.

---

## 13. `criado_por` é um id, e `/api/v1/users/` é `IsSuperAdmin`

*Mesmo levantamento do item 11.*

O critério de auditoria da ficha (#233) pede "quem criou". O detalhe devolve
`"criado_por": 12` e nada mais — e `UserViewSet` é `IsSuperAdmin`, então nenhum
perfil que abre a ficha na prática consegue trocar o id por um nome. É o mesmo
403 já anotado em `listTecnicos` (`app/lib/atividades.ts`).

*Estado atual no frontend:* a ficha procura o id entre as pessoas que ela já tem
com nome — o técnico responsável, a equipe adicional, o próprio usuário logado
—, o que cobre a grande maioria das atividades. Sem correspondência, mostra
`Usuário #12`. Dizer o id é honesto; inventar um nome, não.

**Pedido** — aninhar como já se faz com `tecnico_responsavel`:

```python
data["criado_por"] = (
    {"id": instance.criado_por.pk, "nome": instance.criado_por.nome}
    if instance.criado_por_id else None
)
```

---

## 14. 403 de "sem território" é indistinguível de 403 de "sem acesso"

*Levantado em 09/09/2026, ao corrigir os apontamentos da issue #232.*

`services/budget.py::resolver_nivel_painel` levanta `PermissionDenied` com a
**mesma** mensagem — *"Você não tem acesso ao orçamento do SGP."* — em dois
casos que pedem telas opostas:

```python
if "adt-acr" in slugs:
    territorio_ids = _territorios_do_adt(perfis)
    if not territorio_ids:
        raise PermissionDenied("Você não tem acesso ao orçamento do SGP.")   # (a)
    ...
raise PermissionDenied("Você não tem acesso ao orçamento do SGP.")           # (b)
```

(a) é um ADT sem vínculo: o critério da #232 pede *estado vazio explicativo,
sem erro*. (b) é um perfil sem acesso nenhum: pede `RestrictedAccess`. Pela
resposta é impossível separar os dois.

*Estado atual no frontend:* a tela deduz pelo perfil. Para um ADT/ACR, o 403 do
painel só pode ser (a) — a página nunca manda `estado` nem `territorio` para
esse perfil, e esses são os outros dois motivos de negativa no bloco `adt-acr`.
A dedução é sólida, mas depende de o front continuar não enviando aqueles dois
parâmetros: qualquer filtro novo para o ADT a invalida em silêncio.

**Pedido** — um `code` distinto no detalhe do 403 de (a), por exemplo
`SEM_TERRITORIO`, para o frontend ler a causa em vez de inferi-la.

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
