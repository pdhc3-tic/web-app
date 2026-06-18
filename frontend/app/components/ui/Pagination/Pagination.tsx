"use client";

import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";

const DEFAULT_PAGE_SIZES = [25, 50, 100];

export type PaginationProps = {
  /** Total de itens (count da resposta paginada). */
  count: number;
  offset: number;
  limit: number;
  onOffsetChange: (offset: number) => void;
  onLimitChange: (limit: number) => void;
  /** Opções do seletor de tamanho de página. */
  pageSizes?: number[];
  /** Substantivo contável para o resumo (ex.: usuário/usuários). */
  itemNoun?: { one: string; other: string };
};

const navBtn =
  "inline-flex h-8 w-8 items-center justify-center rounded-md border border-border text-text-muted transition-colors enabled:hover:bg-surface-muted enabled:hover:text-text disabled:opacity-40 disabled:cursor-not-allowed";

/** Paginação genérica para listagens (LimitOffset). */
export function Pagination({
  count,
  offset,
  limit,
  onOffsetChange,
  onLimitChange,
  pageSizes = DEFAULT_PAGE_SIZES,
  itemNoun = { one: "item", other: "itens" },
}: PaginationProps) {
  const from = count === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, count);
  const totalPages = Math.max(1, Math.ceil(count / limit));
  const currentPage = Math.floor(offset / limit) + 1;

  const isFirst = offset <= 0;
  const isLast = to >= count;

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 px-1 py-1">
      <p className="text-sm text-text-muted">
        <span className="font-medium text-text">
          {from}–{to}
        </span>{" "}
        de <span className="font-medium text-text">{count}</span>{" "}
        {count === 1 ? itemNoun.one : itemNoun.other}
      </p>

      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-text-muted">
          <span className="hidden sm:inline">Por página</span>
          <select
            value={limit}
            onChange={(e) => onLimitChange(Number(e.target.value))}
            className="h-8 rounded-md border border-border bg-surface px-2 text-sm text-text outline-none transition-colors hover:border-text-muted focus:border-primary"
          >
            {pageSizes.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Primeira página"
            className={navBtn}
            disabled={isFirst}
            onClick={() => onOffsetChange(0)}
          >
            <ChevronsLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label="Página anterior"
            className={navBtn}
            disabled={isFirst}
            onClick={() => onOffsetChange(Math.max(0, offset - limit))}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          <span className="px-2 text-sm text-text-muted whitespace-nowrap">
            Página <span className="font-medium text-text">{currentPage}</span>{" "}
            de <span className="font-medium text-text">{totalPages}</span>
          </span>

          <button
            type="button"
            aria-label="Próxima página"
            className={navBtn}
            disabled={isLast}
            onClick={() => onOffsetChange(offset + limit)}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label="Última página"
            className={navBtn}
            disabled={isLast}
            onClick={() => onOffsetChange((totalPages - 1) * limit)}
          >
            <ChevronsRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
