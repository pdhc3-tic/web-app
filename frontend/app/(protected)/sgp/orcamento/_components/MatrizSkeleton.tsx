/**
 * Esqueleto da matriz durante a primeira carga.
 *
 * Reproduz a grade real (8 colunas, grupos de 6 rubricas) em vez de um spinner
 * centralizado: a tabela é a única coisa na tela, e um bloco com a forma certa
 * evita o salto de layout quando os dados chegam. As larguras variam por coluna
 * porque uma grade de barras idênticas lê como um padrão, não como conteúdo
 * carregando.
 */

const COLUNAS_VALOR = 5;
const RUBRICAS_POR_META = 6;
const METAS = 2;

function Barra({ className }: { className: string }) {
  return <div className={`h-4 animate-pulse rounded bg-surface-muted ${className}`} />;
}

export function MatrizSkeleton() {
  return (
    <div
      className="overflow-hidden rounded-lg border border-border bg-surface"
      data-testid="orcamento-skeleton"
      aria-busy="true"
      aria-label="Carregando o orçamento"
    >
      <div className="px-4 py-3">
        <Barra className="w-80 max-w-full" />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[62rem] border-collapse">
          <tbody>
            <tr className="bg-surface-muted">
              <td className="px-4 py-2.5">
                <Barra className="w-20" />
              </td>
              {Array.from({ length: COLUNAS_VALOR + 2 }).map((_, i) => (
                <td key={i} className="px-4 py-2.5">
                  <Barra className="ml-auto w-16" />
                </td>
              ))}
            </tr>

            {Array.from({ length: METAS }).flatMap((_, m) => [
              <tr key={`grupo-${m}`} className="border-t border-border bg-surface-warm">
                <td colSpan={COLUNAS_VALOR + 3} className="px-4 py-2">
                  <Barra className="w-64 max-w-full" />
                </td>
              </tr>,

              ...Array.from({ length: RUBRICAS_POR_META }).map((__, r) => (
                <tr key={`linha-${m}-${r}`} className="border-t border-border">
                  <td className="px-4 py-2.5">
                    <Barra className="w-32" />
                  </td>
                  {Array.from({ length: COLUNAS_VALOR }).map((___, c) => (
                    <td key={c} className="px-4 py-2.5">
                      <Barra className="ml-auto w-24" />
                    </td>
                  ))}
                  <td className="px-4 py-2.5">
                    <Barra className="ml-auto w-28 rounded-full" />
                  </td>
                  <td className="px-4 py-2.5">
                    <Barra className="ml-auto w-14" />
                  </td>
                </tr>
              )),
            ])}
          </tbody>
        </table>
      </div>
    </div>
  );
}
