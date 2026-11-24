# Decisões de modelo de dados — desvios em relação à especificação

## Escopo

Este documento cataloga os pontos em que o modelo de dados implementado em
`backend/apps/sgp/models/` diverge, de forma **consciente**, do que está
especificado em `Requisitos-SGP.docx`, seção **"8. Modelo de Dados — SGP"**
(raiz do repositório, não versionado no git).

Para cada desvio: o que a especificação define, o que o código faz, por quê,
e quais as consequências práticas de manter a divergência.

**O que não entra aqui:** campos ou funcionalidades adicionados que a
especificação simplesmente não previa (ex.: integração com Google Calendar em
`Activity`, campos de endereço em `UFPA`) — isso é extensão, não desvio, já que
não há nada especificado para divergir. **O que também não entra aqui:**
qualquer coisa que pareça lacuna sem justificativa técnica — isso é tratado
como possível erro e deve virar issue própria, não uma linha deste documento
(ver seção "Observação" ao final).

---

## 1. `Activity.id` — UUID especificado vs. PK incremental + `uuid_local`

**Especificação:** `Activity` tem `id (UUID)` como chave primária.

**Implementação:** `apps/sgp/models/activity.py` — `id` é o `AutoField`
padrão do Django (inteiro autoincremental). A idempotência do sync com o app
offline SCA é resolvida por um campo **separado**, `uuid_local`
(`UUIDField`, `null=True`, `unique=True`, não é PK).

**Por quê:** uma PK sequencial tem localidade de índice muito superior a um
UUID v4 em B-tree (menos fragmentação de página, inserts e joins mais
baratos). O `uuid_local` já resolve o problema de idempotência offline que
motivava originalmente o uso de UUID como PK — não há necessidade de pagar o
custo de performance de UUID em toda FK que aponta para `Activity`.

**Consequências:** nenhuma FK para `Activity` é uma relação por UUID; toda
integração/sync externa usa `uuid_local` como identificador estável entre
dispositivo e servidor, não `id`. O mesmo padrão
(`device_id` + `uuid_local` + `ultima_origem` + `ultimo_sync_em`) foi
replicado em `UFPA` e `MembroFamilia` por consistência arquitetural, mesmo a
especificação não exigindo isso para essas duas entidades.

---

## 2. `Tecnico` como perfil adicional, não como FK de `Activity`

**Especificação:** a especificação lista `Tecnico` como entidade própria
(`id, user_id, territorio_id, osc_id, papel, ativo`).

**Implementação:** `Tecnico.user` é uma `OneToOneField` para `User` — um
perfil *adicional*, opcional. `Activity.tecnico_responsavel` continua sendo
uma FK direta para `settings.AUTH_USER_MODEL`, não para `Tecnico`.

Esta decisão já está detalhada em
[`docs/tecnico-fk-activity.md`](tecnico-fk-activity.md), incluindo a
justificativa completa (custo de migração de dados históricos, risco para o
contrato de sync do app SCA, e o fato de `Tecnico` ser opcional por natureza)
e onde isso aparece no código. Este documento não duplica esse conteúdo —
apenas referencia-o como parte da varredura completa do §8.

**Consequência direta:** desativar um `Tecnico` (`ativo=False`) não afeta
`Activity`s já registradas, já que elas não têm nenhuma FK para `Tecnico` —
apenas para `User`.

---

## 3. `UFPA` — dados pessoais do titular normalizados em `MembroFamilia`

**Especificação:** `UFPA` tem, diretamente, os campos de identificação do
titular: `nome_titular, cpf, rg, data_nasc, genero, cor_raca, nis, dap_caf,
estado_civil, escolaridade, telefone, email, ...`.

**Implementação:** os dados pessoais do titular não ficam em
`apps/sgp/models/ufpa.py`. `UFPA.titular` é uma `OneToOneField` (`PROTECT`)
para `MembroFamilia`, e é nesse model (`apps/sgp/models/membro.py`) que vivem
`nome_completo`, `cpf`, `rg`, `nis`, `data_nascimento`, `genero`, `cor_raca`,
`escolaridade` e `caf` — o titular é apenas um `MembroFamilia` como outro
qualquer, identificado via `UFPA.titular`. Dos campos de identificação que
a especificação lista, ficam na `UFPA`, por serem da unidade e não da pessoa,
`numero_dap` (exposto na API como `dap_caf`), `nis`, `celular` e `whatsapp`.

**Por quê:** evita duplicar o mesmo dado pessoal em duas tabelas (o titular
já é um membro da família, presente em `MembroFamilia.ufpa`) e mantém uma
única fonte de verdade para atualização de dados pessoais, independente de a
pessoa ser titular ou dependente.

**Consequências:** qualquer código que precise de dados pessoais do titular
de uma `UFPA` precisa navegar por `ufpa.titular.<campo>`, não `ufpa.<campo>`
diretamente. Campos que a especificação lista para `UFPA` mas que não existem
nem em `UFPA` nem em `MembroFamilia` — `estado_civil` e `email` — estão
listados na seção "Observação" abaixo, pois não há justificativa técnica
registrada para a ausência deles.

---

## 4. `MembroFamilia` — criptografia de campos sensíveis

**Especificação:** `cor_raca` e `saude_json` são campos comuns, sem menção a
tratamento especial.

**Implementação:** `apps/sgp/models/membro.py` usa `EncryptedIntChoiceField`
(`cor_raca`) e `EncryptedJSONField` (`saude`) — armazenamento criptografado
em repouso (AES-256-GCM), com leitura restrita por perfil
(`apps.core.sensitive_fields`).

**Por quê:** são dados sensíveis sob a LGPD (raça/cor e condição de saúde);
a especificação não previu esse tratamento, mas é uma decisão de segurança
necessária independentemente do que o documento de requisitos define.

**Consequências:** esses dois campos não podem ser filtrados/ordenados
diretamente em queries SQL (estão cifrados na coluna); qualquer relatório ou
exportação que precise desses valores precisa passar pela camada de
descriptografia da aplicação, respeitando o controle de acesso por perfil.

