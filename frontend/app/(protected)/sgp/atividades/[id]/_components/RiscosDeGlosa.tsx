"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { canVerRiscosDeGlosa } from "@/app/lib/auth/roles";
import {
  SEVERIDADE_GLOSA_LABEL,
  TIPO_RISCO_GLOSA_LABEL,
  listRiscosDeGlosaDaAtividade,
  riscosAbertos,
  totalExposto,
  type RiscoGlosa,
} from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";

/**
 * Cor da severidade, nos tokens semânticos: alta em erro, média em atenção e
 * baixa em neutro. O rótulo em texto acompanha sempre, para a cor não ser o
 * único portador do significado.
 */
const SEVERIDADE_CLASSE: Record<RiscoGlosa["severidade"], string> = {
  alta: "border-error-text bg-error-bg text-error-text",
  media: "border-warning-text bg-warning-bg text-warning-text",
  baixa: "border-neutral-text bg-neutral-bg text-neutral-text",
};

/**
 * Bloco "Riscos de glosa" da ficha da Atividade (#404, SGP §3.4): tipo,
 * severidade e valor exposto de cada risco em aberto, de
 * `GET /sgp/glosa-riscos/?activity=`.
 *
 * Só aparece quando há risco: sem risco, em carregamento ou em erro, não ocupa
 * espaço na ficha. O ADT não consulta a rota (`canVerRiscosDeGlosa`).
 */
export function RiscosDeGlosa({ atividadeId }: { atividadeId: number }) {
  const { data: session } = useSession();
  const podeVer = canVerRiscosDeGlosa(session?.user);

  const consulta = useQuery({
    queryKey: qk.demandas.glosasDaAtividade(atividadeId),
    queryFn: ({ signal }) => listRiscosDeGlosaDaAtividade(atividadeId, signal),
    enabled: podeVer,
  });

  const riscos = riscosAbertos(consulta.data);
  if (riscos.length === 0) return null;

  return (
    <section
      aria-labelledby="riscos-de-glosa-titulo"
      className="rounded-lg border border-warning-text bg-surface"
      data-testid="riscos-de-glosa"
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
        <h2 id="riscos-de-glosa-titulo" className="flex items-center gap-2 text-sm font-semibold text-text">
          <ShieldAlert className="h-4 w-4 text-warning-text" aria-hidden />
          Riscos de glosa
          <span className="text-xs font-normal tabular-nums text-text-muted">{riscos.length}</span>
        </h2>
        <p className="text-sm text-text-muted">
          Total exposto:{" "}
          <span className="font-semibold tabular-nums text-text" data-testid="riscos-de-glosa-total">
            {formatCurrencyBRL(totalExposto(riscos))}
          </span>
        </p>
      </header>
      <ul className="divide-y divide-border">
        {riscos.map((r) => (
          <li
            key={r.id}
            className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2.5"
            data-testid={`risco-de-glosa-${r.id}`}
          >
            <div className="flex min-w-0 flex-col gap-0.5">
              <span className="text-sm text-text">{TIPO_RISCO_GLOSA_LABEL[r.tipo] ?? r.tipo}</span>
              <Link
                href={`/sgd/demandas?visao=todas&demanda=${r.demanda_id}`}
                className="text-xs text-primary hover:underline"
              >
                Demanda #{r.demanda_id}
              </Link>
            </div>
            <span className="flex shrink-0 items-center gap-3">
              <span
                className={`rounded-full border px-2 py-0.5 text-xs font-medium ${SEVERIDADE_CLASSE[r.severidade]}`}
                data-testid={`risco-de-glosa-severidade-${r.id}`}
                data-severidade={r.severidade}
              >
                Severidade {SEVERIDADE_GLOSA_LABEL[r.severidade]?.toLowerCase() ?? r.severidade}
              </span>
              <span className="text-sm font-medium tabular-nums text-text">
                {formatCurrencyBRL(r.valor_exposto)}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
