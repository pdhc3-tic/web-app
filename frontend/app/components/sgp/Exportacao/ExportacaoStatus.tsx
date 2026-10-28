"use client";

import { AlertTriangle, CheckCircle2, Download, RotateCcw, X } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import Spinner from "@/app/components/icons/Spinner";
import { ProgressBar } from "@/app/components/ui/ProgressBar/ProgressBar";
import type { TarefaExportacao } from "@/app/lib/hooks/useExportacao";

type ExportacaoStatusProps = {
  tarefa: TarefaExportacao<unknown>;
  /** O que está sendo exportado, com a preposição: "de 1.234 UPFs", "do Plano de Trabalho". */
  objeto: string;
  /** Prefixo dos test ids (`{prefixo}-exportacao-status`, `{prefixo}-exportacao-dispensar`). */
  prefixo: string;
  baixando: boolean;
  erroAcompanhamento: string | null;
  onBaixar: () => void;
  onRepetir: () => void;
  onReconsultar: () => void;
  onDescartar: () => void;
};

/**
 * Faixa de acompanhamento de uma exportação em segundo plano (#240, A4 da #302).
 *
 * Fica acima da listagem e NÃO bloqueia a tela: o usuário segue filtrando e
 * navegando enquanto o arquivo é gerado. `role="status"` anuncia as mudanças
 * de estado para leitores de tela sem roubar o foco.
 */
export function ExportacaoStatus({
  tarefa,
  objeto,
  prefixo,
  baixando,
  erroAcompanhamento,
  onBaixar,
  onRepetir,
  onReconsultar,
  onDescartar,
}: ExportacaoStatusProps) {
  const { exportacao } = tarefa;

  const botaoFechar = (
    <Button
      size="sm"
      variant="ghost"
      onClick={onDescartar}
      aria-label="Dispensar aviso de exportação"
      data-testid={`${prefixo}-exportacao-dispensar`}
    >
      <X className="h-4 w-4" />
    </Button>
  );

  if (exportacao.status === "concluida" && tarefa.indisponivel) {
    // O download respondeu 410: o arquivo passou das 24 h e foi descartado.
    return (
      <div
        role="status"
        data-testid={`${prefixo}-exportacao-status`}
        data-status="expirada"
        className="flex flex-wrap items-center gap-3 rounded-lg border border-warning-text bg-warning-bg px-4 py-3"
      >
        <AlertTriangle className="h-5 w-5 shrink-0 text-warning-text" aria-hidden />
        <p className="flex-1 text-sm text-text">
          O arquivo da exportação {objeto} expirou (ele fica disponível por 24 horas).
        </p>
        <Button
          size="sm"
          variant="secondary"
          onClick={onRepetir}
          leftIcon={<RotateCcw className="h-4 w-4" />}
        >
          Gerar novamente
        </Button>
        {botaoFechar}
      </div>
    );
  }

  if (exportacao.status === "concluida") {
    return (
      <div
        role="status"
        data-testid={`${prefixo}-exportacao-status`}
        data-status="concluida"
        className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-success-bg px-4 py-3"
      >
        <CheckCircle2 className="h-5 w-5 shrink-0 text-success-text" aria-hidden />
        <p className="flex-1 text-sm text-text">
          Exportação {objeto} concluída.
        </p>
        <Button
          size="sm"
          onClick={onBaixar}
          loading={baixando}
          leftIcon={<Download className="h-4 w-4" />}
        >
          Baixar arquivo
        </Button>
        {botaoFechar}
      </div>
    );
  }

  if (exportacao.status === "erro") {
    return (
      <div
        role="status"
        data-testid={`${prefixo}-exportacao-status`}
        data-status="erro"
        className="flex flex-wrap items-center gap-3 rounded-lg border border-error bg-error-bg px-4 py-3"
      >
        <AlertTriangle className="h-5 w-5 shrink-0 text-error-text" aria-hidden />
        <p className="flex-1 text-sm text-text">
          A exportação falhou.{" "}
          {exportacao.erro || "Não foi possível gerar o arquivo."}
        </p>
        <Button
          size="sm"
          variant="secondary"
          onClick={onRepetir}
          leftIcon={<RotateCcw className="h-4 w-4" />}
        >
          Tentar novamente
        </Button>
        {botaoFechar}
      </div>
    );
  }

  const processando = exportacao.status === "processando";
  const pct = exportacao.progresso;

  return (
    <div
      role="status"
      data-testid={`${prefixo}-exportacao-status`}
      data-status={exportacao.status}
      className="flex flex-col gap-2 rounded-lg border border-border bg-info-bg px-4 py-3"
    >
      <div className="flex flex-wrap items-center gap-3">
        <Spinner className="h-4 w-4 shrink-0 animate-spin text-info-text" />
        <p className="flex-1 text-sm text-text">
          {processando
            ? `Gerando a exportação ${objeto}${pct !== null ? ` — ${Math.round(pct)}%` : ""}.`
            : `Exportação ${objeto} na fila.`}{" "}
          <span className="text-text-muted">
            Você pode continuar usando a tela; o arquivo fica disponível aqui ao terminar.
          </span>
        </p>
      </div>
      <ProgressBar
        value={processando ? pct : null}
        label={`Progresso da exportação ${objeto}`}
        valueText={pct !== null ? `${Math.round(pct)}%` : "Aguardando início"}
      />
      {erroAcompanhamento && (
        <div className="flex flex-wrap items-center gap-2 text-sm text-error-text">
          <span>{erroAcompanhamento}</span>
          <Button size="sm" variant="ghost" onClick={onReconsultar}>
            Consultar novamente
          </Button>
        </div>
      )}
    </div>
  );
}