---

## 5. `ActivityUFPA` / `ActivityMember` — relação implícita do Django em vez de entidade explícita

**Especificação:** modela `ActivityUFPA` e `ActivityMember` como entidades
próprias, cada uma com `id` próprio, ligando `Activity` a `UFPA` e a
`MembroFamilia` respectivamente.

**Implementação:** `Activity.ufpas_participantes` e
`Activity.membros_participantes` são `ManyToManyField` padrão do Django, com
tabela *through* implícita (sem model Python próprio, sem `id` exposto pela
ORM).

**Por quê:** nenhuma das duas relações carrega atributos próprios (data de
participação, papel do membro na atividade, etc.) — só a associação em si.
Usar o M2M padrão do Django evita a complexidade de manter dois models extras
sem ganho funcional.

**Consequências:** se no futuro a relação precisar carregar um atributo
próprio (ex.: papel do membro na atividade), será necessário migrar para um
`through` model explícito — hoje isso exigiria uma migração de dados, não
apenas de schema, já que a tabela existe mas não é gerenciada como model.

---

## 6. `Production` — FKs tipadas em vez de referência genérica

**Especificação:** um único campo `cultura_ou_especie_id`, cujo significado é
discriminado por `tipo` (agrícola → cultura; pecuária → espécie animal).

**Implementação:** `apps/sgp/models/production.py` tem duas FKs separadas e
tipadas — `cultura` (→ `sgp.Cultura`, `PROTECT`) e `especie`
(→ `sgp.EspecieAnimal`, `PROTECT`) — ambas nullable, com a exclusividade
mútua garantida por validação em `Production.clean()` de acordo com `tipo`.

**Por quê:** uma FK genérica (um `id` que pode apontar para duas tabelas
diferentes dependendo de um discriminador) não é validável pelo banco nem
pela ORM do Django da forma nativa — abriria espaço para inconsistência
referencial (um `id` de `Cultura` sendo interpretado como `EspecieAnimal` por
erro de `tipo`, por exemplo). Duas FKs tipadas deixam o `PROTECT` e a
integridade referencial nativos do banco.

**Consequências:** qualquer leitura de "qual é a cultura/espécie desta
produção" precisa checar `tipo` e então ler `cultura` ou `especie`
(mutualmente exclusivos por validação, não por constraint de banco).

---

## 7. `WorkPlanAcao` / `WorkPlanMeta` — campos derivados calculados, não persistidos

**Especificação:** lista `valor_total`, `perc_realizado`, `status_execucao`
(em `WorkPlanAcao`) e `status_calculado` (em `WorkPlanMeta`) como campos das
respectivas entidades.

