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
`Activity`, campos de endereço em `UPF`) — isso é extensão, não desvio, já que
não há nada especificado para divergir. **O que também não entra aqui:**
qualquer coisa que pareça lacuna sem justificativa técnica — isso é tratado
como possível erro e deve virar issue própria, não uma linha deste documento
(ver seção "Pontos a validar" ao final).

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
replicado em `UPF` e `MembroFamilia` por consistência arquitetural, mesmo a
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

## 3. `UPF` — dados pessoais do titular normalizados em `MembroFamilia`

**Especificação:** `UPF` tem, diretamente, os campos de identificação do
titular: `nome_titular, cpf, rg, data_nasc, genero, cor_raca, nis, daf_caf,
estado_civil, escolaridade, telefone, email, ...`.

**Implementação:** `apps/sgp/models/upf.py` não tem nenhum desses campos.
`UPF.titular` é uma `OneToOneField` (`PROTECT`) para `MembroFamilia`, e é
nesse model (`apps/sgp/models/membro.py`) que vivem `nome_completo`, `cpf`,
`rg`, `nis`, `data_nascimento`, `genero`, `cor_raca`, `escolaridade` — o
titular é apenas um `MembroFamilia` como outro qualquer, identificado via
`UPF.titular`.

**Por quê:** evita duplicar o mesmo dado pessoal em duas tabelas (o titular
já é um membro da família, presente em `MembroFamilia.upf`) e mantém uma
única fonte de verdade para atualização de dados pessoais, independente de a
pessoa ser titular ou dependente.

**Consequências:** qualquer código que precise de dados pessoais do titular
de uma `UPF` precisa navegar por `upf.titular.<campo>`, não `upf.<campo>`
diretamente. Campos que a especificação lista para `UPF` mas que não existem
nem em `UPF` nem em `MembroFamilia` — `daf_caf` (existe como `caf`, sem o
prefixo "da"), `estado_civil`, `telefone`, `email` — estão listados na seção
"Pontos a validar" abaixo, pois não há justificativa técnica registrada para
a ausência deles.

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

## 5. `ActivityUPF` / `ActivityMember` — relação implícita do Django em vez de entidade explícita

**Especificação:** modela `ActivityUPF` e `ActivityMember` como entidades
próprias, cada uma com `id` próprio, ligando `Activity` a `UPF` e a
`MembroFamilia` respectivamente.

**Implementação:** `Activity.upfs_participantes` e
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
- **Campos do modelo de dados do SGP fora deste modelo:** `ted_versao_id` depende da entidade do TED; `transfer_id` não é preciso, porque o remanejamento já referencia os dois pools; `periodicidade` e `acumula_saldo` são parâmetros globais do Core; `valor_disponivel` é calculado.

### Divergências do documento mantidas, para a coordenação confirmar

- **Remanejamento entre rubricas:** o SGP 6.7 permite, e o motor só aceita a mesma rubrica, como já fazia. Os demais tipos dependem do simulador da #389.
- **Exatos 90% de comprometimento:** o SGP 6.8 diz amarelo até 90%; o código, como a #373, trata 90% como vermelho.
- **`reserva_ugp`:** com um pool por rubrica e nível, uma rubrica nacional não pode, ao mesmo tempo, ser reserva da UGP e distribuir aos estados.

**Em aberto com a coordenação:** os valores iniciais dos limites por perfil e rubrica e se
ADT e ACR precisam de valores diferentes. Hoje os dois são um só perfil no sistema.

---

## Observação

Achado da varredura que **não** tem justificativa técnica registrada em
nenhum lugar do código ou de outra documentação — não foi tratado como
"decisão" neste documento porque isso exigiria inventar uma justificativa.
Fica aqui como nota para a coordenação técnica confirmar se é decisão
implícita (e então deve virar uma entrada numerada acima) ou lacuna real:

- **`UPF`/`MembroFamilia` não têm `estado_civil`, `telefone` nem `email`**,
  campos que a especificação lista para `UPF`. `daf_caf` da especificação
  existe como `MembroFamilia.caf` (sem o prefixo "DA"), o que pode ser só uma
  simplificação de nome, não uma lacuna.
