"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { ApiError } from "@/app/lib/api";
import type { TipoSolicitacao } from "@/app/lib/camposSolicitacao";
import { formatCurrencyBRL } from "@/app/lib/format";
import { useDebounced } from "@/app/lib/hooks/useDebounced";
import { qk } from "@/app/lib/queryKeys";
import { consultarSaldo, type TravaSaldo } from "@/app/lib/solicitacoes";

function Trava({ titulo, trava, testId }: { titulo: string; trava: TravaSaldo; testId: string }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-border px-3 py-2.5" data-testid={testId}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-text-muted">{titulo}</span>
        <span className="flex items-center gap-1.5">
          <SemaforoBadge nivel={trava.semaforo_atual ?? "sem-dado"} compact />
          <ArrowRight className="h-3 w-3 text-text-muted" aria-label="depois desta solicitação" />
          <SemaforoBadge nivel={trava.semaforo_apos ?? "sem-dado"} />
        </span>
      </div>
      <p className="text-sm text-text">
        Disponível: <strong className="tabular-nums">{formatCurrencyBRL(trava.saldo)}</strong>
      </p>
      {!trava.disponivel && trava.motivo_bloqueio && (
        <p className="flex items-start gap-1.5 text-xs text-error-text">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          {trava.motivo_bloqueio}
        </p>
      )}
    </div>
  );
}

/**
 * Saldo das duas travas — o limite individual do solicitante na rubrica e a
 * verba do território — para o valor da solicitação (SGD-RF12, §4.1), antes
 * de submeter. Consulta `GET /sgd/saldo/` com debounce enquanto o valor muda.
 *
 * Em Devolvida, a submissão anterior já reservou o valor das solicitações que
 * ela levou: o saldo mostrado já o desconta.
 */
export function SaldoSolicitacao({
  atividadeId,
  tipo,
  valor,
  devolvida,
}: {
  atividadeId: number;
  tipo: TipoSolicitacao;
  /** Decimal "1234.56"; "0" mostra só o disponível. */
  valor: string;
  devolvida: boolean;
}) {
  const valorAdiado = useDebounced(valor);
  const saldo = useQuery({
    queryKey: qk.solicitacao.saldo(atividadeId, tipo, valorAdiado),
    queryFn: ({ signal }) => consultarSaldo({ atividadeId, tipo, valor: valorAdiado }, signal),
    placeholderData: (anterior) => anterior,
  });

  return (
    <section className="flex flex-col gap-2" aria-label="Saldo disponível" data-testid="saldo-solicitacao">
      <h3 className="flex items-center gap-2 text-sm font-medium text-text">
        Saldo {saldo.data ? `em ${saldo.data.rubrica_nome}` : ""}
        {saldo.isFetching && <Spinner className="h-3.5 w-3.5 animate-spin text-text-muted" />}
      </h3>
      {saldo.isPending ? (
        <p className="text-sm text-text-muted">Consultando o saldo…</p>
      ) : saldo.isError ? (
        <p role="alert" className="text-sm text-error-text">
          {saldo.error instanceof ApiError ? saldo.error.message : "Não foi possível consultar o saldo."}
        </p>
      ) : (
        <>
          <div className="grid gap-2 sm:grid-cols-2">
            <Trava titulo="Seu limite individual" trava={saldo.data.individual} testId="saldo-individual" />
            <Trava titulo="Verba do território" trava={saldo.data.territorial} testId="saldo-territorial" />
          </div>
          {devolvida && (
            <p className="text-xs text-text-muted">
              Demanda devolvida: o valor reservado na submissão anterior já está descontado do saldo.
            </p>
          )}
        </>
      )}
    </section>
  );
}
