"use client";

import { useRouter } from "next/navigation";
import { Eye, Pencil } from "lucide-react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { relativeTime, absoluteDateTime } from "@/app/lib/datetime";
import type { UpfListItem } from "@/app/lib/upfs";

const TH_BASE =
  "sticky top-0 z-10 bg-surface-muted px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-[0.08em] text-text-muted whitespace-nowrap";

const actionBtn =
  "inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-text-muted transition-colors hover:border-border hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface";

function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return format(date, "dd/MM/yyyy", { locale: ptBR });
}

type UpfsTableProps = {
  upfs: UpfListItem[];
  loading: boolean;
};

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <tr key={i} className="border-t border-border">
          {Array.from({ length: 6 }).map((__, j) => (
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
      {Array.from({ length: 6 }).map((_, i) => (
        <li
          key={i}
          className="rounded-lg border border-border bg-surface p-4"
        >
          <div className="h-4 w-40 animate-pulse rounded bg-surface-muted" />
          <div className="mt-2 h-3 w-24 animate-pulse rounded bg-surface-muted" />
          <div className="mt-4 grid grid-cols-2 gap-2">
            <div className="h-3 animate-pulse rounded bg-surface-muted" />
            <div className="h-3 animate-pulse rounded bg-surface-muted" />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function UpfsTable({ upfs, loading }: UpfsTableProps) {
  const router = useRouter();

  function goToDetail(id: number) {
    router.push(`/sgp/upfs/${id}/`);
  }

  return (
    <>
      {/* Desktop — tabela (>= 768px) */}
      <div className="relative hidden max-h-[calc(100vh-22rem)] overflow-auto rounded-lg border border-border bg-surface md:block">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">
            Lista de UPFs (unidades produtivas familiares) cadastradas.
          </caption>
          <thead>
            <tr>
              <th scope="col" className={TH_BASE}>
                Titular
              </th>
              <th scope="col" className={`${TH_BASE} w-45`}>
                Município
              </th>
              <th scope="col" className={`${TH_BASE} w-40`}>
                Território
              </th>
              <th scope="col" className={`${TH_BASE} w-40`}>
                Cadastrado em
              </th>
              <th scope="col" className={`${TH_BASE} w-25`}>
                Status
              </th>
              <th scope="col" className={`${TH_BASE} w-20`}>
                <span className="sr-only">Ações</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <SkeletonRows />
            ) : (
              upfs.map((u) => (
                <tr
                  key={u.id}
                  tabIndex={0}
                  onClick={() => goToDetail(u.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      goToDetail(u.id);
                    }
                  }}
                  className="cursor-pointer border-t border-border transition-colors hover:bg-surface-warm focus:bg-surface-warm focus:outline-none"
                >
                  <td className="px-4 py-3">
                    <div className="flex flex-col leading-tight">
                      <span className="font-medium text-text">
                        {u.nome_titular}
                      </span>
                      <span className="text-xs text-text-muted">
                        {u.cpf || "—"}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {u.municipio || "—"}
                  </td>
                  <td className="px-4 py-3">
                    {u.territorio ? (
                      <Chip>{u.territorio}</Chip>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </td>
                  <td
                    className="px-4 py-3 whitespace-nowrap text-text-muted"
                    title={absoluteDateTime(u.criado_em)}
                  >
                    <span className="text-text">{shortDate(u.criado_em)}</span>
                    <span className="ml-1 text-xs">
                      ({relativeTime(u.criado_em)})
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Badge status={u.ativa ? "ativo" : "inativo"} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        aria-label={`Ver UPF de ${u.nome_titular}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          goToDetail(u.id);
                        }}
                        className={actionBtn}
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        aria-label={`Editar UPF de ${u.nome_titular}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push(`/sgp/upfs/${u.id}/editar/`);
                        }}
                        className={actionBtn}
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
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
            {upfs.map((u) => (
              <li key={u.id}>
                <button
                  type="button"
                  onClick={() => goToDetail(u.id)}
                  className="flex w-full flex-col gap-2 rounded-lg border border-border bg-surface p-4 text-left transition-colors hover:bg-surface-warm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 flex-col leading-tight">
                      <span className="truncate font-medium text-text">
                        {u.nome_titular}
                      </span>
                      <span className="text-xs text-text-muted">
                        {u.cpf || "—"}
                      </span>
                    </div>
                    <Badge status={u.ativa ? "ativo" : "inativo"} />
                  </div>

                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
                    <span>{u.municipio || "—"}</span>
                    {u.territorio && <Chip>{u.territorio}</Chip>}
                  </div>

                  <div
                    className="text-xs text-text-muted"
                    title={absoluteDateTime(u.criado_em)}
                  >
                    Cadastrada em {shortDate(u.criado_em)}
                    <span className="ml-1">({relativeTime(u.criado_em)})</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
