"use client";

import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  descreverEscopo,
  labelSemaforoOrcamento,
  valorNumerico,
} from "@/app/lib/orcamento";
import { formatPercentual } from "@/app/lib/semaforo";
import type { CelulaOrcamento, EscopoExibido, MetaComRubricas } from "./tipos";

type Props = {
  grupos: MetaComRubricas[];
  escopo: EscopoExibido;
  onSelect: (celula: CelulaOrcamento) => void;
};

/**
 * As cinco colunas de §5.3.3, na ordem em que o dinheiro se move: o que foi
 * aprovado, o que desceu de nível, o que já está reservado, o que já saiu e o
 * que sobra.
 */
const COLUNAS = [
  { chave: "valor_aprovado", titulo: "Aprovado" },
  { chave: "valor_distribuido", titulo: "Distribuído" },
  { chave: "valor_comprometido", titulo: "Comprometido" },
  { chave: "valor_executado", titulo: "Executado" },
  { chave: "saldo_disponivel", titulo: "Disponível" },
] as const;

/**
 * Saldo negativo é possível e não é um bug: `saldo_disponivel` é
 * aprovado − distribuído − comprometido − executado, e um remanejamento da UGP
 * pode deixar uma linha estourada. Pintar de vermelho é a única forma de o
 * gestor notar sem conferir a conta de cabeça.
 */
function classeDoValor(chave: string, bruto: string): string {
  if (chave !== "saldo_disponivel") return "text-text";
  return valorNumerico(bruto) < 0 ? "text-error-text font-semibold" : "text-text";
}

function LinhaRubrica({
  celula,
  onSelect,
}: {
  celula: CelulaOrcamento;
  onSelect: (celula: CelulaOrcamento) => void;
}) {
  const { linha, nivelSemaforo, percentual } = celula;

  return (
    <tr
      className="border-t border-border transition-colors hover:bg-surface-warm"
      data-testid={`orcamento-linha-${linha.meta.id}-${linha.rubrica.slug}`}
      data-nivel={nivelSemaforo}
    >
      {/* A rubrica é o cabeçalho da própria linha: um leitor de tela que pousa
          numa célula de valor precisa ouvir "Diárias", não só "R$ 8.000,00". */}
      <th
        scope="row"
        className="whitespace-nowrap px-4 py-2.5 text-left text-sm font-medium text-text"
      >
        {linha.rubrica.nome}
      </th>

      {COLUNAS.map((coluna) => (
        <td
          key={coluna.chave}
          className={`whitespace-nowrap px-4 py-2.5 text-right text-sm tabular-nums ${classeDoValor(coluna.chave, linha[coluna.chave])}`}
        >
          {formatCurrencyBRL(linha[coluna.chave])}
        </td>
      ))}

      <td className="px-4 py-2.5">
        <div className="flex items-center justify-end gap-2">
          {/* O percentual ao lado da cor é o que torna o semáforo auditável —
              mesma decisão da AcaoLinha do painel do PT. */}
          <span className="hidden tabular-nums text-xs text-text-muted sm:inline">
            {formatPercentual(percentual)}
          </span>
          <SemaforoBadge
            nivel={nivelSemaforo}
            label={labelSemaforoOrcamento(nivelSemaforo)}
          />
        </div>
      </td>

      <td className="px-4 py-2.5 text-right">
        <button
          type="button"
          onClick={() => onSelect(celula)}
          data-testid={`orcamento-detalhar-${linha.meta.id}-${linha.rubrica.slug}`}
          aria-label={`Detalhar ${linha.rubrica.nome} na Meta ${linha.meta.numero} por nível`}
          className="rounded-md px-2 py-1 text-xs font-medium text-primary transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Detalhar
        </button>
      </td>
    </tr>
  );
}

/**
 * Matriz Meta × Rubrica (§5.3.3).
 *
 * Uma <table> só, com um <tbody> por Meta em vez de uma tabela por Meta: os
 * valores de rubricas diferentes ficam na mesma coluna e podem ser comparados
 * de cima a baixo, que é o ponto de chamar isso de matriz. Tabelas separadas
 * alinhariam por acaso, e desalinhariam assim que uma Meta tivesse um valor
 * mais largo.
 *
 * A rolagem horizontal vive no wrapper, não na página: são 8 colunas, e em
 * telas estreitas o layout do resto da tela não pode ir junto.
 */
export function MatrizOrcamento({ grupos, escopo, onSelect }: Props) {
  const escopoTexto = descreverEscopo(escopo.nivel, escopo.nomeLocal);

  return (
    <div
      className="overflow-hidden rounded-lg border border-border bg-surface"
      data-testid="orcamento-matriz"
      data-nivel-escopo={escopo.nivel}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[62rem] border-collapse">
          <caption className="px-4 py-3 text-left text-sm text-text-muted">
            Orçamento por Meta e rubrica — nível{" "}
            <span className="font-medium text-text">{escopoTexto}</span>. Valores
            em reais; o semáforo compara o comprometido com o aprovado de cada
            rubrica.
          </caption>

          <thead className="bg-surface-muted">
            <tr>
              <th
                scope="col"
                className="whitespace-nowrap px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
              >
                Rubrica
              </th>
              {COLUNAS.map((coluna) => (
                <th
                  key={coluna.chave}
                  scope="col"
                  className="whitespace-nowrap px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
                >
                  {coluna.titulo}
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
            <tbody key={grupo.meta.id} data-testid={`orcamento-meta-${grupo.meta.id}`}>
              {/* Cabeçalho de grupo: `colSpan` sobre a largura inteira, com
                  scope="colgroup" para que a Meta seja anunciada como o
                  contexto das linhas abaixo dela. */}
              <tr className="border-t border-border bg-surface-warm">
                <th
                  scope="colgroup"
                  colSpan={COLUNAS.length + 3}
                  className="px-4 py-2 text-left text-sm font-semibold text-text"
                >
                  Meta {grupo.meta.numero}
                  <span className="ml-2 font-normal text-text-muted">
                    {grupo.meta.titulo}
                  </span>
                </th>
              </tr>

              {grupo.celulas.map((celula) => (
                <LinhaRubrica
                  key={celula.linha.rubrica.slug}
                  celula={celula}
                  onSelect={onSelect}
                />
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </div>
  );
}
