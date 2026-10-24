"use client";

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { ApiError } from "@/app/lib/api";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import { simularDiarias, type SimulacaoDiarias as Simulacao } from "@/app/lib/solicitacoes";

const formatoDiarias = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

export type SimulacaoDiariasState = {
  /** Destino e datas preenchidos, com a volta depois da ida. */
  completo: boolean;
  simulacao: UseQueryResult<Simulacao>;
};

/**
 * `GET /sgd/config/diarias/simular/` (pendência 27) para o destino e as datas
 * do formulário. O formulário usa o total no saldo; o quadro abaixo, para
 * mostrar — a mesma consulta, deduplicada pelo React Query.
 */
export function useSimulacaoDiarias(municipioId: string, dataInicio: string, dataFim: string): SimulacaoDiariasState {
  const completo = !!municipioId && !!dataInicio && !!dataFim && dataFim >= dataInicio;
  const simulacao = useQuery({
    queryKey: qk.solicitacao.simulacaoDiarias(municipioId, dataInicio, dataFim),
    queryFn: ({ signal }) => simularDiarias({ municipioDestinoId: municipioId, dataInicio, dataFim }, signal),
    enabled: completo,
    retry: false,
  });
  return { completo, simulacao };
}

/**
 * Total das diárias em tempo real (#295): faixa do destino, valor unitário,
 * quantidade e total, recalculados quando destino ou datas mudam. O cálculo é
 * do backend — o front não repete a contagem nem lê o valor da diária.
 */
export function SimulacaoDiarias({ completo, simulacao }: SimulacaoDiariasState) {
  return (
    <section
      className="flex flex-col gap-1.5 rounded-md border border-border bg-surface-muted px-3 py-2.5"
      aria-label="Valor das diárias"
      data-testid="simulacao-diarias"
    >
      <h3 className="text-sm font-medium text-text">Valor das diárias</h3>
      {!completo ? (
        <p className="text-sm text-text-muted">
          Preencha o destino e as datas para ver a quantidade de diárias e o total.
        </p>
      ) : simulacao.isPending ? (
        <p className="text-sm text-text-muted">Calculando…</p>
      ) : simulacao.isError ? (
        <p role="alert" className="text-sm text-error-text" data-testid="simulacao-diarias-erro">
          {/* Um 400 traz o motivo (ex.: sem valor vigente); o resto não diz nada a quem preenche. */}
          {simulacao.error instanceof ApiError && simulacao.error.status === 400
            ? simulacao.error.message
            : "Não foi possível calcular as diárias agora."}{" "}
          O total é calculado pelo sistema ao salvar.
        </p>
      ) : (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm" data-testid="simulacao-diarias-resultado">
          <dt className="text-text-muted">Faixa de destino</dt>
          <dd className="text-text">{simulacao.data.faixa_destino.nome}</dd>
          <dt className="text-text-muted">Valor da diária</dt>
          <dd className="tabular-nums text-text">{formatCurrencyBRL(simulacao.data.valor_por_diaria)}</dd>
          <dt className="text-text-muted">Quantidade</dt>
          <dd className="tabular-nums text-text">
            {formatoDiarias.format(Number(simulacao.data.numero_diarias))} diária(s)
          </dd>
          <dt className="font-medium text-text">Total</dt>
          <dd className="font-medium tabular-nums text-text" data-testid="simulacao-diarias-total">
            {formatCurrencyBRL(simulacao.data.valor_total)}
          </dd>
        </dl>
      )}
    </section>
  );
}
