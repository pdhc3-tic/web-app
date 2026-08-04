# Testes — Formulário de Atividade (FE-SGP)

O frontend ainda não tem infra de teste (sem Playwright, Vitest, Jest ou Testing
Library no `package.json`). Este documento especifica os 5 testes exigidos pelo
ticket para que possam ser implementados assim que a infra existir.

## Infra necessária

| Teste | Ferramenta |
|---|---|
| E2E 1, 2, 3 e acessibilidade | `@playwright/test` |
| Componente (busca de Ação do PT) | `vitest` + `@testing-library/react` + `jsdom` |

O E2E precisa de um usuário semeado com perfil que enxergue o SGP, ao menos uma
`WorkPlanAcao`, um `Municipality` com `territory` e uma UPF ativa com membros.

## Seletores estáveis

Os ids dos campos vêm de `fieldId()` em [`_components/formModel.ts`](./_components/formModel.ts) —
`atividade-<campo com hífen>`:

```
#atividade-titulo              #atividade-data-inicio
#atividade-tipo-atividade      #atividade-data-fim
#atividade-acao                #atividade-upfs-participantes
#atividade-forma-atuacao       #atividade-total-participantes
#atividade-tecnico-responsavel #atividade-descricao-narrativa
#atividade-municipio           #atividade-status
#atividade-ambito              #atividade-justificativa
```

O toast expõe `[data-testid="toast"]` com `data-variant="success" | "error"`.

---

## 1. E2E — preencher os obrigatórios e salvar

**Estado:** logado, em `/sgp/atividades/nova`.

1. Preencher `#atividade-titulo`.
2. Selecionar Tipo de atividade e Forma de atuação (`role=combobox` → `role=option`).
3. Digitar no `#atividade-acao` o número de uma ação semeada e escolher a opção.
4. Selecionar Estado, depois Município (o município só habilita após o estado) e Âmbito.
5. Preencher datas de início e fim.
6. Preencher `#atividade-descricao-narrativa`.
7. Clicar em **Salvar**.

**Esperado:** toast `Atividade salva.` com `data-variant="success"`, e a URL passa
a `/sgp/atividades/<id>/editar/`.

> ⚠️ O critério original diz "atividade aparece na listagem". A tela de listagem
> não existe (decisão do ticket: só o formulário), então a asserção aqui é o
> redirect para a edição. Quando a listagem existir, estender para navegar até
> ela e conferir o título e o status.

## 2. E2E — submit bloqueado sem campo obrigatório

**Estado:** logado, em `/sgp/atividades/nova`, formulário vazio.

1. Clicar em **Salvar**.

**Esperado:**
- Nenhuma requisição `POST /api/v1/sgp/atividades/` é disparada (interceptar com `page.route`).
- Alerta global "Corrija os campos destacados e tente novamente." visível.
- `#atividade-titulo` tem `aria-invalid="true"` e mensagem "Informe o título da atividade."
- O foco está em `#atividade-titulo` (primeiro campo com erro na ordem de `FIELD_ORDER`).

## 3. E2E — status "Cancelada" exige justificativa

> ⚠️ **Este teste só é válido em modo edição.** O `ActivityDetailSerializer`
> aceita apenas `planejado` e `agendado` na criação, então o formulário de
> criação nem oferece "Cancelada". Ver a nota sobre o motor de status abaixo.

**Estado:** logado, editando uma atividade cujo status atual permita transição
para `cancelada` (qualquer um dos não terminais: planejado, agendado,
em_andamento, adiada).

1. Abrir `/sgp/atividades/<id>/editar/`.
2. Selecionar **Cancelada** em `#atividade-status`.
3. Verificar que `#atividade-justificativa` apareceu (não existe no DOM com outros status).
4. Clicar em **Salvar** com a justificativa vazia.
   **Esperado:** erro "Justificativa é obrigatória quando o status é Não realizada
   ou Cancelada." e nenhum `PATCH` disparado.
5. Preencher a justificativa e salvar de novo.
   **Esperado:** toast `Atividade salva.` com `data-variant="success"`.

## 4. Componente — busca de "Ação do PT" filtra por termo

Alvo: `filterAcoes` e `AcaoCombobox` em [`_components/AcaoCombobox.tsx`](./_components/AcaoCombobox.tsx).

`filterAcoes` é exportada justamente para ser testada sem montar o componente:

