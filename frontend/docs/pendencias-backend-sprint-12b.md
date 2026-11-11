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

*Estado atual no frontend:* ao filtrar categoria, `listUsers` percorre todas as páginas do recorte atual, filtra os perfis e pagina o resultado no cliente. Assim a lista e a contagem ficam corretas, mas o custo cresce com o número de usuários. Quando o backend aceitar `categoria`, substituir essa leitura completa pelo filtro e pela paginação do servidor.
