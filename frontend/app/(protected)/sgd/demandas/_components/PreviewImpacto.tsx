"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import {
  previewDecisao,
  type FaixaSemaforo,
  type SolicitacaoDemanda,
} from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";

const DEBOUNCE_MS = 400;

const FAIXA: Record<FaixaSemaforo, { rotulo: string; classe: string }> = {
  verde: { rotulo: "Verde", classe: "bg-success-bg text-success-text border-success-text" },
  amarelo: { rotulo: "Amarelo", classe: "bg-warning-bg text-warning-text border-warning-text" },
  vermelho: { rotulo: "Vermelho", classe: "bg-error-bg text-error-text border-error-text" },
};

function Faixa({ faixa }: { faixa: FaixaSemaforo | null }) {
  if (!faixa) return <span className="text-text-muted">—</span>;
  const f = FAIXA[faixa];
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-2xs font-semibold ${f.classe}`}
      data-faixa={faixa}
    >
      {f.rotulo}
    </span>
  );
}

type Trava = { semaforo_antes: FaixaSemaforo | null; semaforo_apos: FaixaSemaforo | null; saldo_apos: number | string | null };

function LinhaTrava({ nome, trava }: { nome: string; trava: Trava }) {
  const mudou = trava.semaforo_antes !== trava.semaforo_apos;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
      <span className="text-text-muted">{nome}</span>
      <span className="flex items-center gap-1.5">
        <Faixa faixa={trava.semaforo_antes} />
        <ArrowRight className="h-3 w-3 text-text-muted" aria-label="passa para" />
        <Faixa faixa={trava.semaforo_apos} />
        {mudou && (
          <span className="font-medium text-warning-text" data-testid="preview-mudanca-faixa">
            muda de faixa
          </span>
        )}
      </span>
      <span className="w-full text-right tabular-nums text-text">
        Saldo após: {trava.saldo_apos === null ? "—" : formatCurrencyBRL(trava.saldo_apos)}
      </span>
    </div>
  );
}

/**
 * Preview do impacto de uma decisão no saldo da rubrica (#296, BE-3).
 *
 * Mostra, para as duas travas — limite individual do solicitante e pool
 * territorial —, a faixa do semáforo antes e depois e o saldo que sobra.
 * `valor` é o que a decisão vai reservar; muda ao ajustar o valor.
 */
export function PreviewImpacto({
  demandaId,
  solicitacao,
  valor,
}: {
  demandaId: number;
  solicitacao: SolicitacaoDemanda;
  valor: string;
}) {
  const [valorEstavel, setValorEstavel] = useState(valor);
  useEffect(() => {
    const t = setTimeout(() => setValorEstavel(valor), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [valor]);

  const valido = /^\d+(\.\d{1,2})?$/.test(valorEstavel);
  const { data, isFetching, error } = useQuery({
    queryKey: qk.demandas.preview(demandaId, solicitacao.id, valorEstavel),
    queryFn: ({ signal }) => previewDecisao(demandaId, solicitacao.id, valorEstavel, signal),
    enabled: valido,
    staleTime: 0,
  });

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border bg-surface-muted/40 px-3 py-2.5"
      data-testid={`preview-${solicitacao.id}`}
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-2 text-xs font-medium text-text">
        <span>
          {solicitacao.tipo_display} · {solicitacao.rubrica_nome}
        </span>
        {isFetching && <Spinner className="h-3.5 w-3.5 animate-spin text-text-muted" />}
      </div>
      {!valido ? (
        <p className="text-xs text-text-muted">Informe um valor válido para ver o impacto.</p>
      ) : error ? (
        <p className="text-xs text-error-text">
          {error instanceof ApiError ? error.message : "Não foi possível calcular o impacto."}
        </p>
      ) : data ? (
        <>
          <LinhaTrava nome="Limite individual" trava={data.individual} />
          <LinhaTrava nome="Pool territorial" trava={data.territorial} />
          {!data.disponivel && (
            <p className="text-xs font-medium text-error-text" data-testid="preview-bloqueio">
              {data.trava_bloqueada === "individual"
                ? "Este valor excede o limite individual do solicitante."
                : "Este valor excede o saldo do pool territorial."}
            </p>
          )}
        </>
      ) : null}
    </div>
  );
}
