"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Button } from "@/app/components/ui/Button/Button";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { exportarParaArlo } from "@/app/lib/arlo";
import { listDemandas } from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";

const AUTORIZADAS = ["autorizada"] as const;
const TH = "px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-[0.06em] text-text-muted";
const TD = "px-4 py-3 align-middle";

/**
 * As demandas Autorizadas — o que vai para o Arlo — e o acionamento manual da
 * exportação. O backend exporta todas as autorizadas de uma vez, uma linha por
 * solicitação (rubrica), e registra a operação no histórico.
 */
export function ExportarArlo() {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [exportando, setExportando] = useState(false);

  const query = useQuery({
    queryKey: qk.demandas.lista([...AUTORIZADAS]),
    queryFn: ({ signal }) => listDemandas({ status: [...AUTORIZADAS] }, signal),
  });
  const demandas = query.data ?? [];
  const totalSolicitacoes = demandas.reduce((n, d) => n + d.solicitacoes.length, 0);

  async function exportar() {
    setExportando(true);
    try {
      const nome = await exportarParaArlo();
      showToast(`Download de ${nome} iniciado.`);
      void queryClient.invalidateQueries({ queryKey: qk.arlo.all });
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Não foi possível exportar para o Arlo.",
        "error",
      );
    } finally {
      setExportando(false);
    }
  }

  return (
    <section aria-labelledby="arlo-exportar-titulo" className="space-y-3" data-testid="arlo-exportar">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="arlo-exportar-titulo" className="text-base font-semibold text-text">
            Exportar para o Arlo
          </h2>
          <p className="mt-0.5 text-sm text-text-muted">
            Demandas autorizadas aguardando pagamento. O arquivo leva todas elas, uma linha por
            solicitação.
          </p>
        </div>
        <Button
          leftIcon={<Download className="h-4 w-4" aria-hidden />}
          onClick={exportar}
          loading={exportando}
          disabled={query.isPending || demandas.length === 0}
        >
          Exportar para Arlo
        </Button>
      </div>

      {query.isPending ? (
        <div className="flex items-center gap-2 py-6 text-sm text-text-muted">
          <Spinner className="h-4 w-4" /> Carregando demandas autorizadas…
        </div>
      ) : query.isError ? (
        <div role="alert" className="rounded-lg border border-error-text bg-error-bg px-4 py-3 text-sm text-error-text">
          {query.error instanceof ApiError
            ? query.error.message
            : "Não foi possível carregar as demandas autorizadas."}{" "}
          <button type="button" className="font-medium underline" onClick={() => void query.refetch()}>
            Tentar novamente
          </button>
        </div>
      ) : demandas.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted">
          Nenhuma demanda autorizada aguardando exportação.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border bg-surface">
            <table className="w-full text-sm" data-testid="arlo-autorizadas">
              <caption className="sr-only">Demandas autorizadas que entram na exportação</caption>
              <thead className="border-b border-border bg-surface-muted/50">
                <tr>
                  <th className={TH}>Demanda</th>
                  <th className={TH}>Solicitante</th>
                  <th className={TH}>Território</th>
                  <th className={`${TH} text-right`}>Solicitações</th>
                  <th className={`${TH} text-right`}>Valor autorizado</th>
                </tr>
              </thead>
              <tbody>
                {demandas.map((d) => (
                  <tr key={d.id} className="border-b border-border last:border-0">
                    <td className={TD}>
                      <span className="text-text-muted tabular-nums">#{d.id}</span>{" "}
                      <span className="font-medium text-text">{d.titulo}</span>
                    </td>
                    <td className={`${TD} text-text-muted`}>{d.solicitante_nome}</td>
                    <td className={`${TD} text-text-muted`}>{d.contexto?.territorio_nome ?? "—"}</td>
                    <td className={`${TD} text-right tabular-nums`}>{d.solicitacoes.length}</td>
                    <td className={`${TD} text-right tabular-nums`}>
                      {formatCurrencyBRL(d.valor_autorizado_total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-text-muted">
            {demandas.length} {demandas.length === 1 ? "demanda" : "demandas"} · {totalSolicitacoes}{" "}
            {totalSolicitacoes === 1 ? "linha" : "linhas"} no arquivo.
          </p>
        </>
      )}
    </section>
  );
}
