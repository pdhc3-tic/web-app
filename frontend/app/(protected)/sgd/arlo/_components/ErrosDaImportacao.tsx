"use client";

import { Badge, type BadgeStatus } from "@/app/components/ui/Badge/Badge";
import type { OperacaoArlo, StatusOperacaoArlo } from "@/app/lib/arlo";

const BADGE_DO_STATUS: Record<StatusOperacaoArlo, BadgeStatus> = {
  pendente: "agendado",
  processando: "em-andamento",
  concluido: "concluido",
  falhou: "nao-realizada",
};

export function StatusOperacao({ operacao }: { operacao: OperacaoArlo }) {
  return <Badge status={BADGE_DO_STATUS[operacao.status]} label={operacao.status_display} />;
}

/**
 * Nome da coluna da planilha para um campo do SGD, pelo mapeamento vigente na
 * operação (`mapeamento_snapshot.importacao`). Sem snapshot (ex.: operações do
 * seed), mostra o nome do campo.
 */
function colunaDoCampo(operacao: OperacaoArlo, campo: string): string {
  const importacao = operacao.mapeamento_snapshot?.importacao as
    | Record<string, { coluna?: string }>
    | undefined;
  return importacao?.[campo]?.coluna ?? campo;
}

const TH = "px-3 py-2 text-left text-2xs font-medium uppercase tracking-[0.06em] text-text-muted";

/**
 * Relatório de erros por linha de uma importação. As linhas recusadas não
 * impedem as demais: o resumo diz quantas entraram, e a tabela aponta a linha
 * da planilha, a coluna e o motivo de cada recusa.
 */
export function ErrosDaImportacao({ operacao }: { operacao: OperacaoArlo }) {
  const erros = [...operacao.erros_json].sort((a, b) => a.linha - b.linha);
  const falhou = operacao.status === "falhou";

  return (
    <div className="space-y-3" data-testid="arlo-erros">
      {!falhou && (
        <p className="text-sm text-text" data-testid="arlo-resumo">
          <strong>{operacao.registros_ok}</strong> de <strong>{operacao.total_registros}</strong>{" "}
          {operacao.total_registros === 1 ? "linha processada" : "linhas processadas"} com sucesso
          {erros.length > 0 && (
            <>
              {" · "}
              <span className="text-error-text">
                {erros.length} {erros.length === 1 ? "linha recusada" : "linhas recusadas"}
              </span>
            </>
          )}
          .
        </p>
      )}

      {erros.length > 0 && (
        <div className="max-h-80 overflow-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <caption className="sr-only">Linhas da planilha recusadas na importação</caption>
            <thead className="sticky top-0 border-b border-border bg-surface-muted">
              <tr>
                <th className={TH}>Linha</th>
                <th className={TH}>Coluna</th>
                <th className={TH}>Motivo</th>
              </tr>
            </thead>
            <tbody>
              {erros.map((e, i) => (
                <tr
                  key={`${e.linha}-${i}`}
                  className="border-b border-border last:border-0"
                  data-testid={`arlo-erro-linha-${e.linha}`}
                >
                  <td className="px-3 py-2 align-top tabular-nums font-medium text-text">{e.linha}</td>
                  <td className="px-3 py-2 align-top text-text-muted">
                    {e.campo ? colunaDoCampo(operacao, e.campo) : "—"}
                  </td>
                  <td className="px-3 py-2 align-top text-text">{e.erro}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
