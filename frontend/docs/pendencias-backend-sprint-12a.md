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
