"use client";

import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { BellRing } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Button } from "@/app/components/ui/Button/Button";
import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { ApiError } from "@/app/lib/api";
import {
  ALERTAS_POR_PAGINA,
  FAIXA_ALERTA_LABEL,
  TIPO_ALERTA_LABEL,
  alvoDoAlerta,
  fetchAlertas,
  nivelDoAlerta,
  type FaixaAlerta,
  type FiltrosDeAlerta,
  type TipoAlerta,
} from "@/app/lib/alertasOrcamento";
import { formatDate } from "@/app/lib/datetime";
import { qk } from "@/app/lib/queryKeys";

const formatoPercentual = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

const SELECT =
  "h-8 rounded-md border border-border bg-surface px-2 text-sm text-text outline-none transition-colors hover:border-text-muted focus:border-primary";

/**
 * Painel de alertas orçamentários (#403): os alertas abertos do escopo do
 * perfil, filtráveis por tipo e por faixa. Usado no Painel de Orçamento e na
 * home do SGD.
 *
 * Quem não tem acesso ao orçamento recebe 403 de `GET /sgp/orcamento/alertas/`:
 * o painel some, em vez de mostrar erro numa tela que a pessoa pode usar.
 */
export function PainelAlertas({ titulo = "Alertas orçamentários" }: { titulo?: string }) {
  const [filtros, setFiltros] = useState<FiltrosDeAlerta>({ tipo: "", faixa: "" });
  const [limite, setLimite] = useState(ALERTAS_POR_PAGINA);

  const alertas = useQuery({
    queryKey: qk.alertasOrcamento(filtros, limite),
    queryFn: ({ signal }) => fetchAlertas({ ...filtros, limit: limite }, signal),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    retry: (tentativas, erro) => !(erro instanceof ApiError && erro.status === 403) && tentativas < 2,
  });

  if (alertas.error instanceof ApiError && alertas.error.status === 403) return null;

  function filtrar(patch: Partial<FiltrosDeAlerta>) {
    setFiltros((atual) => ({ ...atual, ...patch }));
    setLimite(ALERTAS_POR_PAGINA);
  }

  const itens = alertas.data?.results ?? [];
  const total = alertas.data?.count ?? 0;
  const filtrando = filtros.tipo !== "" || filtros.faixa !== "";

  return (
    <section
      className="flex min-w-0 flex-col rounded-lg border border-border bg-surface"
      aria-label={titulo}
      data-testid="painel-alertas-orcamento"
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text">
          {titulo}
          <span className="text-xs font-normal tabular-nums text-text-muted" data-testid="alertas-orcamento-total">
            {total}
          </span>
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-text-muted">
            Tipo
            <select
              className={SELECT}
              value={filtros.tipo}
              onChange={(e) => filtrar({ tipo: e.target.value as TipoAlerta | "" })}
              data-testid="alertas-orcamento-filtro-tipo"
            >
              <option value="">Todos</option>
              {(Object.keys(TIPO_ALERTA_LABEL) as TipoAlerta[]).map((t) => (
                <option key={t} value={t}>
                  {TIPO_ALERTA_LABEL[t]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-text-muted">
            Faixa
            <select
              className={SELECT}
              value={filtros.faixa}
              onChange={(e) => filtrar({ faixa: e.target.value as FaixaAlerta | "" })}
              data-testid="alertas-orcamento-filtro-faixa"
            >
              <option value="">Todas</option>
              {(Object.keys(FAIXA_ALERTA_LABEL) as FaixaAlerta[]).map((f) => (
                <option key={f} value={f}>
                  {FAIXA_ALERTA_LABEL[f]}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {alertas.isPending ? (
        <p role="status" className="flex items-center gap-2 px-4 py-6 text-sm text-text-muted">
          <Spinner className="h-4 w-4 animate-spin" /> Carregando alertas…
        </p>
      ) : alertas.error ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 px-4 py-4 text-sm text-error-text" data-testid="alertas-orcamento-erro">
          {alertas.error instanceof ApiError ? alertas.error.message : "Não foi possível carregar os alertas."}
          <Button variant="secondary" size="sm" onClick={() => void alertas.refetch()}>
            Tentar de novo
          </Button>
        </div>
      ) : itens.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-6 py-8 text-center" data-testid="alertas-orcamento-vazio">
          <span aria-hidden className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-muted text-text-muted">
            <BellRing className="h-5 w-5" />
          </span>
          <p className="text-sm font-medium text-text">
            {filtrando ? "Nenhum alerta com estes filtros" : "Nenhum alerta aberto"}
          </p>
          <p className="max-w-xs text-xs text-text-muted">
            {filtrando
              ? "Mude o tipo ou a faixa para ver os demais."
              : "O orçamento do seu escopo está dentro dos limites."}
          </p>
        </div>
      ) : (
        <>
          <ul
            className={`divide-y divide-border transition-opacity ${alertas.isPlaceholderData ? "opacity-60" : ""}`}
            aria-busy={alertas.isPlaceholderData}
          >
            {itens.map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3"
                data-testid={`alerta-orcamento-${a.id}`}
                data-tipo={a.tipo}
                data-faixa={a.faixa}
              >
                <div className="flex min-w-0 flex-col gap-0.5">
                  <span className="truncate text-sm font-medium text-text">{alvoDoAlerta(a)}</span>
                  <span className="text-xs text-text-muted">
                    {TIPO_ALERTA_LABEL[a.tipo] ?? a.tipo} · desde {formatDate(a.alertado_em)}
                  </span>
                </div>
                <span className="flex shrink-0 items-center gap-2">
                  <span className="text-xs tabular-nums text-text">
                    {formatoPercentual.format(Number(a.percentual_atingido))}%
                  </span>
                  <SemaforoBadge
                    nivel={nivelDoAlerta(a)}
                    label={a.faixa ? FAIXA_ALERTA_LABEL[a.faixa] : "Sem faixa"}
                  />
                </span>
              </li>
            ))}
          </ul>
          {total > itens.length && (
            <div className="border-t border-border px-4 py-2.5 text-center">
              <button
                type="button"
                onClick={() => setLimite((n) => n + ALERTAS_POR_PAGINA)}
                className="text-sm text-primary hover:underline"
                data-testid="alertas-orcamento-mais"
              >
                Ver mais ({itens.length} de {total})
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
