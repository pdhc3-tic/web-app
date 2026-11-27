"use client";

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { ApiError } from "@/app/lib/api";
import { formatarQuantidadeDeDiarias } from "@/app/lib/diarias";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import { simularDiarias, type SimulacaoDiarias as Simulacao } from "@/app/lib/solicitacoes";

export type SimulacaoDiariasState = {
  /** Destino e datas preenchidos, com a volta depois da ida. */
  completo: boolean;
  simulacao: UseQueryResult<Simulacao>;
};

/**
 * `GET /sgd/config/diarias/simular/` (pendência 27) para o destino e as datas
 * do formulário, e a hospedagem custeada por outro meio (#366), que muda a
 * contagem. O formulário usa o total no saldo; o quadro abaixo, para
 * mostrar — a mesma consulta, deduplicada pelo React Query.
 */
export function useSimulacaoDiarias(
  municipioId: string,
  dataInicio: string,
  dataFim: string,
  hospedagemCusteada = false,
): SimulacaoDiariasState {
  const completo = !!municipioId && !!dataInicio && !!dataFim && dataFim >= dataInicio;
  const simulacao = useQuery({
    queryKey: qk.solicitacao.simulacaoDiarias(municipioId, dataInicio, dataFim, hospedagemCusteada),
    queryFn: ({ signal }) =>
      simularDiarias({ municipioDestinoId: municipioId, dataInicio, dataFim, hospedagemCusteada }, signal),
    enabled: completo,
    retry: false,
  });
  return { completo, simulacao };
}

/**
 * Por que a diária não pode ser salva com o destino e as datas do formulário,
 * ou null quando pode (#440).
 *
 * A simulação usa o mesmo cálculo da gravação (`calcular_diarias`), então um
 * 400 dela é a recusa que o backend daria ao salvar — sem valor vigente na
 * tabela para a faixa, faixa inativa, datas trocadas. Erro de rede ou 5xx não
 * bloqueia: aí quem decide é o backend ao gravar. Um total zerado também
 * bloqueia: a issue pede que nenhuma diária seja salva com R$ 0,00.
 */
export function bloqueioDaDiaria({ completo, simulacao }: SimulacaoDiariasState): string | null {
  if (!completo) return null;
  if (simulacao.isError) {
    const erro = simulacao.error;
    return erro instanceof ApiError && erro.status === 400 ? erro.message : null;
  }
  if (simulacao.isSuccess && !(Number(simulacao.data.valor_total) > 0)) {
    return "O cálculo das diárias deu R$ 0,00.";
  }
  return null;
}

/** O 400 é a falta de valor na tabela de diárias, e não um dado do formulário. */
function semValorNaTabela(erro: unknown): boolean {
  return (
    erro instanceof ApiError &&
    (erro.fieldErrors ?? []).some((fe) => fe.field === "valor_por_diaria")
  );
}

/**
 * Total das diárias em tempo real (#295): faixa do destino, valor unitário,
 * quantidade e total, recalculados quando destino ou datas mudam. O cálculo é
 * do backend — o front não repete a contagem nem lê o valor da diária.
 *
 * Quando o cálculo é recusado (#440), o quadro vira o aviso de bloqueio: o
 * formulário não salva. `congelada` é a edição de uma diária já gravada sem
 * mudar destino, datas nem hospedagem: o backend mantém o valor gravado e
 * aceita salvar mesmo sem tabela vigente, então o aviso só informa.
 */
export function SimulacaoDiarias({
  completo,
  simulacao,
  congelada = false,
}: SimulacaoDiariasState & { congelada?: boolean }) {
  const bloqueio = bloqueioDaDiaria({ completo, simulacao });
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
      ) : bloqueio ? (
        <div role="alert" className="flex flex-col gap-1 text-sm text-error-text" data-testid="simulacao-diarias-erro">
          <p className="flex items-start gap-1.5">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span>{bloqueio}</span>
          </p>
          <p data-testid="simulacao-diarias-bloqueio">
            {congelada
              ? "Destino e datas não mudaram, então o valor calculado quando a solicitação foi salva continua valendo."
              : semValorNaTabela(simulacao.error)
                ? "A solicitação não pode ser salva enquanto não houver valor de diária vigente para este destino. A FGD ou o Super Admin cadastra o valor na Tabela de diárias."
                : "A solicitação não pode ser salva com este destino e estas datas."}
          </p>
        </div>
      ) : simulacao.isError ? (
        <p role="alert" className="text-sm text-error-text" data-testid="simulacao-diarias-erro">
          Não foi possível calcular as diárias agora. O total é calculado pelo sistema ao salvar.
        </p>
      ) : (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm" data-testid="simulacao-diarias-resultado">
          <dt className="text-text-muted">Faixa de destino</dt>
          <dd className="text-text">{simulacao.data.faixa_destino.nome}</dd>
          <dt className="text-text-muted">Valor da diária</dt>
          <dd className="tabular-nums text-text">{formatCurrencyBRL(simulacao.data.valor_por_diaria)}</dd>
          <dt className="text-text-muted">Quantidade</dt>
          <dd className="tabular-nums text-text" data-testid="simulacao-diarias-quantidade">
            {formatarQuantidadeDeDiarias(simulacao.data.numero_diarias)}
          </dd>
          {Number(simulacao.data.adicional_embarque ?? 0) > 0 && (
            <>
              <dt className="text-text-muted">Adicional de embarque e desembarque</dt>
              <dd className="tabular-nums text-text" data-testid="simulacao-diarias-adicional">
                {formatCurrencyBRL(simulacao.data.adicional_embarque)}
              </dd>
            </>
          )}
          <dt className="font-medium text-text">Total</dt>
          <dd className="font-medium tabular-nums text-text" data-testid="simulacao-diarias-total">
            {formatCurrencyBRL(simulacao.data.valor_total)}
          </dd>
        </dl>
      )}
    </section>
  );
}
