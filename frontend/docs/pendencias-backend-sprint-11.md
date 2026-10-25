# Pendências de backend — sprint 11

*Compilado em 25/10/2026, na branch `frontend/sprint-11a`. Os itens também estão na issue de backend #373, que reúne as pendências abertas do frontend.*

*Os documentos das sprints anteriores (`pendencias-backend-sprint-9.md` e `pendencias-backend-sprint-10.md`) continuam valendo para o que está lá.*

---

## 1. Não há rota que liste as rubricas do orçamento (#319)

*Compilado em 25/10/2026, ao planejar a issue #319 (configuração do mapeamento tipo de solicitação → rubrica).*

A tela da #319 consome o CRUD da BE-8 (`/api/v1/sgd/config/tipo-rubrica/`). Para criar ou alterar um mapeamento, o Super Admin escolhe a rubrica, e o `POST`/`PATCH` espera o `id` dela (`rubrica`).

Nenhuma rota do backend lista as rubricas (`BudgetRubrica`) com o `id`. Conferido em 25/10/2026 contra a `main`, pelo `schema.yml` e pela API:
- o `GET /api/v1/choices/` não traz rubricas;
- a lista do próprio mapeamento só mostra as rubricas que já estão mapeadas (`rubrica`, `rubrica_nome`);
- `GET /api/v1/sgp/metas/{id}/orcamento/` traz as rubricas de uma meta, dentro do orçamento dela, e serve à distribuição, não a um cadastro geral;
- `GET /api/v1/sgd/painel/rubricas/` é o painel de execução, recortado pelos filtros de demanda.

Montar a lista no front a partir de uma dessas rotas seria contornar a falta da rota certa.

**Pedido:** uma rota de leitura do catálogo de rubricas, sem paginação, com este contrato:

```
GET /api/v1/sgp/rubricas/?ativo=true
```

```json
[
  { "id": 4, "slug": "alimentacao-refeicoes", "nome": "Alimentação/Refeições", "ativo": true }
]
```

- ordenada por `nome`;
- `?ativo=true` devolve só as ativas. Sem o parâmetro, devolve todas, para a tela mostrar o nome de uma rubrica inativa que ainda esteja num mapeamento antigo;
- leitura para qualquer usuário autenticado. É um catálogo, sem valores de orçamento, e outras telas também podem usá-la.

*Estado atual no frontend:* a tela de Tipos e Rubricas (`/admin/configuracoes/sgd/tipos-rubricas`) chama só essa rota para montar o campo "Rubrica". Enquanto ela não existe, o campo mostra o erro do componente, e não dá para criar um mapeamento nem trocar a rubrica de um existente. Listar, desativar, reativar e remover funcionam. No E2E, só a resposta dessa rota é simulada, com os ids reais do banco; o resto roda contra o CRUD real.