**Implementação:** `apps/sgp/models/workplan.py` só persiste
`quantidade_realizada` em `WorkPlanAcao` (materializado por signal, conforme
a issue #229). `valor_total` e `status_execucao` (em `WorkPlanAcao`) e
`status_calculado` (em `WorkPlanMeta`) são `@property` calculadas em tempo de
leitura a partir de outros campos. `perc_realizado` não existe nem como
campo nem como `@property` no model — se for exposto, é calculado fora do
model (serializer/view), o que está fora do escopo deste levantamento de
modelo de dados.

**Por quê:** `valor_total` é uma multiplicação trivial
(`quantidade_planejada × valor_unitario`) e `status_execucao`/
`status_calculado` dependem da data corrente (`timezone.localdate()`) — nenhum
dos dois precisa ser persistido, e persistir criaria risco de o valor
armazenado ficar desatualizado (ex.: `status_execucao` mudar de "no prazo"
para "em atraso" sem nenhuma escrita acontecer). Diferente de
`quantidade_realizada`, que depende de uma contagem cara (atividades
relacionadas) e por isso é materializada.

**Consequências:** `valor_total`, `status_execucao` e `status_calculado` não
podem ser filtrados/ordenados via query no banco (não são colunas) — qualquer
filtro por esses "campos" precisa ser feito em Python após a query, ou
reescrito como anotação (`annotate`) equivalente na querynet quando
necessário em listagens grandes.

---

## 8. Orçamento — padrões do Relatório de Set/2026 adotados

Registrado em 03/11/2026 por Adrian. O Relatório de Alterações lista os três
primeiros pontos como decisões em aberto, mas já traz um padrão para cada um, e os
documentos de requisitos o confirmam. Valem como decididos, sem depender de nova
resposta da coordenação. Período, sobrealocação e acúmulo são parâmetros do Core e
podem mudar por configuração.

| Questão | Decisão | Fonte |
|---|---|---|
| Periodicidade dos limites | Global, trimestral (`budget_limit_period`) | SGP 6.4; Core; Relatório, seção 9 |
| Sobrealocação | Permitida (`budget_overallocation_allowed = true`); o bloqueio efetivo continua sendo o pool | SGP 6.3; Core; Relatório, seção 9 |
| Saldo não usado | Expira no fim do período (`budget_limit_carry_over = false`) | SGP 6.4; Core; Relatório, seção 9 |
| Saldo por Meta | A Meta não tem saldo próprio: é dimensão do valor executado. Os relatórios previstos trazem saldo por rubrica, pool e território | Relatório 2.2; SGP, seção 6 |

### Escolhas de implementação sem regra nos documentos

- **Mais de um perfil:** vale o maior padrão.
- **`vigencia`:** período único e fixo, até existir a entidade do TED.
- **Padrão por perfil:** vale até ser alterado, sem precisar de novo cadastro a cada período.
- **Recurso extra:** eleva o período vigente na data da decisão. `periodo_aplicacao` é texto livre e o front não o preenche.
- **Campo do limite:** `valor_limite`, como no modelo de dados do SGP, em vez do `valor` da issue.
- **RLS:** a FGD, o nível nacional para o Articulador e a leitura dos padrões por todo usuário vão além do texto da arquitetura. Ver `orcamento.md`.
- **Padrão sem uso:** a alteração corrige o próprio registro, em vez de esperar o período seguinte, para um valor errado no cadastro não valer um trimestre inteiro. O mesmo vale em `vigencia`, que não tem período seguinte.
- **`trava: "origem"`:** o `INSUFFICIENT_BALANCE` dos remanejamentos usa esse valor, além de `individual` e `territorial`.
- **Limite individual sem padrão:** na virada, só gera linha se houver saldo a acumular. Sem nenhum dos dois, o usuário fica sem limite no período novo.
- **Django Admin:** consulta de pools; nos limites, só linhas individuais. A distribuição e os padrões por perfil têm regras que o Admin não aplicaria.
- **Diff da #387:** o critério de restringir o diff em `apps/sgd` a três arquivos não dá para cumprir, porque `balance.py`, `approval.py`, `remanejamento.py`, `reconciliacao.py`, o Admin, os seeds e a auditoria usavam os modelos removidos.

- **Check de pool territorial:** além das regras de consistência de nível, exige `estado` nulo. Sem isso, o mesmo território poderia ter dois pools. Na matriz, o `estado` da célula territorial vem do território.
- **Soma da sobrealocação:** conta só quem reserva no pool do território. O Articulador reserva no estadual e fica de fora, e território sem pool também.
- **Sobrescrita com acúmulo ligado:** vale exatamente o valor informado, sem somar o saldo anterior.
- **Justificativa do alias:** `/sgd/limites-individuais/` não recebe justificativa no contrato antigo. Ela é preenchida com um texto fixo até o front migrar.
- **`acao_sugerida` do remanejamento:** `informar_outra_origem`, além dos dois valores das travas da submissão.
- **Testes da #387:** as asserções de redução de limite mudaram para seguir o documento: reduzir preserva o comprometido. `test_estado_da_reserva_migration.py` saiu porque rodava uma migration antiga contra o modelo removido.
- **Campos do modelo de dados do SGP fora deste modelo:** `ted_versao_id` entrou com a entidade do TED (seção 13); `transfer_id` não é preciso, porque o remanejamento já referencia os dois pools; `periodicidade` e `acumula_saldo` são parâmetros globais do Core; `valor_disponivel` é calculado. `BudgetPool.atualizado_em` não existe porque toda alteração de alocação já vai para o ledger, com usuário e data. Em `BudgetRubrica`, `descricao` não é usada, e `tipo_solicitacao_sgd` vive em `TipoSolicitacao`, porque o mapeamento é configuração. `demanda_id` é referência sem FK, para o SGP não depender do SGD. `BudgetAlert` fica para a #390.

- **Acúmulo:** o saldo acumulado é debitado da linha antiga, para não existir nas duas. O que for liberado nela depois da virada expira. Só acumula a linha que termina na véspera do novo período.
- **Recurso extra em Devolvida:** com a reserva da rubrica de pé, o pedido é aceito com o valor informado, mesmo sem déficit calculado. A edição para mais é recusada e não fica gravada, e a mensagem orienta a pedir recurso extra, como manda o SGD §4.1.

- **`BudgetAlert`:** segue o modelo de dados do SGP v1.3, e não os nomes da #390 (`percentual_atingido`, em vez de `percentual`; `escopo` e `referencia_id`, em vez de FKs para pool e limite). Acrescenta `tipo` e `resolvido_em`, que o documento não tem e o critério de um alerta aberto por alvo exige, e `criado_em`, que a #390 pede: é a data imutável de criação, enquanto `alertado_em`, do documento, muda a cada nova entrada numa faixa. `faixa` fica vazia no remanejamento excessivo, que o documento não lista. Alertas por rubrica usam o pool nacional como alvo, porque o documento não tem escopo de rubrica.
- **Fim da vigência para a subexecução:** maior `data_fim` das Metas, até existir `TED.vigencia_fim`.
- **Espelho de saldo no SCA:** fotografia dos cartões de "meu saldo" gravada em `SyncDevice.espelho_saldo` a cada pull, por dispositivo. O pull devolve a mesma fotografia em `saldos`, para a consulta offline, e `GET /sca/saldo/` a devolve com `ultimo_sync`. Uma movimentação depois do sync só aparece no pull seguinte.
- **Falha ao gerar o espelho:** o pull não cai. Devolve `saldos: null`, para o app manter o que tem, e `GET /sca/saldo/` segue com a fotografia anterior e a data dela (`espelho_saldo_em`).
- **Aviso de semáforo:** a cada nova entrada numa faixa, como o SGP §6.8 pede, inclusive de vermelho para amarelo. Voltar ao verde resolve o alerta sem notificar. Limite de período encerrado não alerta.
- **Pool em estado sem Articulador:** o aviso vai à UGP, tanto o de semáforo quanto o de remanejamento efetivado, para não ficar sem destinatário.
- **Rubrica inativa em "meu saldo" e no espelho do SCA:** aparece só para quem tem limite vigente e já movimentou nela, porque o SGP §6.2 mantém o saldo executado e o histórico. `rubrica_ativa: false` avisa que o `disponivel` não pode ser usado em nova demanda.
- **Extrato de "meu saldo":** por padrão, o período vigente, cuja soma é o `disponivel`; `?historico=true` traz os encerrados. Limite só herdado do padrão ainda não tem lançamento, então o extrato vem vazio com o `disponivel` igual ao padrão.
- **Periodicidade "vigência" em "meu saldo":** `periodo_fim` e `dias_restantes` usam o fim da vigência, e vêm nulos sem Metas.
- **Alertas para a FGD:** a matriz de perfis do Core dá à FGD leitura de pools e nada em limites de gasto, então `/orcamento/alertas/` mostra os pools e só o limite dela. O RLS segue listando a FGD como global porque ela conclui demandas.
- **Simulador obrigatório:** o SGP RF39 pede a simulação antes de confirmar. O backend oferece a rota e não a exige; a confirmação em duas etapas fica na tela.
- **Remanejamento excessivo:** o evento não está na tabela do Core. Vai à UGP por e-mail e in-app, como a subexecução.
- **Semáforo em Meta, Submeta e Ação:** o SGP §6.8 os inclui, mas a #390 cobre pool e limite. Os valores `meta`, `submeta` e `acao` de `escopo` e `devolucao` de `faixa` existem no modelo e ainda não são gerados.
- **Pools de nível superior no semáforo:** a reserva territorial não sobe para os pools estadual e nacional, então eles só refletem o que foi reservado neles. É o mesmo cálculo do painel.
- **Faixa do semáforo:** segue o percentual comprometido, como o SGP §6.8 define, sem somar o executado. Um limite de 1000 com 950 executados fica verde com 50 disponíveis.
- **Fora de "meu saldo":** "demandas em trânsito" e "ações rápidas" do SGP §6.5. A tela compõe com `GET /sgd/demandas/`, porque o motor não importa `apps.sgd`.
- **Templates de notificação:** o catálogo com `{{rubrica}}` e `{{saldo_disponivel}}` fica em `alertas.py`. Os templates editáveis pelo Super Admin do Core §4.2 ainda não existem.
- **Rodada diária de `check_budget_thresholds`:** além de rodar após cada movimentação, como a Arquitetura pede, roda uma vez por dia para cobrir mudança de parâmetro e fim de período.

### Divergências do documento mantidas, para a coordenação confirmar

- **Remanejamento entre rubricas:** o SGP 6.7 permite, e o motor só aceita a mesma rubrica, como já fazia, e o simulador segue a mesma regra. Os demais tipos do SGP 6.7 não existem no motor.
- **Exatos 90% de comprometimento:** o SGP 6.8 diz amarelo até 90%; o código, como a #373, trata 90% como vermelho.
- **`reserva_ugp`:** com um pool por rubrica e nível, uma rubrica nacional não pode, ao mesmo tempo, ser reserva da UGP e distribuir aos estados.

Sem resposta nos documentos, com o comportamento atual:

- **Recurso extra na virada:** a elevação vale para o período da decisão. Aprovado em 30/12 e submetido em 2/1, a linha nova vem do padrão, e a demanda volta a ser barrada.
- **Sobrescrita com datas próprias:** o padrão vale inteiro no restante do período. Uma sobrescrita de 200 no início do trimestre, com padrão de 1.000, dá 1.200 no trimestre.
- **Acúmulo com a sobrealocação desligada:** a linha gerada não confere o pool, e a soma dos limites pode passar dele. O bloqueio efetivo continua sendo o pool.
- **Quem não reservou no período:** não tem linha e não acumula, embora o padrão não tenha sido usado.

**Em aberto com a coordenação:** os valores iniciais dos limites por perfil e rubrica e se
ADT e ACR precisam de valores diferentes. Hoje os dois são um só perfil no sistema.

---

## 9. Custo da atividade e risco de glosa — o documento prevalece sobre a #391

- **`custo_previsto`:** soma o estimado das demandas ainda não concluídas, como o SGP 3.1 define, e também exclui canceladas e recusadas, como a #391 pede. A #391 incluía as concluídas.
- **`custo_realizado`:** soma o valor executado das demandas concluídas, como o SGP 3.1 define, e não o pago. Pago acima do autorizado executa só o autorizado, e a diferença fica no risco de glosa.
- **Cálculo:** feito na leitura, com visão total. O RLS de `sgd_demand` mostra ao ADT só as próprias demandas, e o custo da mesma atividade mudaria conforme quem lê. Não há colunas materializadas em `Activity`, porque recalcular a soma exigiria travar a atividade a cada mudança de solicitação.
- **Severidade de `pago_acima_autorizado`:** alta, como o SGP 7.5 define para a divergência entre autorizado e pago, inclusive nos registros migrados. A #391 pedia média.
- **Nomes no modelo:** seguem o SGP 10.3 (`tipo_situacao`, `entidade`, `entidade_id`, `detectado_em`, `resolvido_em`, `resolvido_por`). `activity`, `demanda_id`, `demand_request_id`, `valor_autorizado` e `valor_pago` são acréscimos para a #391 e a #408.
- **Nomes na API:** o documento não define a rota, então ela segue a #391 e a #408: `tipo`, `activity_id` e `criado_em`.
- **Quando registra `demanda_sem_evidencia`:** com a demanda concluída e a atividade em `concluido_sem_evidencia`, em qualquer ordem. Demanda concluída com a atividade ainda em andamento não é risco até a atividade fechar sem evidência. O registro acontece no próprio salvamento, sem tarefa, porque o status é terminal e não haveria outra chance se o broker estivesse fora. A conclusão trava a atividade, para que as duas ordens se enxerguem mesmo quando acontecem juntas.
- **Situações detectadas:** só 2 das 8 do SGP 7.5; as demais e o relatório semanal ficam para a sprint do TED.
- **Quem lê `/sgp/glosa-riscos/`:** UGP, Super Admin, FGD e Articulador, como o SGP 7.5 define para o relatório. O ADT recebe 403. O Articulador continua vendo o risco de atividade inativa, porque inativar não desfaz a despesa.

---

## 10. Perfis operacionais — regras além da #393

- **Trigger em vez de `CheckConstraint` para a categoria:** um CHECK não enxerga `core_role`. O CHECK garante que `objeto_tipo` e `objeto_id` vêm juntos, e a trigger, que objeto só existe em perfil operacional, que todo operacional tem objeto e que ele não tem território.
- **Sem território:** a abrangência é o objeto, como o Core define. Com território, o perfil operacional ampliaria o escopo territorial de quem o recebe, porque as regras de escopo somam os territórios de todos os perfis do usuário.
- **Sempre com um perfil principal:** o Core diz "nunca isolados". `perfis_input` recusa operacional sozinho. Pelo Admin ainda é possível apagar o principal, e por isso `user_territories`, `/users/`, `/auth/me/` e o filtro de dispositivos do SCA não contam perfil operacional como acesso global.
- **Objeto de cada perfil:** Coordenador de Evento e Credenciador em `evento`, Avaliador de Seleção em `candidatura` e Gestor de Edital em `edital`. O Credenciador também abrange sessões no Core, mas sessão ainda não existe como objeto.
- **`objeto_id` sem FK:** `apps/sge` e `apps/sgs` ainda não têm modelos.
- **Listagens:** `/users/` e `/auth/me/` trazem o objeto de cada perfil e o perfil principal primeiro, porque a barra lateral do front usa `perfis[0]`.
- **Sem designação repetida:** cada usuário tem no máximo uma linha por perfil e objeto. O mesmo perfil pode valer para vários objetos, uma linha para cada.
- **`categoria` só de leitura:** na API e no Admin, porque mudar a categoria de um perfil em uso deixaria os vínculos dele inconsistentes.
- **Escrita em `/roles/` só para o Super Admin, com `slug` imutável:** a matriz do Core dá a configuração ao Super Admin. Antes, qualquer autenticado podia alterar perfis; com perfis sem vínculo, dava para apagar um deles e trocar os slugs até virar Super Admin.
- **Busca de Articulador por estado:** o território precisa ser o do próprio perfil de Articulador. Sem isso, o perfil operacional, que não tem território, valeria como alcance global.

---

## 11. Renomeação de UPF para UFPA — o que a #392 não cobre ao pé da letra

- **Rotas:** a canônica é `/api/v1/sgp/ufpas/…`, como a Arquitetura define. `/api/v1/sgp/upfs/…` e `/api/v1/upfs/…` ficam por um ciclo, com o cabeçalho `Deprecation: true`; a #392 cita só a primeira, mas a segunda é a que o front mais usa. Os três prefixos respondem todas as rotas aninhadas, inclusive as que antes existiam só em um deles. O schema descreve só a canônica, e o CORS expõe `Deprecation` e `Link` ao front.
- **JSON e contrato do SCA:** também mudam, sem alias, e o front precisa da #407. O app do SCA ainda não consome essas rotas.
- **RLS em `sgp_ufpa`:** não existia política em `sgp_upf` para recriar. A política foi entregue na #425, descrita na seção 12.
- **Índice `(cpf)`:** o CPF fica em `MembroFamilia`, como descrito na seção 3, e o índice já existe lá.
- **Índices automáticos do Django:** os criados por FK e `unique` (`sgp_upf_municipio_id_...`) mantêm o nome de origem, sem efeito no funcionamento. Os nomeados no modelo (`idx_ufpa_*`) foram recriados.
- **Auditoria gravada:** o `AuditLog` é imutável, então o histórico da UFPA lê `UFPA` e `UPF`, e o filtro `entidade` de `/audit-logs/` traz o nome antigo junto: `UFPA` com `UPF`, `UFPADocument` com `UPFDocument`. As chaves dentro de registros antigos, como `upf_id`, ficam como foram gravadas.
- **Permissões do Django:** a migration renomeia `add_upf`, `change_upf` e as demais para `*_ufpa` (e as de `UPFDocument`), mantendo grupos e usuários que já as tinham. Se a permissão com o nome novo já existir, a antiga fica como está.
- **Arquivos já enviados:** a chave gravada continua válida; só upload novo usa `ufpas/`. A confirmação da foto e do documento aceita também `upfs/`, para a URL de upload emitida antes do deploy e confirmada depois.
- **Chaves antigas na escrita:** `upfs_participantes` e `daf_caf` respondem 400 durante o ciclo. Como o DRF ignora chave desconhecida, sem isso o front ainda não migrado receberia sucesso e perderia o dado.
- **`dap_caf`:** o campo `daf_caf` da API passa a se chamar como no SGP 10.1 e no Relatório. O nome do modelo continua `numero_dap`.
- **Critério do `grep` da #392:** além das migrations antigas e dos aliases, ele acha o que trata o nome antigo de propósito: `NOMES_DA_ENTIDADE`, a recusa das chaves antigas, `ROTAS_DEPRECIADAS`, a confirmação de upload com `upfs/` e os testes disso.
- **`AlterModelTable`:** não foi preciso: `RenameModel` já move as tabelas, e `AlterField(db_table=...)` leva a M2M a `sgp_activityufpa`.
- **Conflitos do SCA:** a migration troca `entidade` e `campo`, porque o `campo` volta ao objeto na resolução. Os valores dentro de `valor_local` e `valor_servidor` e os detalhes de erro de `SyncEvent` ficam como foram gravados.
- **Limite do valor total da Ação:** `valor_unitario` em (14,2) não basta: quantidade × valor também precisa caber nesse limite, e a API recusa com 400. As saídas agregadas de Ação, Submeta, Meta e painel não têm limite de dígitos, para um total alto nunca derrubar a leitura.
- **Ensaio da migration:** não há produção. Medido numa cópia com o seed de demonstração (300 UFPAs, 1.140 membros, 692 participantes): 9,5 s no total, contando a inicialização do Django, sem perda ao reverter e reaplicar.

---

## 12. RLS em `sgp_ufpa` — matriz do Core no banco (#425)

A migration `sgp/0022_rls_ufpa` habilita a RLS e cria quatro políticas, uma por comando. Ela não toca em dados: reverter só remove as políticas e desabilita a RLS, e reaplicar as recria. O escopo em Python (`apps/sgp/services/access.py`) continua sendo o filtro das telas, e a política é a proteção extra para consultas que não o apliquem.

**Matriz aplicada** (Requisitos-CORE §2.1, "SGP — UFPAs"):

| Perfil | Leitura | Escrita (INSERT/UPDATE/DELETE) |
|---|---|---|
| Super Admin (ou `is_superuser`, o Django Admin) | todas | todas |
| UGP | todas | — |
| Articulador Estadual | UFPAs dos estados dos territórios do **próprio** perfil | — |
| ADT/ACR | UFPAs dos territórios do **próprio** perfil | as mesmas |
| FGD, Agricultor, sem perfil | — | — |

- **O escopo sai de `app.current_user_id`, não de `app.user_role`:** a política consulta `core_userprofile`/`core_role` (e `core_user.is_superuser`). Assim, um usuário com vários perfis recebe a união dos escopos, e a elevação `visao_total()` do orçamento, que troca só `app.user_role`, não amplia o acesso a UFPAs. Por isso `adt-acr` também não precisou entrar na lista de papéis do `SessionContextMiddleware`.
- **Vínculo ausente não vira acesso global:** um ADT/ACR ou Articulador sem território no próprio perfil não vê nada. Os territórios de outros perfis não contam. Sem contexto, nada é visível nem gravável. O Python seguiu a mesma regra: `resolver_escopo` devolve `vazio` para o Articulador sem vínculo (antes, `user_states` dava todos os estados) e `combinado` para quem acumula Articulador e ADT/ACR. `user_states` não mudou, porque o SGD e o orçamento o usam.
- **Efeito fora do SGP:** `municipios_acessiveis_ao_usuario` também segue `resolver_escopo`. Por isso, o Articulador sem vínculo deixa de ver municípios ao criar uma demanda com atividade nova no SGD (`apps/sgd/views/demand.py`) e recebe 404 no município informado. As demais regras do SGD usam `user_states` e não mudaram.
- **Escrita na API:** UGP e Articulador recebem 403 ao criar, editar, desativar ou trocar a foto de uma UFPA (`PodeEscreverUFPA`), como a matriz define. A permissão também confere o território da UFPA existente (`has_object_permission`) e o do município de destino. Quem acumula perfis (UGP ou Articulador com ADT/ACR) lê mais do que escreve, e sem essa checagem o UPDATE recusado pela RLS virava 500. O `WITH CHECK` impede, no banco, mover uma UFPA para fora do escopo.
- **Escrita no SCA:** o escopo do sync (`territory_ids_for`, via `user_territories`) decide o que é visível. A escrita de UFPA segue a matriz em `UFPASyncEntity.pode_escrever`, que confere o território atual e o de destino (o do município conta, porque o signal preenche o território a partir dele). O item recusado volta como `SEM_PERMISSAO_ESCRITA`. Se uma recusa do banco ainda escapar, `_process_item` trata `DatabaseError` como erro do item (`ERRO_INTERNO`), e o restante do batch segue.
- **Agricultor ("Própria"):** pendente. O modelo ainda não liga `User` a uma UFPA, então a política não tem como reconhecer a "própria" e o Agricultor fica sem acesso, como já era em Python.
- **Elevação de sistema:** `app.ufpa_sistema = 'on'` libera a tabela, só por `apps.core.db_context.acesso_de_sistema_ufpa(motivo)`, que registra o motivo em log e restaura o valor anterior. Ela é usada em cinco pontos do SCA:
  1. **Idempotência:** a busca por `uuid_local`.
  2. **Duplicidade:** a busca por CPF do titular. Esta e a busca anterior precisam achar a UFPA fora do território para responder `FORA_TERRITORIO`/`DUPLICATA` em vez de bater na constraint, e nada é gravado sob a elevação.
  3. **Território do membro:** `MemberSyncEntity.territorio_of` lê só o `territorio_id` da UFPA do membro. Sem isso, a UFPA oculta lançava `DoesNotExist` e derrubava o batch inteiro, em vez de responder `FORA_TERRITORIO` no item.
  4. **Geração de `uuid_local` no pull:** é um UPDATE só dessa coluna, condicionado a ela estar vazia, numa linha que o usuário já lê. UGP e Articulador recebem o pull, mas a RLS recusaria a gravação deles.
  5. **Aplicação da resolução de conflito:** o Articulador resolve conflitos, mas só lê UFPAs. Antes da elevação, `_pode_gravar_no_territorio` exige Super Admin ou que o território esteja nos estados do **próprio** perfil de Articulador. O critério vale para o território registrado no conflito e também, dentro do bloco elevado, para os territórios que a gravação toca (`territorios_afetados`): o atual da entidade, que pode ter mudado depois que o conflito nasceu, e o de destino, quando o campo resolvido troca o vínculo territorial. Se algum falhar, a resposta é 403 e o conflito segue pendente. O `IsArticuladorEstadual` usa `user_states`, em que Articulador sem território alcança todos os estados, e não pode ser a única barreira de uma gravação elevada.
- **Erros por item no push:** além de `DatabaseError`, o `_process_item` trata `ObjectDoesNotExist`, por exemplo uma relação oculta pela RLS, como erro do item. O restante do batch segue.
- **Tarefas e exportações:** o worker do Celery não passa pelo middleware. `executar_exportacao` gera as linhas dentro de `contexto_de_acesso(job.solicitante)`, que monta o contexto pela mesma função do middleware (`montar_contexto`) e o restaura no fim do job. Sem isso, o arquivo sairia vazio. Uma tarefa nova que leia UFPAs precisa do mesmo bloco.
- **Push e pull do SCA:** rodam com o contexto HTTP do técnico. O pull filtra pelos territórios do usuário, e a política só corta o que já estaria fora do escopo.
- **Participantes de atividade:** o detalhe da atividade lista só as UFPAs participantes que quem lê alcança, e os membros seguem o mesmo recorte. As contagens agregadas (apuração de indicadores, exportação) leem a tabela de ligação `sgp_activityufpa`, que não tem RLS, e contam todos os participantes. Na edição, `set()` não enxerga as UFPAs ocultas e por isso não as remove: quem não vê uma participante não a tira da atividade.
- **Papel de runtime:** `app_user` não é superusuário, não tem `BYPASSRLS` e não é dono das tabelas, porque as migrations rodam como `postgres`. Por isso basta `ENABLE`, sem `FORCE`, como em `sgd_demand` e no orçamento. `python manage.py verificar_papel_rls`, rodado com o usuário de runtime, falha se essa premissa deixar de valer. O `deploy.sh` o executa logo depois das migrations, sem sobrescrever `DB_USER`, e um papel fora da premissa interrompe o deploy. A suíte de testes e os seeds de desenvolvimento rodam como `postgres` e ignoram a RLS: os testes de `apps/sgp/tests/test_ufpa_rls.py` trocam para um papel `NOBYPASSRLS` com `SET LOCAL ROLE`.
## 12. Saúde e Cor/Raça — quem lê, por decisão da coordenação

A Arquitetura exige criptografia desses campos, e a matriz do Core dá leitura das UFPAs ao
Articulador e à UGP sem separar os campos sensíveis. Nenhum documento diz quem pode lê-los. A
pergunta foi levada à coordenação (PDF de 11/11/2026, item 1), com quatro opções: manter como
está, restringir a quem cadastra, restringir a quem cadastra e à UGP, ou outra regra.

**Resposta da coordenação (17/11/2026): opção "a", manter como está.** Leem Saúde e Cor/Raça:

| Perfil | Lê |
|---|---|
| Super Admin | Sim |
| UGP | Sim |
| Articulador Estadual | Sim, nas UFPAs que vê |
| ADT/ACR | Sim, nas UFPAs do território |
| FGD, Agricultor e perfis operacionais | Não |

A matriz fica em `apps/core/sensitive_fields.py` (`SENSITIVE_FIELD_ROLES`), usada pelos serializers
e pela exportação. O código não mudou.

---

## 13. TED — cadastro, versões e teto do pool nacional

O SGP §7.1 e §10.3 definem o TED e as versões. O §6.3 e o RF28 limitam o pool nacional ao total
aprovado no TED para a rubrica. O que os documentos deixam em aberto foi resolvido assim:

| Questão | Decisão | Fonte |
|---|---|---|
| Pool nacional sem TED | Criar ou aumentar é recusado: não há aprovado contra o que validar. Reduzir continua permitido | SGP §6.3, RF28 |
| Aditivo com rubrica abaixo do pool nacional | A versão é recusada, com as rubricas na mensagem. A UGP reduz o pool antes | SGP §6.3: o pool não passa do aprovado |
| Soma das rubricas | Igual ao valor global da versão. Rubrica sem linha na versão tem aprovado zero | SGP §7.1 "Valor total e distribuição inicial por rubrica"; §6.1, o catálogo reflete a classificação de despesa do TED |
| Remanejamento | Com destino no pool nacional, segue o mesmo teto: o remanejamento só acontece dentro da rubrica, e um estadual devolvido ao nacional não pode deixá-lo acima do aprovado. A simulação recusa igual. O alerta do §6.7 trata de volume remanejado, e não autoriza teto acima do aprovado | SGP §6.3 e §6.7 |
| Quantidade de TEDs | Um só, o do PDHC III. Aditivos e prorrogações entram como versões | SGP §5 e §7.1 |
| Versões | Imutáveis e numeradas em sequência. A original nasce com o TED; prorrogação precisa estender o fim da vigência | SGP §7.1 |
| Snapshot do plano | Gerado pelo sistema no registro da versão, com Metas, Submetas, Ações, quantidades, valores, prazos e rubricas previstas | SGP §7.1 |
| Documento | PDF obrigatório em cada versão, até 10 MB, com a mesma confirmação no storage dos documentos da UFPA | SGP §7.1; Arquitetura §8 |
| Leitura | UGP, Super Admin, Articulador e FGD ("Parcial" na matriz do Core). Escrita: UGP e Super Admin | Core, matriz de permissões |

### Escolhas de implementação sem regra nos documentos

- **Distribuição por rubrica:** tabela própria, `TEDVersionRubrica`, porque o §10.3 lista os campos da versão sem ela.
- **Nomes de campo:** `plano_snapshot` no lugar de `plano_snapshot_json`, porque o tipo já é JSON. `documento_key` no lugar de `documento_url`: o arquivo vai para o storage por URL pré-assinada, como nos documentos da UFPA (`arquivo_key`), e a leitura devolve `documento_url` com um link temporário.
- **Data da versão:** a versão não tem data própria de entrada em vigor. `vigencia_inicio` e `vigencia_fim` são a vigência do TED segundo aquela versão, e a versão vale a partir de `registrado_em`. A consulta "plano vigente numa data" entra com os relatórios por versão (RF48).
- **Painel de orçamento:** o `valor_aprovado` do painel e de `orcamento_por_rubrica` continua sendo o valor atribuído a cada nível; no nacional, o que a UGP lançou no pool, que nunca passa do aprovado no TED. O aprovado do TED vem em `/sgp/ted/` e entra no relatório "Execução por rubrica" do Monitoramento do TED.
- **Versão pelo id:** o detalhe da versão fica em `/sgp/ted/{id}/versoes/{id}/`, no padrão de detalhe da API. O `numero_versao` vem no corpo.
- **Sem exclusão:** o TED e as versões não têm DELETE. Os pools apontam para as versões, e o §7.1 pede preservar as anteriores. A issue fala em CRUD; a criação, a leitura e a edição da identificação cobrem o cadastro.
- **Aditivo e vigência:** um aditivo pode mudar as duas datas, inclusive encurtar a vigência. Só a prorrogação precisa estender o fim, porque é para isso que ela existe.
- **`BudgetPool.ted_versao`:** sempre a versão vigente. O registro de uma versão trava o TED e depois todos os pools, em ordem de rubrica e pk, que é a ordem de quem move saldo, e regrava o campo em todos eles. A criação, a alteração e o remanejamento gravam a versão vigente no pool que mudou. Com os pools travados, a conferência contra o novo aprovado e a troca de versão não deixam brecha. O plano vigente numa data passada sai das próprias versões (`registrado_em`).
- **Identificação editável:** número, partícipes e objeto mudam sem nova versão. Valor global e vigência do `TED` espelham a versão vigente; mandá-los no `PATCH` dá `400`, para o cliente não achar que mudou o que não mudou.
- **Responsável pela versão:** `registrado_por` com `PROTECT`, como no ledger. A versão é imutável, e um `SET_NULL` apagaria quem a registrou.
- **PDF de cada termo:** a mesma chave não entra em duas versões. Falha do storage na confirmação responde `503`, e não `500`.
- **Rubrica inativa:** pode ter valor aprovado numa versão. Ela mantém saldo executado e histórico, e o pool nacional dela continua precisando caber no aprovado.
- **Pontos que esperavam o TED:** o fim da vigência na subexecução e o período `vigencia` dos limites continuam como estão. Entram com o Monitoramento do TED (RF51 e RF52).

---

## 14. Monitoramento do TED — aderência, custo por entrega, rastreabilidade e comparativo

O SGP §7.2, §7.4 e §7.5 definem as fórmulas, e o §7.1 pede relatórios contra qualquer versão do
TED e o comparativo entre versões. A árvore Meta → Submeta → Ação e o planejado de cada Ação
(quantidade e valor unitário) saem do snapshot da versão; o realizado e o executado são os de agora.
O executado segue a regra do valor executado da Ação: valor pago das demandas concluídas das
Atividades ativas.

| Questão | Decisão | Fonte |
|---|---|---|
| Índice | % físico ÷ % financeiro, com duas casas. Faixas na ordem: acima de 1,20 subexecução financeira; a partir de 0,95 equilibrada; a partir de 0,80 atenção; abaixo, crítica | SGP §7.2 |
| % físico de Submeta, Meta, Indicador e projeto | Soma das quantidades realizadas sobre a soma das planejadas, como a árvore consolida | SGP §5.2, §5.3 e §5.4 |
| Projeto | O projeto como um todo, com `referencia_id` vazio | SGP §7.2 |
| Série histórica | Task diária às 4h (`calculate_adherence_index`) e recálculo sob demanda. Cada linha guarda a versão contra a qual foi calculada | SGP §7.1, §7.2; Arquitetura §6 |
| Custo por entrega | Executado ÷ quantidade realizada, contra o valor unitário da versão. Indicador e território consolidam as Ações: o previsto é o valor planejado sobre a quantidade planejada delas. Ranking pelo tamanho do desvio, para cima ou para baixo | SGP §7.4 |
| Rastreabilidade | Solicitação paga → demanda → Atividade → cadeia do Plano de Trabalho → contagem de fotos, documentos, listas de presença, UFPAs e membros | SGP §7.5 |
| Comparativo entre versões | O que mudou em quantidade, valor e prazo por Meta, Submeta e Ação, só com o que mudou (incluída, removida ou alterada) | SGP §7.1 |
| Formatos | Aderência e custo por entrega também em CSV e XLSX | SGP §7.7 |

### Escolhas de implementação sem regra nos documentos

- **Território:** o planejado não tem quebra por território. O recorte filtra o realizado e o executado, e o denominador é o planejado das Ações com atividade no território. Com uma Ação só, o índice fica igual a (quantidade entregue × valor unitário do TED) ÷ valor executado nas atividades dele.
- **Indicador de lançamento manual:** a quantidade lançada pela UGP não tem território nem período. Com recorte (território, período ou o escopo do Articulador) e na quebra por território, essas Ações ficam fora do numerador e do denominador, e a resposta conta quantas (`acoes_manuais_fora_do_recorte`).
- **Sem execução financeira:** com entrega física, o índice fica vazio e a faixa é subexecução financeira. Sem entrega nem gasto, não há índice nem faixa.
- **Ação fora da versão:** a do plano atual que não existe no snapshot fica fora do relatório (`acoes_fora_da_versao`). A do snapshot que não existe mais no plano entra com o planejado e sem execução (`acoes_da_versao_fora_do_plano`), e na série fica só no total do projeto, porque a série é por id.
- **Versão numa data:** a última versão registrada até o dia (`registrado_em`).
- **Mês da série:** a task das 4h grava no mês de ontem: o cálculo do dia 1º fecha o mês anterior com o último dia inteiro dentro dele.
- **Limiar do desvio de custo:** `cost_deviation_alert_pct`, com padrão de 20 % (DRS Core §3.3). A chave entra na #461; até lá, e com valor ilegível ou negativo, vale o padrão. As faixas são dentro do limiar, acima e abaixo do previsto. Uma Ação com entrega e sem pagamento sai com custo zero e desvio de −100 %, pela fórmula.
- **Perfis:** os quatro do TED. O Super Admin, a UGP e a FGD leem o projeto inteiro. O Articulador apura só as Atividades dos estados dos territórios do perfil dele; um perfil de ADT do mesmo usuário não amplia esse recorte, porque o ADT não lê o TED. A série gravada é do projeto inteiro: o Articulador só lê a dos territórios que ficam inteiros nos seus estados. O recálculo é da UGP e do Super Admin.
- **Recorte pela Atividade:** custo, composição e rastreabilidade recortam pelo estado da Atividade, e não pelo do solicitante, que é o recorte do RLS do SGD. A leitura do SGD nesses relatórios roda em visão total, com o escopo de quem consulta aplicado pelas Atividades.
- **Paginação:** as linhas de aderência, custo e composição vêm no envelope paginado da API, com o cabeçalho do relatório ao lado.
- **PDF:** o §7.7 também pede PDF da execução consolidada. Fica para a parte com o fechamento mensal, que gera os relatórios em PDF.
- **Semáforo na árvore e no dashboard do Core:** a coluna na árvore do Plano de Trabalho é da #454 e o bloco no dashboard do Core é da #443. Os dois leem o índice daqui.

---

## Observação

Achado da varredura que **não** tem justificativa técnica registrada em
nenhum lugar do código ou de outra documentação — não foi tratado como
"decisão" neste documento porque isso exigiria inventar uma justificativa.
Fica aqui como nota para a coordenação técnica confirmar se é decisão
implícita (e então deve virar uma entrada numerada acima) ou lacuna real:

- **`UFPA`/`MembroFamilia` não têm `estado_civil` nem `email`**, campos que
  a especificação lista para `UFPA`. O telefone da especificação existe como
  `UFPA.celular` e `UFPA.whatsapp`, e o `dap_caf` como `UFPA.numero_dap`,
  exposto na API com o nome `dap_caf`.
