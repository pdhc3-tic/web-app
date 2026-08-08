"use client";

import { Pencil, Trash2 } from "lucide-react";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { formatDate } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  badgeStatusForMeta,
  metaStatusLabel,
  type MetaListItem,
} from "@/app/lib/metas";

const TH_BASE =
  "sticky top-0 z-10 bg-surface-muted px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-[0.08em] text-text-muted whitespace-nowrap";

const actionBtn =
  "inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-text-muted transition-colors hover:border-border hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface";

const dangerBtn = `${actionBtn} hover:bg-error-bg hover:text-error-text`;

type Props = {
  metas: MetaListItem[];
  loading: boolean;
  /**
   * Habilita as ações de escrita. Espelha o `IsSuperAdmin | IsUGP` do backend;
   * quando false a tabela fica em modo somente leitura.
   */
  canManage: boolean;
  onEdit: (meta: MetaListItem) => void;
  onDelete: (meta: MetaListItem) => void;
};

/** Período "01/03/2026 – 31/12/2026". */
function periodo(inicio: string, fim: string): string {
  return `${formatDate(inicio)} – ${formatDate(fim)}`;
}

function StatusCell({ meta }: { meta: MetaListItem }) {
  return (
    <Badge
      status={badgeStatusForMeta(meta.status_calculado)}
      label={metaStatusLabel(meta.status_calculado)}
    />
  );
}

function SkeletonRows({ columns }: { columns: number }) {
  return (
    <>
      {Array.from({ length: 5 }).map((_, i) => (
        <tr key={i} className="border-t border-border">
          {Array.from({ length: columns }).map((__, j) => (
            <td key={j} className="px-4 py-3">
              <div className="h-4 w-full max-w-35 animate-pulse rounded bg-surface-muted" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

function SkeletonCards() {
  return (
    <ul className="flex flex-col gap-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <li key={i} className="rounded-lg border border-border bg-surface p-4">
          <div className="h-4 w-48 animate-pulse rounded bg-surface-muted" />
          <div className="mt-2 h-3 w-28 animate-pulse rounded bg-surface-muted" />
          <div className="mt-4 h-3 w-40 animate-pulse rounded bg-surface-muted" />
        </li>
      ))}
    </ul>
  );
}

function RowActions({
  meta,
  onEdit,
  onDelete,
}: Pick<Props, "onEdit" | "onDelete"> & { meta: MetaListItem }) {
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        aria-label={`Editar Meta ${meta.numero}`}
        onClick={() => onEdit(meta)}
        className={actionBtn}
        data-testid={`meta-editar-btn-${meta.id}`}
      >
        <Pencil className="h-4 w-4" />
      </button>
      <button
        type="button"
        aria-label={`Excluir Meta ${meta.numero}`}
        onClick={() => onDelete(meta)}
        className={dangerBtn}
        data-testid={`meta-excluir-btn-${meta.id}`}
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

/**
 * Listagem das Metas do Plano de Trabalho.
 *
 * TODO(issue-acoes): quando a tela de detalhe da Meta existir, o título vira um
 * link para `/sgp/metas/{id}` (onde as Ações são listadas) e a linha ganha
 * navegação por clique/Enter, como em AtividadesTable. Hoje a linha não é
 * clicável porque não há para onde ir.
 */
export function MetasTable({
  metas,
  loading,
  canManage,
  onEdit,
  onDelete,
}: Props) {
  const columns = canManage ? 6 : 5;

  return (
    <div data-testid="metas-table">
      {/* Desktop — tabela (>= 768px) */}
      <div className="relative hidden overflow-auto rounded-lg border border-border bg-surface md:block">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">
            Metas do Plano de Trabalho do PDHC III.
          </caption>
          <thead>
            <tr>
              <th scope="col" className={`${TH_BASE} w-16`}>
                Nº
              </th>
              <th scope="col" className={TH_BASE}>
                Título
              </th>
              <th scope="col" className={`${TH_BASE} w-52`}>
                Período
              </th>
              <th scope="col" className={`${TH_BASE} w-48`}>
                Valor total planejado
              </th>
              <th scope="col" className={`${TH_BASE} w-40`}>
                Status
              </th>
              {canManage && (
                <th scope="col" className={`${TH_BASE} w-24`}>
                  <span className="sr-only">Ações</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <SkeletonRows columns={columns} />
            ) : (
              metas.map((meta) => (
                <tr
                  key={meta.id}
                  className="border-t border-border transition-colors hover:bg-surface-warm"
                  data-testid={`meta-row-${meta.id}`}
                >
                  <td className="px-4 py-3 font-medium tabular-nums text-text">
                    {meta.numero}
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-medium text-text">{meta.titulo}</span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-text">
                    {periodo(meta.data_inicio, meta.data_fim)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 tabular-nums text-text">
                    {formatCurrencyBRL(meta.valor_total_planejado)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusCell meta={meta} />
                  </td>
                  {canManage && (
                    <td className="px-4 py-3">
                      <RowActions
                        meta={meta}
                        onEdit={onEdit}
                        onDelete={onDelete}
                      />
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile — cards (< 768px) */}
      <div className="md:hidden">
        {loading ? (
          <SkeletonCards />
        ) : (
          <ul className="flex flex-col gap-2">
            {metas.map((meta) => (
              <li
                key={meta.id}
                className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4"
                data-testid={`meta-row-mobile-${meta.id}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex min-w-0 flex-col leading-tight">
                    <span className="text-xs text-text-muted">
                      Meta {meta.numero}
                    </span>
                    <span className="font-medium text-text">{meta.titulo}</span>
                  </div>
                  {canManage && (
                    <RowActions
                      meta={meta}
                      onEdit={onEdit}
                      onDelete={onDelete}
                    />
                  )}
                </div>

                <StatusCell meta={meta} />

                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
                  <span>{periodo(meta.data_inicio, meta.data_fim)}</span>
                  <span className="tabular-nums">
                    {formatCurrencyBRL(meta.valor_total_planejado)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
