"use client";

import { useEffect, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import {
  previewDecisao,
  type FaixaSemaforo,
  type PreviewDecisao,
  type SolicitacaoDemanda,
} from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";

const DEBOUNCE_MS = 400;
const VALOR_VALIDO = /^\d+(\.\d{1,2})?$/;

/** Estado do preview de UMA solicitação, como o rodapé de decisão o enxerga. */
export type EstadoPreview = {
  solicitacao: SolicitacaoDemanda;
  valorValido: boolean;
  carregando: boolean;
  erro: string | null;
  dados: PreviewDecisao | undefined;
};

/**
 * Previews de impacto de TODAS as solicitações de uma decisão (#296, BE-3) e
 * se a decisão pode ser confirmada.
 *
 * `liberado` só é verdadeiro quando cada preview terminou, sem erro, com o
 * valor estável (já passou o debounce) e `disponivel`. Enquanto o impacto não
 * puder ser validado, a confirmação fica bloqueada — e `motivo` diz por quê.
 */
export function usePreviewsDecisao(
  demandaId: number,
  itens: { solicitacao: SolicitacaoDemanda; valor: string }[],
) {
  const chaveAtual = itens.map((i) => `${i.solicitacao.id}:${i.valor}`).join("|");
  const [chaveEstavel, setChaveEstavel] = useState(chaveAtual);
  useEffect(() => {
    const t = setTimeout(() => setChaveEstavel(chaveAtual), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [chaveAtual]);
  const valoresEstaveis = new Map(
    chaveEstavel
      .split("|")
      .filter(Boolean)
      .map((par) => {
        const [id, valor] = par.split(":");
        return [Number(id), valor] as const;
      }),
  );

  const resultados = useQueries({
    queries: itens.map(({ solicitacao }) => {
      const valor = valoresEstaveis.get(solicitacao.id) ?? "";
      return {
        queryKey: qk.demandas.preview(demandaId, solicitacao.id, valor),
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          previewDecisao(demandaId, solicitacao.id, valor, signal),
        enabled: VALOR_VALIDO.test(valor),
        staleTime: 0,
        retry: false,
      };
    }),
  });

  const estados: EstadoPreview[] = itens.map(({ solicitacao }, i) => {
    const valor = valoresEstaveis.get(solicitacao.id) ?? "";
    const r = resultados[i];
    return {
      solicitacao,
      valorValido: VALOR_VALIDO.test(valor),
      carregando: r.isFetching || (VALOR_VALIDO.test(valor) && r.isPending),
      erro: r.error
        ? r.error instanceof ApiError
          ? r.error.message
          : "Não foi possível calcular o impacto."
        : null,
      dados: r.data,
    };
  });

  const estavel = chaveAtual === chaveEstavel;
  let motivo: string | null = null;
  if (estados.some((e) => !e.valorValido)) {
    motivo = "Informe um valor válido em todas as solicitações.";
  } else if (estavel && estados.some((e) => e.erro && !e.carregando)) {
    // Antes de "calculando": um preview com erro também não tem `dados`.
    motivo = "Não foi possível calcular o impacto no saldo. Tente novamente.";
  } else if (!estavel || estados.some((e) => e.carregando || !e.dados)) {
    motivo = "Calculando o impacto no saldo…";
  } else if (estados.some((e) => e.dados && !e.dados.disponivel)) {
    motivo = "O valor excede o saldo disponível: a decisão não pode ser confirmada.";
  }

  return {
    estados,
    liberado: motivo === null,
    motivo,
    tentarDeNovo: () => resultados.forEach((r) => r.error && void r.refetch()),
  };
}

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

type Trava = PreviewDecisao["individual"];

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
 * Preview do impacto de uma decisão no saldo da rubrica, para UMA solicitação:
 * para as duas travas — limite individual e pool territorial —, a faixa do
 * semáforo antes e depois e o saldo que sobra. Só exibe: quem consulta e
 * decide se a confirmação libera é `usePreviewsDecisao`.
 */
export function PreviewImpacto({ estado }: { estado: EstadoPreview }) {
  const { solicitacao, valorValido, carregando, erro, dados } = estado;
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
        {carregando && <Spinner className="h-3.5 w-3.5 animate-spin text-text-muted" />}
      </div>
      {!valorValido ? (
        <p className="text-xs text-text-muted">Informe um valor válido para ver o impacto.</p>
      ) : erro ? (
        <p className="text-xs text-error-text" data-testid="preview-erro">
          {erro}
        </p>
      ) : dados ? (
        <>
          <LinhaTrava nome="Limite individual" trava={dados.individual} />
          <LinhaTrava nome="Pool territorial" trava={dados.territorial} />
          {!dados.disponivel && (
            <p className="text-xs font-medium text-error-text" data-testid="preview-bloqueio">
              {dados.trava_bloqueada === "individual"
                ? "Este valor excede o limite individual do solicitante."
                : "Este valor excede o saldo do pool territorial."}
            </p>
          )}
        </>
      ) : null}
    </div>
  );
}
