"use client";

import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  labelSemaforoOrcamento,
  limiaresDaLinha,
  nivelOrcamentoLabel,
  nomeDoPool,
  valorNumerico,
} from "@/app/lib/orcamento";
import { formatPercentual } from "@/app/lib/semaforo";
import type { CelulaOrcamento, RubricaComPools } from "./tipos";

type Props = {
  grupos: RubricaComPools[];
  /** Com a Meta escolhida, a coluna Executado mostra o executado nas atividades dela. */
  comMeta: boolean;
  onSelect: (celula: CelulaOrcamento) => void;
};

type Coluna = { chave: "valor_aprovado" | "valor_distribuido" | "valor_comprometido" | "valor_executado" | "saldo_disponivel"; titulo: string };

/**
 * As cinco colunas de §5.3.3, na ordem em que o dinheiro se move: o que o pool
 * recebeu, o que desceu para os pools de baixo, o que está reservado, o que já
 * saiu e o que sobra.
 */
const COLUNAS: Coluna[] = [
  { chave: "valor_aprovado", titulo: "Aprovado" },
  { chave: "valor_distribuido", titulo: "Distribuído" },
  { chave: "valor_comprometido", titulo: "Comprometido" },
  { chave: "valor_executado", titulo: "Executado" },
  { chave: "saldo_disponivel", titulo: "Disponível" },
];

const RECUO = ["pl-4", "pl-9", "pl-14"] as const;

/** O valor de uma coluna: com Meta, o executado é o da Meta. */
function valorDaColuna(celula: CelulaOrcamento, coluna: Coluna, comMeta: boolean): string {
  if (coluna.chave === "valor_executado" && comMeta) return celula.linha.valor_executado_meta ?? "0";
  return celula.linha[coluna.chave];
}

/** Saldo negativo é possível (remanejamento) e é pintado para o gestor notar. */
function classeDoValor(coluna: Coluna, bruto: string): string {
  if (coluna.chave !== "saldo_disponivel") return "text-text";
  return valorNumerico(bruto) < 0 ? "text-error-text font-semibold" : "text-text";
}

function LinhaPool({
  celula,
  comMeta,
  onSelect,
}: {
  celula: CelulaOrcamento;
  comMeta: boolean;
  onSelect: (celula: CelulaOrcamento) => void;
}) {
  const { linha, nivelSemaforo, percentual, profundidade } = celula;
  const nome = nomeDoPool(linha);

  return (
    <tr
      className="border-t border-border transition-colors hover:bg-surface-warm"
      data-testid={`orcamento-linha-${linha.id}`}
      data-nivel={nivelSemaforo}
      data-nivel-pool={linha.nivel}
    >
      {/* O local é o cabeçalho da linha: um leitor de tela que pousa num valor
          ouve "Pernambuco", não só "R$ 8.000,00". */}
      <th scope="row" className={`whitespace-nowrap py-2.5 pr-4 text-left text-sm font-medium text-text ${RECUO[profundidade]}`}>
        <span className="flex items-center gap-2">
          {nome}
          {linha.nivel !== "nacional" && (
            <span className="rounded-full bg-surface-muted px-2 py-0.5 text-2xs font-medium uppercase tracking-[0.06em] text-text-muted">
              {nivelOrcamentoLabel(linha.nivel)}
            </span>
          )}
          {linha.reserva_ugp && <span className="text-2xs font-normal text-text-muted">reserva da UGP</span>}
        </span>
      </th>

      {COLUNAS.map((coluna) => {
        const valor = valorDaColuna(celula, coluna, comMeta);
        return (
          <td
            key={coluna.chave}
            className={`whitespace-nowrap px-4 py-2.5 text-right text-sm tabular-nums ${classeDoValor(coluna, valor)}`}
          >
            {formatCurrencyBRL(valor)}
          </td>
        );
      })}

      <td className="px-4 py-2.5">
        <div className="flex items-center justify-end gap-2">
          <span className="hidden tabular-nums text-xs text-text-muted sm:inline">{formatPercentual(percentual)}</span>
          <SemaforoBadge nivel={nivelSemaforo} label={labelSemaforoOrcamento(nivelSemaforo, limiaresDaLinha(linha))} />
        </div>
      </td>

      <td className="px-4 py-2.5 text-right">
        <button
          type="button"
          onClick={() => onSelect(celula)}
          data-testid={`orcamento-detalhar-${linha.id}`}
          aria-label={`Detalhar ${linha.rubrica.nome} em ${nome}`}
          className="rounded-md px-2 py-1 text-xs font-medium text-primary transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Detalhar
        </button>
      </td>
    </tr>
  );
}

/**
 * Matriz Rubrica × Nível (#398).
 *
 * Uma <table> só, com um <tbody> por rubrica: os pools de rubricas diferentes
 * ficam na mesma coluna e podem ser comparados de cima a baixo. Dentro da
 * rubrica, a árvore Nacional → estado → territórios, pelo recuo.
 */
export function MatrizOrcamento({ grupos, comMeta, onSelect }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface" data-testid="orcamento-matriz">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[62rem] border-collapse">
          <caption className="px-4 py-3 text-left text-sm text-text-muted">
            Orçamento por rubrica e nível. Valores em reais; o semáforo compara o comprometido com o aprovado de cada
            pool.{comMeta && " A coluna Executado mostra o executado nas atividades da Meta escolhida."}
          </caption>

          <thead className="bg-surface-muted">
            <tr>
              <th
                scope="col"
                className="whitespace-nowrap px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
              >
                Nível
              </th>
              {COLUNAS.map((coluna) => (
                <th
                  key={coluna.chave}
                  scope="col"
                  className="whitespace-nowrap px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
                >
                  {coluna.chave === "valor_executado" && comMeta ? "Executado na Meta" : coluna.titulo}
                </th>
              ))}
              <th
                scope="col"
                className="whitespace-nowrap px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
              >
                Semáforo
              </th>
              <th scope="col" className="px-4 py-2.5">
                <span className="sr-only">Detalhamento</span>
              </th>
            </tr>
          </thead>

          {grupos.map((grupo) => (
            <tbody key={grupo.rubrica.id} data-testid={`orcamento-rubrica-${grupo.rubrica.slug}`}>
              <tr className="border-t border-border bg-surface-warm">
                <th
                  scope="colgroup"
                  colSpan={COLUNAS.length + 3}
                  className="px-4 py-2 text-left text-sm font-semibold text-text"
                >
                  {grupo.rubrica.nome}
                </th>
              </tr>
              {grupo.celulas.map((celula) => (
                <LinhaPool key={celula.linha.id} celula={celula} comMeta={comMeta} onSelect={onSelect} />
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </div>
  );
}