```ts
const acoes = [
  { id: 1, meta: 1, numero: "1.1", descricao: "Construção de cisternas" },
  { id: 2, meta: 1, numero: "1.2", descricao: "Construção de poços" },
  { id: 3, meta: 2, numero: "2.1", descricao: "Oficina de manejo de água" },
];

filterAcoes(acoes, "poço")     // → [2]  (ignora acento)
filterAcoes(acoes, "CONSTRU")  // → [1, 2]  (ignora caixa)
filterAcoes(acoes, "2.1")      // → [3]  (casa pelo número)
filterAcoes(acoes, "1.2 poc")  // → [2]  (todos os termos precisam casar)
filterAcoes(acoes, "")         // → todos
filterAcoes(acoes, "xyz")      // → []
```

No componente montado: digitar no `role=combobox` e conferir que a `role=listbox`
mostra só as opções correspondentes, e "Nenhuma ação encontrada." quando vazio.

## 5. Acessibilidade — navegação por teclado

**Estado:** logado, em `/sgp/atividades/nova`, foco no início do formulário.

Percorrer com `Tab` e conferir que a ordem alcança, sem armadilhas de foco:

```
titulo → tipo_atividade → forma_atuacao → acao → tecnico_responsavel →
equipe_adicional → estado → município → comunidade → âmbito → GPS →
latitude → longitude → data_inicio → data_fim → busca de UPFs →
parceiros → descricao_narrativa → resultados_alcancados → status →
[justificativa, se visível] → Cancelar → Salvar
```

Verificar também:
- Todo campo tem nome acessível (`getByRole(...).and(hasAccessibleName())`).
- Os comboboxes abrem com `ArrowDown`/`Enter`, navegam com as setas, selecionam
  com `Enter` e fecham com `Escape` devolvendo o foco ao gatilho.
- Mensagens de erro são associadas via `aria-errormessage` e o campo recebe
  `aria-invalid="true"`.
- O toast de sucesso é `role="status"` e o de erro `role="alert"`.

Vale rodar `@axe-core/playwright` na página para pegar regressões de contraste e
rotulagem de brinde.

---

## Notas de contrato com o backend

Descobertas ao implementar; valem para escrever os testes e para o time do back.

1. **Motor de status.** `ActivityDetailSerializer._validate_status_transition()`
   só aceita `planejado` e `agendado` na criação, e na edição só as transições de
   `STATUS_TRANSITIONS`. O formulário reflete isso: no modo criação o select traz
   apenas os dois status iniciais; na edição, o status atual mais o que vier em
   `transicoes_permitidas` na resposta da API.

2. **`concluido` exige evidência.** O serializer recusa a transição para
   `concluido` sem foto ou documento vinculado. O formulário não gerencia
   evidências (outro ticket), então esse erro chega como erro de campo do backend
   e cai no toast de erro — comportamento correto, mas o usuário só descobre ao
   salvar.

3. **Busca de Ação do PT é client-side.** O `WorkPlanAcaoViewSet` não tem
   `SearchFilter` nem filtro `q`, então `listAcoes()` carrega a lista inteira
   (paginando de 200 em 200, teto de 10 páginas) e o combobox filtra em memória.
   **Sugestão ao back:** adicionar `filter_backends = [SearchFilter]` com
   `search_fields = ["numero", "descricao"]` no `WorkPlanAcaoViewSet`; aí a busca
   passa para o servidor e o teto de páginas some.

4. **Listagem de usuários é restrita.** O `UserViewSet` é `IsSuperAdmin`, então
   `GET /api/v1/users/` retorna 403 para ADT/ACR e articuladores — exatamente
   quem registra atividades. Hoje o formulário degrada: o responsável cai para o
   usuário logado e a equipe adicional fica desabilitada com aviso.
   **Sugestão ao back:** expor um endpoint enxuto de técnicos (id + nome) visível
   a quem tem acesso ao SGP, filtrado pelo escopo territorial do usuário.

5. **Participantes vêm só como ids.** `upfs_participantes` e
   `membros_participantes` são arrays de PK na leitura, sem nome. O formulário
   resolve as UPFs com um `GET /api/v1/upfs/{id}/` por item, e os membros são
   reconciliados quando a lista de membros de cada UPF carrega.
   **Sugestão ao back:** devolver `[{id, nome}]` no `to_representation`, como já é
   feito com `municipio`, `acao` e `tecnico_responsavel`.
