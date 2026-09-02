"use client";

import { useRouter } from "next/navigation";
import { Pencil, Users } from "lucide-react";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { formatDate } from "@/app/lib/datetime";
import { badgeStatusFor, type AtividadeListItem } from "@/app/lib/atividades";

const TH_BASE =
  "sticky top-0 z-10 bg-surface-muted px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-[0.08em] text-text-muted whitespace-nowrap";

const actionBtn =
  "inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-text-muted transition-colors hover:border-border hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface";

type Props = {
  atividades: AtividadeListItem[];
  loading: boolean;
};

/** Período "01/03/2026 – 03/03/2026", colapsado quando início e fim coincidem. */
function periodo(inicio: string, fim: string): string {
  const de = formatDate(inicio);
  const ate = formatDate(fim);
  return de === ate ? de : `${de} – ${ate}`;
}

/**
 * Badge de status + badge "Atrasada" sobreposto.
 * `atrasada` vem calculado do backend e já é false em status terminais, então
 * basta obedecer ao campo.
 */
function StatusCell({ atividade }: { atividade: AtividadeListItem }) {
  return (
    <div className="flex flex-wrap items-center gap-1">
      <Badge
        status={badgeStatusFor(atividade.status)}
        label={atividade.status_display}
      />
      {atividade.atrasada && <Badge status="atrasada" />}
    </div>
  );
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <tr key={i} className="border-t border-border">
          {Array.from({ length: 7 }).map((__, j) => (
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
        <li key={i} className="rounded-lg border border-border bg-surface p-4">
          <div className="h-4 w-48 animate-pulse rounded bg-surface-muted" />
          <div className="mt-2 h-3 w-28 animate-pulse rounded bg-surface-muted" />
          <div className="mt-4 grid grid-cols-2 gap-2">
            <div className="h-3 animate-pulse rounded bg-surface-muted" />
            <div className="h-3 animate-pulse rounded bg-surface-muted" />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function AtividadesTable({ atividades, loading }: Props) {
  const router = useRouter();

  // Clicar na linha abre a FICHA, não o formulário: consultar é o caso comum, e
  // quem só tem leitura não deveria cair num modo de edição para ver os dados.
  function goToDetail(id: number) {
    router.push(`/sgp/atividades/${id}/`);
  }

  return (
    <>
      {/* Desktop — tabela (>= 768px) */}
      <div className="relative hidden max-h-[calc(100vh-24rem)] overflow-auto rounded-lg border border-border bg-surface md:block">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">
            Lista de atividades de campo registradas.
          </caption>
          <thead>
            <tr>
              <th scope="col" className={TH_BASE}>
                Atividade
              </th>
              <th scope="col" className={`${TH_BASE} w-40`}>
                Município
              </th>
              <th scope="col" className={`${TH_BASE} w-40`}>
                Técnico
              </th>
              <th scope="col" className={`${TH_BASE} w-50`}>
                Período
              </th>
              <th scope="col" className={`${TH_BASE} w-25`}>
                Participantes
              </th>
              <th scope="col" className={`${TH_BASE} w-45`}>
                Status
              </th>
              <th scope="col" className={`${TH_BASE} w-15`}>
                <span className="sr-only">Ações</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <SkeletonRows />
            ) : (
              atividades.map((a) => (
                <tr
                  key={a.id}
                  tabIndex={0}
                  onClick={() => goToDetail(a.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      goToDetail(a.id);
                    }
                  }}
                  className="cursor-pointer border-t border-border transition-colors hover:bg-surface-warm focus:bg-surface-warm focus:outline-none"
                >
                  <td className="px-4 py-3">
                    <div className="flex min-w-0 flex-col leading-tight">
                      <span className="truncate font-medium text-text">
                        {a.titulo}
                      </span>
                      <span className="text-xs text-text-muted">
                        {a.tipo_atividade_display}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {a.municipio_nome || "—"}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {a.tecnico_nome || "—"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-text">
                    {periodo(a.data_inicio, a.data_fim)}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    <span className="inline-flex items-center gap-1.5 tabular-nums">
                      <Users className="h-3.5 w-3.5" aria-hidden="true" />
                      {a.total_participantes}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusCell atividade={a} />
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      aria-label={`Editar atividade ${a.titulo}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        goToDetail(a.id);
                      }}
                      className={actionBtn}
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
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
            {atividades.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => goToDetail(a.id)}
                  className="flex w-full flex-col gap-2 rounded-lg border border-border bg-surface p-4 text-left transition-colors hover:bg-surface-warm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <div className="flex min-w-0 flex-col leading-tight">
                    <span className="truncate font-medium text-text">
                      {a.titulo}
                    </span>
                    <span className="text-xs text-text-muted">
                      {a.tipo_atividade_display}
                    </span>
                  </div>

                  <StatusCell atividade={a} />

                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
                    <span>{periodo(a.data_inicio, a.data_fim)}</span>
                    <span>{a.municipio_nome || "—"}</span>
                    <span className="inline-flex items-center gap-1 tabular-nums">
                      <Users className="h-3 w-3" aria-hidden="true" />
                      {a.total_participantes}
                    </span>
                  </div>

                  {a.tecnico_nome && (
                    <span className="text-xs text-text-muted">
                      Responsável: {a.tecnico_nome}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
