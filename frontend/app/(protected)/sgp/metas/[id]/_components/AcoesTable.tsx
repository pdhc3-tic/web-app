"use client";

import { Pencil, Trash2 } from "lucide-react";
import { ProgressBar } from "@/app/components/ui/ProgressBar/ProgressBar";
import { formatDate } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  formatQtd,
  progressoAcao,
  progressoLabel,
  type Acao,
} from "@/app/lib/acoes";

const TH_BASE =
  "sticky top-0 z-10 bg-surface-muted px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-[0.08em] text-text-muted whitespace-nowrap";

const actionBtn =
  "inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-text-muted transition-colors hover:border-border hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface";

const dangerBtn = `${actionBtn} hover:bg-error-bg hover:text-error-text`;

type Props = {
  acoes: Acao[];
  /** Espelha o `IsSuperAdmin | IsUGP` do backend. */
  canManage: boolean;
  onEdit: (acao: Acao) => void;
  onDelete: (acao: Acao) => void;
};

/** Período "01/01/2025 – 31/12/2027"; em-dash sozinho quando não há datas. */
function periodo(inicio: string | null, fim: string | null): string {
  if (!inicio && !fim) return "—";
  return `${inicio ? formatDate(inicio) : "—"} – ${fim ? formatDate(fim) : "—"}`;
}

function ProgressoCell({ acao }: { acao: Acao }) {
  const { percentual } = progressoAcao(acao);
  const contagem = progressoLabel(acao);

  return (
    <div className="flex min-w-40 flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        {/* A contagem vem antes do percentual: com metas plurianuais a barra
            passa muito tempo fina, e "2 de 12" é o que se lê de fato. */}
        <span className="tabular-nums text-text">{contagem}</span>
        <span className="tabular-nums text-text-muted">
          {percentual === null ? "—" : `${percentual.toFixed(1).replace(".", ",")}%`}
        </span>
      </div>
      <ProgressBar
        value={percentual}
        label={`Progresso da Ação ${acao.numero}`}
        valueText={`${contagem} — ${acao.tipo_unidade_display}`}
        tone={percentual !== null && percentual >= 100 ? "success" : "primary"}
      />
    </div>
  );
}

function RowActions({
  acao,
  onEdit,
  onDelete,
}: Pick<Props, "onEdit" | "onDelete"> & { acao: Acao }) {
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        aria-label={`Editar Ação ${acao.numero}`}
        onClick={() => onEdit(acao)}
        className={actionBtn}
        data-testid={`acao-editar-btn-${acao.id}`}
      >
        <Pencil className="h-4 w-4" />
      </button>
      <button
        type="button"
        aria-label={`Excluir Ação ${acao.numero}`}
        onClick={() => onDelete(acao)}
        className={dangerBtn}
        data-testid={`acao-excluir-btn-${acao.id}`}
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

/** Listagem das Ações de uma Meta. */
export function AcoesTable({ acoes, canManage, onEdit, onDelete }: Props) {
  return (
    <div data-testid="acoes-table">
      {/* Desktop — tabela (>= 768px) */}
      <div className="relative hidden overflow-auto rounded-lg border border-border bg-surface md:block">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">
            Ações vinculadas a esta Meta do Plano de Trabalho.
          </caption>
          <thead>
            <tr>
              <th scope="col" className={`${TH_BASE} w-14`}>
                Nº
              </th>
              <th scope="col" className={`${TH_BASE} min-w-64`}>
                Descrição
              </th>
              <th scope="col" className={`${TH_BASE} w-32`}>
                Tipo / unidade
              </th>
              <th scope="col" className={`${TH_BASE} w-24`}>
                Qtd.
              </th>
              <th scope="col" className={`${TH_BASE} w-28`}>
                Valor unitário
              </th>
              <th scope="col" className={`${TH_BASE} w-32`}>
                Valor total
              </th>
              <th scope="col" className={`${TH_BASE} w-44`}>
                Progresso
              </th>
              {canManage && (
                <th scope="col" className={`${TH_BASE} w-24`}>
                  <span className="sr-only">Ações</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {acoes.map((acao) => (
              <tr
                key={acao.id}
                className="border-t border-border transition-colors hover:bg-surface-warm"
                data-testid={`acao-row-${acao.id}`}
              >
                <td className="px-4 py-3 font-medium tabular-nums text-text">
                  {acao.numero}
                </td>
                <td className="min-w-64 px-4 py-3">
                  <span className="text-text">{acao.descricao}</span>
                  <span className="mt-0.5 block text-xs text-text-muted">
                    {periodo(acao.data_inicio, acao.data_fim)}
                  </span>
                </td>
                <td className="px-4 py-3 text-text">
                  {acao.tipo_unidade_display}
                </td>
                <td className="whitespace-nowrap px-4 py-3 tabular-nums text-text">
                  {formatQtd(acao.quantidade_planejada)}
                </td>
                <td className="whitespace-nowrap px-4 py-3 tabular-nums text-text">
                  {formatCurrencyBRL(acao.valor_unitario)}
                </td>
                <td className="whitespace-nowrap px-4 py-3 tabular-nums text-text">
                  {formatCurrencyBRL(acao.valor_total)}
                </td>
                <td className="px-4 py-3">
                  <ProgressoCell acao={acao} />
                </td>
                {canManage && (
                  <td className="px-4 py-3">
                    <RowActions
                      acao={acao}
                      onEdit={onEdit}
                      onDelete={onDelete}
                    />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile — cards (< 768px) */}
      <div className="md:hidden">
        <ul className="flex flex-col gap-2">
          {acoes.map((acao) => (
            <li
              key={acao.id}
              className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
              data-testid={`acao-row-mobile-${acao.id}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex min-w-0 flex-col leading-tight">
                  <span className="text-xs tabular-nums text-text-muted">
                    Ação {acao.numero} · {acao.tipo_unidade_display}
                  </span>
                  <span className="font-medium text-text">
                    {acao.descricao}
                  </span>
                </div>
                {canManage && (
                  <RowActions
                    acao={acao}
                    onEdit={onEdit}
                    onDelete={onDelete}
                  />
                )}
              </div>

              <ProgressoCell acao={acao} />

              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
                <span className="tabular-nums">
                  {formatQtd(acao.quantidade_planejada)} ×{" "}
                  {formatCurrencyBRL(acao.valor_unitario)}
                </span>
                <span className="tabular-nums font-medium text-text">
                  {formatCurrencyBRL(acao.valor_total)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
