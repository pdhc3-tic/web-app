# Pendências de backend — sprint 12b

*Compilado em 10/11/2026, na branch `frontend/sprint-12b`.*

*Os itens deste documento vão para uma issue de backend nova, aberta junto do PR da `frontend/sprint-12b`.*

*Os documentos das sprints anteriores continuam valendo para o que está lá. O da 12a já virou a #419.*

---

## 1. Datas do período na listagem de limites (#400)

A tela de limites mostra e navega pelo período dos limites ("4º trimestre de 2026", com setas para o anterior e o seguinte). `GET /sgp/orcamento/limites/?data=` devolve as linhas vigentes na data, mas não diz qual é o período. O padrão do perfil nem tem período próprio: vale de quando foi criado até `2099-12-31`.

Para não pedir uma rota nova só para isso, o front lê `budget_limit_period` em `/system-config/` e calcula as datas com a mesma conta de `periodo_de` (`apps/sgp/budget/limites.py`): blocos de 1, 3 ou 6 meses a partir de janeiro, ou o período único da vigência. É uma cópia da regra. Se o backend mudar o cálculo, por exemplo quando a vigência passar a vir da entidade do TED, a tela fica errada sem aviso.

**Pedido:** a listagem devolver o período que usou. Duas formas servem:
- envelopar a resposta como `{periodo: {inicio, fim}, results: [...]}`;
- ou criar `GET /sgp/orcamento/limites/periodo/?data=`, que devolve `{inicio, fim, periodicidade}`.

*Estado atual no frontend:* `periodoDe` em `app/lib/limites.ts`, com teste de unidade. Quando o backend devolver o período, a função sai e a tela usa o que vier.

## 2. Busca de pessoas para a sobrescrita individual (#400)

A sobrescrita individual pede a pessoa. `/users/` é só do Super Admin, e a UGP também cria sobrescritas. Por isso a tela usa `/sgd/opcoes/usuarios/?papel=solicitante`, que a UGP acessa, mas que traz só os ADT/ACR ativos.

O backend aceita limite individual para os dois perfis operacionais (`PERFIS_OPERACIONAIS = adt-acr, articulador-estadual`). Pela tela, o Articulador Estadual não pode receber uma sobrescrita. Hoje isso não muda nada na prática, porque só o ADT cria demanda e reserva no limite. Mas o contrato do backend é mais amplo do que a tela permite.

**Pedido:** uma lista das pessoas com perfil operacional, acessível a UGP e Super Admin. Pode ser `GET /sgp/orcamento/limites/pessoas/?q=` ou um `papel=operacional` em `/sgd/opcoes/usuarios/`. Ela deve devolver `id`, `nome` e o perfil, para a tela mostrar "ADT" ou "Articulador" ao lado do nome.

*Estado atual no frontend:* a busca usa a lista de solicitantes. Quando a rota existir, só a fonte da lista muda.

## 3. Filtro da listagem de usuários por categoria de perfil (#405)

A #405 pede que a listagem de usuários possa ser filtrada por categoria de perfil (principal ou operacional). O `UserFilter` de `GET /users/` aceita `perfil` (um id), `territorio`, `ativo` e as datas, mas não a categoria. `GET /roles/?categoria=` existe, só que filtra perfis, não usuários.

Sem o filtro no servidor, a tela não tem como recortar a lista inteira: ela é paginada, e filtrar só a página carregada deixaria a contagem e a paginação erradas.

**Pedido:** aceitar `?categoria=principal|operacional` em `GET /users/`, devolvendo quem tem ao menos um perfil da categoria (`profiles__perfil__categoria`, com `distinct`).

*Estado atual no frontend:* o filtro "Categoria de perfil" existe e recorta as opções do filtro "Perfil" à categoria escolhida; a lista só muda quando o perfil é escolhido, e a tela avisa isso. Quando o backend aceitar `categoria`, a tela passa a enviá-la em `listUsers` e a lista filtra só pela categoria.

## 4. Justificativa obrigatória na simulação do remanejamento (#402)

A #402 pede que, ao preencher origem, destino e valor, a tela chame o simulador e mostre o antes e depois. Mas `POST /sgp/orcamento/remanejamentos/simular/` usa o mesmo `RemanejamentoCreateSerializer` da confirmação, e esse serializer exige `justificativa`. A simulação não grava nada, então a justificativa não tem uso nela.

Por isso a tela pede os quatro campos e só simula no clique em **Simular**. Simular sozinho exigiria a justificativa antes de a pessoa ver o impacto, ou mandaria um texto falso só para passar na validação.

**Pedido:** a simulação aceitar o payload sem `justificativa`, com um serializer próprio de origem, destino e valor. A confirmação continua exigindo a justificativa.

*Estado atual no frontend:* o botão **Simular** só habilita com os quatro campos preenchidos. Quando a simulação dispensar a justificativa, a tela pode simular sozinha, com um pequeno atraso, assim que origem, destino e valor estiverem preenchidos, e pedir a justificativa só para confirmar.

## 5. Alvo do alerta orçamentário (#403)

