"use client";

import { useState } from "react";
import Link from "next/link";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Spinner from "@/app/components/icons/Spinner";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import { fetchExtrato, type LinhaDoExtrato, type SaldoDaRubrica } from "@/app/lib/meuSaldo";
import { TIPO_TRANSACAO_LABEL, valorNumerico } from "@/app/lib/orcamento";
import { qk } from "@/app/lib/queryKeys";

const TH = "px-3 py-2 text-left text-2xs font-medium uppercase tracking-[0.06em] text-text-muted";
const TD = "px-3 py-2.5 align-top";

/**
 * Uma linha do extrato (#401). O valor sai com o sinal do `efeito` — o que o
 * lançamento fez no disponível —, não do tipo: assim o front não decide se uma
 * "liberação" soma ou subtrai.
 */
export function LinhaExtrato({ linha }: { linha: LinhaDoExtrato }) {
  const efeito = valorNumerico(linha.efeito);
  const sinal = efeito > 0 ? "+" : efeito < 0 ? "−" : "";
  return (
    <tr className="border-b border-border last:border-b-0" data-testid={`extrato-linha-${linha.id}`}>
      <td className={`${TD} whitespace-nowrap text-text-muted`}>{absoluteDateTime(linha.criado_em)}</td>
      <td className={TD}>
        <span className="text-text" data-testid="extrato-tipo">
          {TIPO_TRANSACAO_LABEL[linha.tipo] ?? linha.tipo}
        </span>
        {linha.justificativa && (
          <p className="mt-0.5 line-clamp-2 text-xs text-text-muted" title={linha.justificativa}>
            {linha.justificativa}
          </p>
        )}
      </td>
      <td className={TD}>
        {linha.demanda_id ? (
          <Link
            href={`/sgd/demandas?demanda=${linha.demanda_id}`}
            className="text-primary hover:underline"
            data-testid="extrato-demanda"
          >
            #{linha.demanda_id}
          </Link>
        ) : (
          <span className="text-text-muted">—</span>
        )}
      </td>
      <td
        className={`${TD} text-right tabular-nums ${
          efeito < 0 ? "text-error-text" : efeito > 0 ? "text-success-text" : "text-text"
        }`}
        data-testid="extrato-valor"
      >
        {sinal}
        {formatCurrencyBRL(Math.abs(efeito))}
      </td>
      <td className={`${TD} text-right tabular-nums text-text`} data-testid="extrato-saldo-depois">
        {linha.saldo_posterior !== null ? formatCurrencyBRL(linha.saldo_posterior) : "—"}
      </td>
    </tr>
  );
}

/**
 * Extrato de uma rubrica do "Meu saldo" (#401): os lançamentos do limite
 * individual, do mais recente ao mais antigo, paginados pelo servidor. Por
 * padrão só o período vigente; a opção inclui os encerrados.
 */
export function ExtratoSlideOver({ saldo, onClose }: { saldo: SaldoDaRubrica | null; onClose: () => void }) {
  return (
    <SlideOver
      open={!!saldo}
      onClose={onClose}
      title={saldo ? `Extrato — ${saldo.rubrica_nome}` : "Extrato"}
      width="wide"
    >
      {/* `key`: trocar de rubrica recomeça da primeira página. */}
      {saldo && <Extrato key={saldo.rubrica} saldo={saldo} />}
    </SlideOver>
  );
}

function Extrato({ saldo }: { saldo: SaldoDaRubrica }) {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [historico, setHistorico] = useState(false);

  const extrato = useQuery({
    queryKey: qk.meuSaldo.extrato(saldo.rubrica, offset, limit, historico),
    queryFn: ({ signal }) => fetchExtrato(saldo.rubrica, { offset, limit, historico }, signal),
    placeholderData: keepPreviousData,
    staleTime: 0,
  });

  return (
    <div className="flex flex-col gap-4 px-4 py-4" data-testid="extrato">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-text-muted">
          Disponível agora:{" "}
          <strong className="tabular-nums text-text">{formatCurrencyBRL(saldo.disponivel)}</strong>
        </p>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-text">
          <input
            type="checkbox"
            checked={historico}
            onChange={(e) => {
              setHistorico(e.target.checked);
              setOffset(0);
            }}
            className="accent-primary"
            data-testid="extrato-historico"
          />
          Incluir períodos encerrados
        </label>
      </div>

      {extrato.isPending ? (
        <p role="status" className="flex items-center gap-2 text-sm text-text-muted">
          <Spinner className="h-4 w-4 animate-spin" /> Carregando o extrato…
        </p>
      ) : extrato.error ? (
        <TabErroSection
          message={extrato.error instanceof ApiError ? extrato.error.message : "Não foi possível carregar o extrato."}
          onRetry={() => void extrato.refetch()}
        />
      ) : extrato.data.count === 0 ? (
        <EmptyState
          title="Nenhum lançamento"
          description={
            historico
              ? "Ainda não houve movimento neste limite."
              : "Nenhum lançamento neste período. O limite que vem só do padrão do perfil ganha o primeiro lançamento na primeira reserva."
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm" data-testid="extrato-tabela">
              <thead className="border-b border-border bg-surface-muted/50">
                <tr>
                  <th className={TH}>Data</th>
                  <th className={TH}>Tipo</th>
                  <th className={TH}>Demanda</th>
                  <th className={`${TH} text-right`}>Valor</th>
                  <th className={`${TH} text-right`}>Saldo depois</th>
                </tr>
              </thead>
              <tbody>
                {extrato.data.results.map((l) => (
                  <LinhaExtrato key={l.id} linha={l} />
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            count={extrato.data.count}
            offset={offset}
            limit={limit}
            onOffsetChange={setOffset}
            onLimitChange={(n) => {
              setLimit(n);
              setOffset(0);
            }}
            pageSizes={[20, 50, 100]}
            itemNoun={{ one: "lançamento", other: "lançamentos" }}
          />
        </>
      )}
    </div>
  );
}
