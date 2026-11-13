# Validação da issue 407

Referência: https://github.com/pdhc3-tic/web-app/issues/407

## Critérios de aceite

| Critério | Implementação e evidência |
| --- | --- |
| Rotas, componentes, tipos, rótulos e textos com UFPA e forma por extenso | Rotas em `/sgp/ufpas`; tipos e componentes com UFPA; forma por extenso “Unidade Familiar de Produção Agropecuária”. Varredura automatizada em `renomeacaoUfpa.test.ts`. |
| Redirecionamento dos endereços anteriores | `next.config.ts` contém redirecionamentos permanentes para a listagem e subrotas. Teste unitário aprovado; E2E cobre mapa com query string. |
| Tipos regenerados caso a #273 esteja entregue | Não se aplica nesta entrega: a #273 ficou fora do PR da sprint 12b. Quando ela entrar, os tipos saem do schema do #417, que já não tem o nome antigo. |
| Exportação da #240 usa o nome novo | A exportação chama `/api/v1/sgp/ufpas/exportar/` com `tipo=ufpas`, e o nome do arquivo vem do `Content-Disposition` do backend. |
| Suíte E2E verde, sem sigla antiga visível | Rodada contra o backend do PR #417: 118 aprovados, 2 pulados e 4 falhas anteriores à #407 (ver abaixo). Verificação de texto e aria-label nas telas de cadastro, edição, ficha, listagem, mapa e hub. |

## Contrato do backend

Esta entrega depende da AJ-BE-09 (#392, PR #417): o front usa só o contrato novo
(`/api/v1/sgp/ufpas/`, `ufpas_participantes`, `dap_caf`, `tipo=ufpas`) e não
funciona com o backend anterior. O PR #417 entra na `main` antes desta branch.
A camada de tradução no cliente HTTP, que a primeira versão trazia, foi retirada
na revisão: ela apontava para rotas que o backend anterior não tem e reenviava
nomes que o #417 recusa com 400.

Os registros `docs/pendencias-backend-sprint-*.md` ficam como foram escritos,
com os endereços da época.

## Verificação em 13/11/2026 (revisão)

- Backend do PR #417 com a `main` atual, rodando local, com as migrações
  aplicadas sobre o banco de demonstração (restaurado depois).
- Testes unitários e TypeScript: aprovados.
- E2E de 13 specs (UFPA, membros, produção, formulários, mapa, exportação,
  atividade, origem SCA, hub e conflitos): 118 aprovados, 2 pulados, 4 falhas.
  As 4 têm a mesma asserção de antes da #407, que só trocou nomes nesses testes:
  - `formularios.spec.ts:20` espera a primeira UFPA sem respostas, e o banco
    de demonstração tem 31 respostas nela desde 09/10;
  - `ufpa-ficha.spec.ts:165` aceita só "documentos anexados" no plural, e a
    primeira UFPA tem um documento;
  - `membros.spec.ts:1010` procura o rótulo exato "Nome completo", e o rótulo
    traz o marcador "(obrigatório)";
  - `membros.spec.ts:634` (alerta de titular durante a revalidação) falha de
    forma consistente, com a lógica da aba sem mudança além dos nomes.