O painel de alertas mostra o que cada alerta aponta. `BudgetAlertSerializer` devolve só `escopo`, `referencia_id` e a rubrica, e o backend gera alertas de pool (semáforo em qualquer nível; subexecução e remanejamento excessivo no nacional) e de limite individual. A tela fica com "Pool · Diárias" ou "Limite de gasto · Diárias". A UGP e o Super Admin veem os alertas de todos os estados e territórios, então aparecem linhas iguais, sem como saber qual pool estourou ou de quem é o limite.

**Pedido:** o serializer devolver a identificação do alvo, por exemplo:
- `alvo_nome`: "Nacional", o nome do estado ou o do território, no pool; o nome da pessoa, no limite;
- ou um objeto `alvo` com `nivel`, `estado{sigla, nome}` e `territorio{id, nome}` no pool, e `usuario{id, nome}` no limite.

*Estado atual no frontend:* `alvoDoAlerta` em `app/lib/alertasOrcamento.ts` monta "Pool · Diárias" com o escopo e a rubrica. A tela não cruza o `referencia_id` com o painel nem com os limites. Quando o campo existir, ele entra no lugar do escopo.

## 6. Validação das opções e faixas dos parâmetros do orçamento (#403)

`PATCH /system-config/{chave}/` valida só o tipo: inteiro ou booleano. `budget_limit_period` é do tipo texto e aceita qualquer valor; um valor fora de mensal, trimestral, semestral e vigência faz `periodo_de` cair em trimestral sem aviso. Os inteiros aceitam zero, negativos e qualquer tamanho: `budget_subexec_min_pct` em 0 desliga o alerta de subexecução, e `budget_transfer_alert_pct` negativo dispara o de remanejamento em todo pool.

A tela confere antes de enviar, com faixas que o front definiu por conta própria:

| Parâmetro | Faixa na tela |
|---|---|
| `budget_limit_period` | mensal, trimestral, semestral, vigencia |
| `budget_subexec_alert_months` | 1 a 24 meses |
| `budget_subexec_min_pct` | 1 a 100% |
| `budget_transfer_alert_pct` | 1 a 100% |

**Pedido:** o backend validar cada chave `budget_*` na escrita, com as opções e faixas que a regra de negócio aceita, e devolver 400 no campo `valor`. Se as faixas forem outras, o front segue as do backend.

*Estado atual no frontend:* `validarParametro` em `app/lib/parametrosOrcamento.ts`. Sem a validação no servidor, outro cliente da API grava qualquer valor.

## 7. Filtro de riscos de glosa em aberto (#404)

A ficha da atividade mostra o bloco "Riscos de glosa" só com os riscos em aberto, e o total exposto deles. `GET /sgp/glosa-riscos/` filtra por `activity`, `demanda`, `tipo` e `severidade`, mas não pelo estado do risco. A rota devolve abertos e resolvidos juntos, paginados, e não traz total.

**Pedido:** aceitar `?aberto=true|false` em `GlosaRiskQuerySerializer` (`resolvido_em__isnull`). Se a ficha também for mostrar o total exposto, devolvê-lo junto da listagem (ex.: `total_exposto` no envelope da paginação), para o front não somar.

*Estado atual no frontend:* `listRiscosDeGlosaDaAtividade` pede uma página de 100 da atividade, e a ficha descarta os resolvidos (`riscosAbertos`) e soma o exposto (`totalExposto`). Uma atividade com mais de 100 riscos teria a lista cortada. Quando o filtro existir, a tela pede só os abertos e usa o total do servidor.

## 8. Tipo de objeto dos perfis operacionais em `/roles/` (#405)

O cadastro de usuário pede o objeto de cada perfil operacional e manda `objeto_tipo` no `perfis_input`. O backend confere o tipo contra `OBJETO_DO_PERFIL_OPERACIONAL` (`apps/core/models/user_profile.py`), mas `RoleSerializer` devolve só `categoria`, sem o tipo. O front mantém uma cópia do mapa (coordenador-evento e credenciador → evento, avaliador-selecao → candidatura, gestor-edital → edital). Um perfil operacional novo, ou um tipo trocado no backend, faz a tela mandar o tipo errado ou nulo, e o cadastro é recusado com um erro que a pessoa não consegue corrigir.

**Pedido:** `RoleSerializer` devolver `objeto_tipo` (`evento`, `edital`, `candidatura`, ou nulo no principal).

*Estado atual no frontend:* `OBJETO_DO_PERFIL` em `app/lib/users.ts`. Quando o campo existir, a tela usa o que vier do perfil e o mapa sai.

## 9. Busca dos objetos de abrangência (#405)

A #405 pede um seletor de objeto para o perfil operacional. O backend guarda o objeto só pelo número (`objeto_tipo` + `objeto_id`, sem FK) e ainda não tem os cadastros de evento, edital e candidatura do SGE e do SGS. Não há o que listar, então a tela pede o número do objeto ("Evento (número)"), e nada confere se ele existe.

**Pedido:** quando os cadastros existirem, uma busca por tipo, acessível ao Super Admin, por exemplo `GET /core/objetos-abrangencia/?tipo=evento&q=`, devolvendo `id` e um nome para exibir. O `perfis_input` também deveria recusar um `objeto_id` que não existe.

*Estado atual no frontend:* campo de número no `NovoUsuarioForm`, e a listagem mostra o objeto pelo número ("Coordenador de evento · evento 12"). Com a busca, o campo vira um seletor e a listagem mostra o nome.
