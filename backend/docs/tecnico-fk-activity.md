# Decisão: `Activity.tecnico_responsavel` continua apontando para `User`

## Contexto

A Issue #225 introduz o model `apps.sgp.models.Tecnico` (§8 do documento de refatoração — ver `plano_refatoracao.pdf`, na raiz do repositório, decisão R7), que enriquece um `User` com os campos `territorio`, `osc` (Organization), `papel` e `ativo`.

§8 sugere que `Activity` referencie `Tecnico` como técnico responsável. **Esta implementação não faz essa troca.**

## Decisão

`Activity.tecnico_responsavel` (`apps/sgp/models/activity.py`) **permanece uma `ForeignKey` direta para `settings.AUTH_USER_MODEL`**, como já era antes da Issue #225.

`Tecnico.user` é uma `OneToOneField` para `User` — um perfil *adicional*, não uma substituição. Consultas que precisam da OSC ou do território do técnico responsável de uma atividade fazem join através dessa relação (`tecnico_responsavel__tecnico__osc_id`, `tecnico_responsavel__tecnico__territorio_id`), em vez de trocar a FK da atividade.

## Justificativa

- **Custo de migração de dados.** Trocar a FK exigiria migrar toda a base histórica de `Activity` para apontar para `Tecnico` em vez de `User`, incluindo atividades cujo técnico responsável nunca teve (ou já perdeu) um vínculo `Tecnico`.
- **Risco para o sync SCA.** O app offline SCA sincroniza atividades referenciando o usuário diretamente; trocar a FK quebraria esse contrato e exigiria uma migração coordenada com o app mobile.
- **`Tecnico` é opcional por natureza.** Nem todo usuário responsável por uma atividade necessariamente tem (ou precisa ter) um registro `Tecnico` — manter a FK em `User` evita acoplar `Activity` a uma entidade que pode não existir para o responsável.

## Como isso aparece no código

- `apps/sgp/models/tecnico.py`: `Tecnico.user = OneToOneField(User, related_name="tecnico")`.
- `apps/sgp/filters.py` (`ActivityFilter.osc`): filtra atividades por OSC do técnico responsável via `tecnico_responsavel__tecnico__osc_id`.
- `apps/sgp/models/activity.py`: `tecnico_responsavel` inalterado.

Consequência direta: desativar um `Tecnico` (`ativo=False`) não afeta `Activity`s já registradas, já que elas não têm nenhuma FK para `Tecnico` — apenas para `User`.
