"use client";

import { AlertTriangle } from "lucide-react";
import { Badge, type BadgeStatus } from "@/app/components/ui/Badge/Badge";
import type { DivergenciaArlo, OperacaoArlo, StatusOperacaoArlo } from "@/app/lib/arlo";
import { formatCurrencyBRL } from "@/app/lib/format";

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
  const divergencias = operacao.divergencias ?? [];
  const glosas = divergencias.filter((d) => d.risco_glosa).length;

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
          {glosas > 0 && (
            <>
              {" · "}
              <span className="font-medium text-error-text">
                {glosas} com risco de glosa
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

      {divergencias.length > 0 && <DivergenciasDaImportacao divergencias={divergencias} />}
    </div>
  );
}

/**
 * Linhas pagas com valor diferente do autorizado. Acima do autorizado é risco
 * de glosa: a linha vem destacada, primeiro, e o excedente não entra na
 * execução do orçamento. Abaixo, a sobra volta aos limites.
 */
function DivergenciasDaImportacao({ divergencias }: { divergencias: DivergenciaArlo[] }) {
  const ordenadas = [...divergencias].sort((a, b) => Number(b.risco_glosa) - Number(a.risco_glosa));
  return (
    <section className="space-y-2" aria-labelledby="arlo-divergencias-titulo" data-testid="arlo-divergencias">
      <h3 id="arlo-divergencias-titulo" className="text-sm font-semibold text-text">
        Pagamentos diferentes do autorizado
      </h3>
      <div className="max-h-80 overflow-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 border-b border-border bg-surface-muted">
            <tr>
              <th className={TH}>Demanda</th>
              <th className={`${TH} text-right`}>Autorizado</th>
              <th className={`${TH} text-right`}>Pago</th>
              <th className={`${TH} text-right`}>Diferença</th>
            </tr>
          </thead>
          <tbody>
            {ordenadas.map((d) => (
              <tr
                key={d.solicitacao_id}
                className={`border-b border-border last:border-0 ${d.risco_glosa ? "bg-error-bg" : ""}`}
                data-testid={`arlo-divergencia-${d.solicitacao_id}`}
              >
                <td className="px-3 py-2 align-top text-text">
                  <span className="font-medium">#{d.demanda_id}</span> {d.demanda_titulo}
                  {d.risco_glosa ? (
                    <span className="mt-1 flex items-center gap-1 text-xs font-medium text-error-text">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
                      Risco de glosa: pago acima do autorizado
                    </span>
                  ) : (
                    <span className="mt-1 block text-xs text-text-muted">
                      Pago abaixo do autorizado; a diferença voltou ao saldo
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 align-top text-right tabular-nums text-text-muted">
                  {formatCurrencyBRL(d.valor_autorizado)}
                </td>
                <td className="px-3 py-2 align-top text-right tabular-nums text-text">
                  {formatCurrencyBRL(d.valor_pago)}
                </td>
                <td
                  className={`px-3 py-2 align-top text-right tabular-nums font-medium ${d.risco_glosa ? "text-error-text" : "text-text-muted"}`}
                >
                  {Number(d.diferenca) > 0 ? "+" : ""}
                  {formatCurrencyBRL(d.diferenca)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/**
 * Importação que falhou antes de ler as linhas (arquivo não encontrado ou
 * ilegível): nenhuma demanda foi alterada. O motivo gravado pelo backend (ex.:
 * colunas obrigatórias ausentes) vai como detalhe técnico, para o suporte.
 */
export function FalhaDaImportacao({ operacao }: { operacao: OperacaoArlo }) {
  const detalhe = operacao.erros_json[0]?.erro;
  return (
    <div role="alert" className="space-y-1 text-sm" data-testid="arlo-falha">
      <p className="font-medium text-error-text">
        Não foi possível processar a planilha, e nenhuma demanda foi alterada.
      </p>
      <p className="text-text">
        Envie a planilha de novo. Se a falha continuar, avise o suporte informando o detalhe abaixo.
      </p>
      {detalhe && (
        <p className="text-xs text-text-muted" data-testid="arlo-falha-detalhe">
          Detalhe técnico: {detalhe}
        </p>
      )}
    </div>
  );
}
