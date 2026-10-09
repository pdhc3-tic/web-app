"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowDownToLine, ArrowUpFromLine } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import { listOperacoesArlo, operacaoEmAndamento, type OperacaoArlo } from "@/app/lib/arlo";
import { absoluteDateTime } from "@/app/lib/datetime";
import { qk } from "@/app/lib/queryKeys";
import { ErrosDaImportacao, StatusOperacao } from "./ErrosDaImportacao";

const TH = "px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-[0.06em] text-text-muted";
const TD = "px-4 py-3 align-middle";

function IconeTipo({ op }: { op: OperacaoArlo }) {
  const Icone = op.tipo === "exportacao" ? ArrowUpFromLine : ArrowDownToLine;
  return (
    <span className="inline-flex items-center gap-1.5 text-text">
      <Icone className="h-4 w-4 text-text-muted" aria-hidden />
      {op.tipo_display}
    </span>
  );
}

/**
 * Histórico das exportações e importações (arquivo, data, quem operou e
 * registros processados). Clicar numa linha abre o detalhe, com o relatório de
 * erros por linha das importações.
 */
export function HistoricoArlo() {
  const [aberta, setAberta] = useState<OperacaoArlo | null>(null);
  const query = useQuery({
    queryKey: qk.arlo.operacoes,
    queryFn: ({ signal }) => listOperacoesArlo(signal),
    // Uma importação em andamento muda de status sozinha: acompanha até terminar.
    refetchInterval: (q) => (q.state.data?.some(operacaoEmAndamento) ? 3_000 : false),
  });
  const operacoes = query.data ?? [];
  // O detalhe acompanha a versão mais nova da operação aberta.
  const detalhe = aberta ? (operacoes.find((o) => o.id === aberta.id) ?? aberta) : null;

  return (
    <section aria-labelledby="arlo-historico-titulo" className="space-y-3" data-testid="arlo-historico">
      <div>
        <h2 id="arlo-historico-titulo" className="text-base font-semibold text-text">
          Histórico de operações
        </h2>
        <p className="mt-0.5 text-sm text-text-muted">
          Exportações e importações trocadas com o Arlo, da mais recente para a mais antiga.
        </p>
      </div>

      {query.isPending ? (
        <div className="flex items-center gap-2 py-6 text-sm text-text-muted">
          <Spinner className="h-4 w-4" /> Carregando histórico…
        </div>
      ) : query.isError ? (
        <div role="alert" className="rounded-lg border border-error-text bg-error-bg px-4 py-3 text-sm text-error-text">
          {query.error instanceof ApiError ? query.error.message : "Não foi possível carregar o histórico."}{" "}
          <button type="button" className="font-medium underline" onClick={() => void query.refetch()}>
            Tentar novamente
          </button>
        </div>
      ) : operacoes.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted">
          Nenhuma exportação ou importação feita ainda.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full text-sm">
            <caption className="sr-only">Histórico de operações com o Arlo</caption>
            <thead className="border-b border-border bg-surface-muted/50">
              <tr>
                <th className={TH}>Operação</th>
                <th className={TH}>Arquivo</th>
                <th className={TH}>Data</th>
                <th className={TH}>Operado por</th>
                <th className={`${TH} text-right`}>Registros</th>
                <th className={TH}>Situação</th>
              </tr>
            </thead>
            <tbody>
              {operacoes.map((op) => {
                const erros = op.erros_json.length;
                return (
                  <tr
                    key={op.id}
                    tabIndex={0}
                    role="button"
                    aria-label={`Ver detalhes: ${op.tipo_display} de ${absoluteDateTime(op.operado_em)}`}
                    onClick={() => setAberta(op)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setAberta(op);
                      }
                    }}
                    className="cursor-pointer border-b border-border last:border-0 hover:bg-surface-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
                    data-testid={`arlo-operacao-${op.id}`}
                  >
                    <td className={TD}>
                      <IconeTipo op={op} />
                    </td>
                    <td className={`${TD} max-w-[16rem] truncate text-text-muted`} title={op.nome_original}>
                      {op.nome_original || "—"}
                    </td>
                    <td className={`${TD} whitespace-nowrap tabular-nums text-text-muted`}>
                      {absoluteDateTime(op.operado_em)}
                    </td>
                    <td className={`${TD} text-text-muted`}>{op.operado_por_nome ?? "—"}</td>
                    <td className={`${TD} text-right tabular-nums`}>
                      {op.registros_ok}/{op.total_registros}
                      {erros > 0 && (
                        <span className="ml-2 text-xs text-error-text">
                          {erros} {erros === 1 ? "erro" : "erros"}
                        </span>
                      )}
                    </td>
                    <td className={TD}>
                      <StatusOperacao operacao={op} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <SlideOver
        open={detalhe !== null}
        onClose={() => setAberta(null)}
        title={detalhe ? `${detalhe.tipo_display} #${detalhe.id}` : ""}
        badge={detalhe ? <StatusOperacao operacao={detalhe} /> : undefined}
      >
        {detalhe && (
          <div className="flex flex-col gap-6 px-4 py-4" data-testid="arlo-operacao-detalhe">
            <DefinitionList
              items={[
                {
                  label: "Arquivo",
                  value: detalhe.arquivo_url ? (
                    <a href={detalhe.arquivo_url} target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline">
                      {detalhe.nome_original || "Baixar arquivo"}
                    </a>
                  ) : (
                    detalhe.nome_original || "—"
                  ),
                },
                { label: "Data", value: absoluteDateTime(detalhe.operado_em) ?? "—" },
                { label: "Operado por", value: detalhe.operado_por_nome ?? "—" },
                {
                  label: "Registros processados",
                  value: `${detalhe.registros_ok} de ${detalhe.total_registros}`,
                },
              ]}
            />
            {detalhe.tipo === "importacao" && detalhe.status === "concluido" && (
              <ErrosDaImportacao operacao={detalhe} />
            )}
            {detalhe.status === "falhou" && (
              <p role="alert" className="text-sm text-error-text">
                {detalhe.erros_json[0]?.erro ?? "O arquivo não pôde ser processado."}
              </p>
            )}
          </div>
        )}
      </SlideOver>
    </section>
  );
}
