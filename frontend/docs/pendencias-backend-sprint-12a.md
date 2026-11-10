# Pendências de backend — sprint 12a

*Compilado em 08/11/2026, na branch `frontend/sprint-12a`.*

*Os itens deste documento vão para uma issue de backend nova, aberta junto do PR da `frontend/sprint-12a`.*

*Os documentos das sprints anteriores continuam valendo para o que está lá.*

---

## 1. Campo de anexo no catálogo de tipos (#365)

A #365 pede que o formulário de um tipo de solicitação novo, desenhado a partir do `schema_campos` do catálogo (`/sgd/config/tipos-solicitacao/`, #357), aceite campos de texto, número, data, booleano, enumeração **e upload**.

Os cinco primeiros têm representação no JSON Schema que o backend já valida (`type`, `format: date`/`date-time`, `enum`). O upload não tem: os campos da solicitação são gravados em `DemandRequest.campos_json`, sem arquivo, e os anexos da demanda vão por `DemandDocument` (aba Documentos), sem ligação com um campo do schema. Nada no catálogo diz que um campo é um anexo, nem onde o arquivo fica.

**Pedido:** definir como um campo de anexo é declarado no `schema_campos` e como o arquivo chega ao backend. Sugestão, a combinar com o front:

- no schema, `{"type": "string", "format": "anexo", "title": "Comprovante de reserva"}`, com `required` valendo como nos demais campos;
- o arquivo sobe pelo fluxo de upload que já existe para documentos da demanda (URL assinada e confirmação), ligado à solicitação e ao campo;
- em `campos_json`, o campo guarda o id do documento, e a validação confere que o documento existe, é da mesma demanda e, se obrigatório, foi enviado antes de submeter;
- a leitura da solicitação devolve, para cada campo de anexo, o nome do arquivo e o link de download.

*Estado atual no frontend:* o formulário automático cobre texto, número, data, data e hora, booleano e enumeração. Um campo com `format` desconhecido aparece como texto. Quando o contrato do anexo for definido, o campo entra no mesmo renderizador.

---

## 2. Busca de atividades de outros estados para vincular à demanda (#361)

O #352 (PR #416) passou a aceitar, na criação da demanda, uma `activity_id` de qualquer estado ou território: a abrangência vem do solicitante e a resposta traz `atividade_fora_do_territorio`. Mas não há por onde o ADT **encontrar** essa atividade. O campo de busca usa `GET /sgp/atividades/?status=planejado&status=agendado&q=`, e essa rota aplica `atividades_acessiveis_ao_usuario`, que recorta pelo território do usuário. Um ADT da PB nunca vê uma atividade do RN, e o E2E que a #361 pede (ADT da PB vincula atividade do RN) não tem como ser feito pela tela.

**Pedido:** uma busca de atividades elegíveis para demanda sem o recorte territorial, só com os filtros de status e título. Pode ser um parâmetro na rota do SGP (ex.: `?elegiveis_para_demanda=true`, que troca o recorte territorial por "status Planejado/Agendado") ou uma rota no SGD (ex.: `GET /sgd/atividades-elegiveis/?q=`), devolvendo id, título, status, data, município com estado e técnico.

*Estado atual no frontend:* o campo já não filtra por técnico nem por estado. Quando a rota existir, só a URL da busca muda.

## 3. Estado e Articulador antes de criar, e o estado da atividade na demanda (#361)

A #361 pede que o formulário mostre, só para leitura, o território da demanda e o Articulador que vai analisá-la, e que avise antes de submeter quando a atividade é de outro estado ("A atividade é em RN; a demanda será analisada pelo Articulador da PB…").

Faltam três dados:

- **Antes de criar:** nenhuma rota diz qual estado e território a demanda vai receber. A regra é `abrangencia_para_nova_demanda` / `resolver_nivel_do_usuario`, que considera a ordem dos perfis e o estado-sede do território. O front não copia essa regra.
- **O Articulador responsável:** nem a demanda nem outra rota trazem o nome do Articulador do `estado_sigla` da demanda.
- **O estado da atividade:** o `contexto` da demanda traz o município da atividade, mas não a UF. Quem abre a demanda não pode ver a atividade de outro estado pelo SGP, que recorta por território. Sem a UF, o aviso diz "outro estado" em vez de "RN".

**Pedido:**

- uma prévia da abrangência para quem vai criar (ex.: `GET /sgd/demandas/abrangencia/?activity_id=`), que devolva `estado_sigla`, `territorio{id, nome}`, `articulador{id, nome}` (ou nulo) e `atividade_fora_do_territorio`;
- `articulador_nome` (ou `{id, nome}`) no `DemandSerializer`;
- `contexto.municipio_estado_sigla` (a UF do município da atividade) no `DemandContextoSerializer`.

*Estado atual no frontend:* o território da demanda e o aviso de atividade em outro estado aparecem na montagem, logo depois de criar e antes de submeter, com o que o backend gravou. O detalhe e a listagem mostram o território da demanda e o selo "Atividade fora do território". O nome do Articulador não aparece em lugar nenhum.
