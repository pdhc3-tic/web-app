"use client";

import { AlertTriangle, Pencil, PlusCircle, Trash2 } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { resumoSolicitacao } from "@/app/lib/camposSolicitacao";
import type { SolicitacaoDemanda } from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import type { BloqueioSolicitacao } from "@/app/lib/solicitacoes";

const ORIENTACAO: Record<BloqueioSolicitacao["acao_sugerida"], string> = {
  solicitar_recurso_extra: "Peça recurso extra para cobrir a diferença.",
  acionar_articulador: "Acione o Articulador Estadual para remanejar verba ao território.",
};

/**
 * Uma solicitação da demanda em montagem: o que é, quanto custa e, depois de
 * uma submissão barrada, qual trava barrou, com o disponível e o solicitado
 * do `INSUFFICIENT_BALANCE` (#359), e o que fazer (§4.1):
 * - limite individual → atalho "Solicitar recurso extra" (#321);
 * - verba do território → orienta acionar o Articulador Estadual; sem atalho.
 */
export function SolicitacaoCartao({
  solicitacao,
  bloqueio,
  onEditar,
  onRemover,
  onRecursoExtra,
}: {
  solicitacao: SolicitacaoDemanda;
  bloqueio?: BloqueioSolicitacao;
  onEditar: () => void;
  onRemover: () => void;
  onRecursoExtra: () => void;
}) {
  const resumo = resumoSolicitacao(solicitacao.tipo, solicitacao.campos_json);

  return (
    <li
      className={`flex flex-col gap-3 rounded-lg border bg-surface px-4 py-3 ${
        bloqueio ? "border-error-text" : "border-border"
      }`}
      data-testid={`solicitacao-${solicitacao.id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-text">{solicitacao.tipo_display}</p>
          {resumo && <p className="mt-0.5 truncate text-xs text-text-muted">{resumo}</p>}
          <p className="mt-0.5 text-xs text-text-muted">Rubrica: {solicitacao.rubrica_nome}</p>
        </div>
        <div className="flex items-center gap-1">
          <span className="mr-2 text-sm font-medium tabular-nums text-text" data-testid={`solicitacao-valor-${solicitacao.id}`}>
            {formatCurrencyBRL(solicitacao.valor_estimado)}
          </span>
          <button
            type="button"
            onClick={onEditar}
            aria-label={`Editar ${solicitacao.tipo_display}`}
            className="rounded p-1.5 text-text-muted hover:text-text"
            data-testid={`solicitacao-editar-${solicitacao.id}`}
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onRemover}
            aria-label={`Remover ${solicitacao.tipo_display}`}
            className="rounded p-1.5 text-text-muted hover:text-error-text"
            data-testid={`solicitacao-remover-${solicitacao.id}`}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {solicitacao.alerta_rubrica_fora_do_previsto && (
        // RF22: alerta, não bloqueio.
        <p className="flex items-start gap-1.5 rounded border border-warning-text bg-warning-bg px-2 py-1.5 text-xs text-warning-text">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          A rubrica “{solicitacao.rubrica_nome}” não está entre as previstas na Ação desta atividade.
        </p>
      )}

      {bloqueio && (
        <div
          role="alert"
          className="flex flex-col gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
          data-testid={`bloqueio-${solicitacao.id}`}
        >
          <p className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <strong>
              {bloqueio.trava === "individual"
                ? "Limite individual insuficiente."
                : "Verba do território insuficiente."}
            </strong>
          </p>
          <p className="pl-6 tabular-nums" data-testid={`bloqueio-valores-${solicitacao.id}`}>
            {bloqueio.trava === "individual" ? "Disponível no seu limite" : "Disponível na verba do território"}:{" "}
            {formatCurrencyBRL(bloqueio.disponivel)} · Solicitado: {formatCurrencyBRL(bloqueio.solicitado)}
          </p>
          <p className="pl-6">{ORIENTACAO[bloqueio.acao_sugerida]}</p>
          {/* A trava territorial não tem atalho: quem remaneja é o Articulador. */}
          {bloqueio.acao_sugerida === "solicitar_recurso_extra" && (
            <div className="pl-6">
              <Button
                size="sm"
                variant="secondary"
                leftIcon={<PlusCircle className="h-4 w-4" />}
                onClick={onRecursoExtra}
                data-testid={`recurso-extra-atalho-${solicitacao.id}`}
              >
                Solicitar recurso extra
              </Button>
            </div>
          )}
        </div>
      )}
    </li>
  );
}
