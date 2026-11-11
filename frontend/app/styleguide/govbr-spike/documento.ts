export const documentoSpike = `
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GOV.BR DS e Tailwind</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@govbr-ds/core@4.3.0/dist/core.min.css">
    <link rel="stylesheet" href="/govbr-spike.css">
  </head>
  <body class="tw:p-6 tw:flex tw:flex-col tw:gap-4">
    <section aria-labelledby="govbr-titulo" data-testid="govbr-spike-bloco-govbr">
      <h2 id="govbr-titulo">Componentes do GOV.BR DS</h2>
      <div class="tw:flex tw:flex-col tw:gap-3">
        <div class="br-input">
          <label for="nome">Nome completo</label>
          <input id="nome" type="text" placeholder="Digite seu nome" data-testid="govbr-input-nome">
        </div>
        <div class="tw:flex tw:gap-2">
          <button type="button" class="br-button primary" data-testid="govbr-botao-primario">Enviar</button>
          <button type="button" class="br-button secondary">Cancelar</button>
        </div>
        <div class="br-message warning" role="status">
          <div class="content">
            <span class="message-title">Atenção</span>
            <span class="message-body">Preencha os dados antes de enviar.</span>
          </div>
        </div>
      </div>
    </section>
    <section aria-labelledby="layout-titulo" class="tw:p-6" data-testid="govbr-spike-bloco-tailwind">
      <h2 id="layout-titulo">Layout com Tailwind prefixado</h2>
      <p>Grid, espaçamento e variantes responsivas compilados com prefix(tw).</p>
      <div class="tw:mt-4 tw:grid tw:grid-cols-1 tw:gap-4 tw:sm:grid-cols-3" data-testid="govbr-spike-grid-tw">
        <div class="tw:flex tw:flex-col tw:gap-1 tw:p-3"><span>Território</span><span>Rio Grande do Norte</span></div>
        <div class="tw:flex tw:flex-col tw:gap-1 tw:p-3"><span>Meta</span><span>Meta 1</span></div>
        <div class="tw:flex tw:flex-col tw:gap-1 tw:p-3"><span>Rubrica</span><span>Diárias</span></div>
      </div>
    </section>
    <section aria-labelledby="convivencia-titulo" class="tw:p-6" data-testid="govbr-spike-conviv">
      <h2 id="convivencia-titulo">Componentes em uma grade Tailwind</h2>
      <div class="tw:mt-4 tw:grid tw:grid-cols-1 tw:gap-4 tw:sm:grid-cols-2">
        <button type="button" class="br-button primary">Autorizar</button>
        <button type="button" class="br-button secondary">Devolver</button>
      </div>
    </section>
  </body>
</html>
`;
