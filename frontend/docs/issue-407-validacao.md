# Validação da issue 407

Referência: https://github.com/pdhc3-tic/web-app/issues/407

## Critérios de aceite

| Critério | Implementação e evidência |
| --- | --- |
| Rotas, componentes, tipos, rótulos e textos com UFPA e forma por extenso | Rotas em `/sgp/ufpas`; tipos e componentes com UFPA; forma por extenso “Unidade Familiar de Produção Agropecuária”. Varredura automatizada em `renomeacaoUfpa.test.ts`. |
| Redirecionamento dos endereços anteriores | `next.config.ts` contém redirecionamentos permanentes para a listagem e subrotas. Teste unitário aprovado; E2E cobre mapa com query string. |
| Tipos regenerados caso a #273 esteja entregue | Não aplicável enquanto #273 estiver aberta; não há geração integrada ao build nesta versão. |
| Exportação da #240 usa o nome novo | Parser de Content-Disposition e fallback traduzem nomes de arquivos, tanto no download síncrono quanto no assíncrono. Testes cobrem ambos os formatos de cabeçalho. |
| Suíte E2E verde, sem sigla antiga visível | Pendente de execução em ambiente completo. Acrescentada verificação de texto e aria-label nas telas de cadastro, edição, ficha, listagem, mapa e hub. |

## Contrato do backend

A dependência AJ-BE-09 ainda não está refletida no backend deste checkout.
`app/lib/ufpaContrato.ts` isola a tradução de rotas, campos e discriminadores
no cliente HTTP. A interface e seus tipos usam UFPA, enquanto a comunicação
permanece compatível com o servidor atual. Conteúdo textual de usuários e
respostas livres de formulários não são renomeados. As fixtures E2E mantêm os
nomes reais dos modelos e tabelas do servidor.

## Verificação local em 12/11/2026

- Suíte unitária completa: 42 arquivos e 249 testes aprovados.
- Após acrescentar a cobertura do cliente autenticado: 10 testes aprovados
  nos três arquivos de contrato e renomeação, incluindo os três novos casos.
- TypeScript: aprovado.
- ESLint dos arquivos de lógica alterados e da spec de renomeação: aprovado.
- Playwright: descoberta de 406 testes em 53 arquivos aprovada.
- Execução da spec de listagem: interrompida no setup por ausência do
  executável Chromium do Playwright. Nenhum teste de tela foi executado.
- Também não há servidor em localhost:3000 nem comando Docker disponível.

Não fechar o critério E2E até executar a suíte contra a stack completa.
