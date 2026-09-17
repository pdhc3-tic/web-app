"use client";

import { useState } from "react";
import { AlertTriangle, ArrowRight, ImagePlus } from "lucide-react";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { ApiError } from "@/app/lib/api";
import {
  badgeStatusFor,
  exigenciasDaTransicao,
  statusLabel,
  transicionarStatus,
  type AtividadeDetail,
} from "@/app/lib/atividades";

type Props = {
  open: boolean;
  onClose: () => void;
  atividade: AtividadeDetail;
  /** Recebe a atividade já atualizada — a ficha troca o badge sem recarregar. */
  onTransicionado: (atualizada: AtividadeDetail) => void;
  /** Leva o usuário às evidências quando falta anexo para concluir. */
  onIrParaEvidencias?: () => void;
};

/**
 * Fluxo guiado de transição de status (Issue #234).
 *
 * A máquina de estados vive no backend (`STATUS_TRANSITIONS` em
 * models/activity.py) e é a autoridade. Este diálogo existe para que o técnico
 * conheça as regras ANTES de submeter, em vez de descobri-las num 400: oferece
 * só os destinos que `transicoes_permitidas` autoriza e coleta, para cada um,
 * o que aquele destino exige.
 */
export function TransicaoStatusDialog({
  open,
  onClose,
  atividade,
  onTransicionado,
  onIrParaEvidencias,
}: Props) {
  const [destino, setDestino] = useState("");
  const [justificativa, setJustificativa] = useState("");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [erroCampo, setErroCampo] = useState<Record<string, string>>({});

  // Reflete a atividade vigente a cada abertura e esquece a tentativa anterior.
  // Ajuste durante a renderização — não há sistema externo a sincronizar.
  const [abertoAnterior, setAbertoAnterior] = useState(open);
  if (open !== abertoAnterior) {
    setAbertoAnterior(open);
    if (open) {
      setDestino("");
      setJustificativa("");
      setDataInicio("");
      setDataFim("");
      setErro(null);
      setErroCampo({});
    }
  }

  const exigencias = destino
    ? exigenciasDaTransicao(atividade.status, destino)
    : { justificativa: false, novaData: false, evidencia: false };

  const temEvidencia =
    (atividade.fotos?.length ?? 0) > 0 || (atividade.documentos?.length ?? 0) > 0;

  // O aviso aparece ANTES da submissão — é o que o critério pede. O backend
  // recusaria de todo jeito, mas aí o usuário já teria perdido a viagem.
  const faltaEvidencia = exigencias.evidencia && !temEvidencia;

  const opcoes = atividade.transicoes_permitidas.map((s) => ({
    value: s,
    label: statusLabel(s),
  }));

  function validar(): boolean {
    const errs: Record<string, string> = {};
    if (!destino) {
      errs.status = "Escolha o novo status.";
    }
    if (exigencias.justificativa && !justificativa.trim()) {
      errs.justificativa = `Justificativa é obrigatória para "${statusLabel(destino)}".`;
    }
    if (exigencias.novaData && !dataInicio) {
      errs.data_inicio = "Informe a nova data de início do reagendamento.";
    }
    if (exigencias.novaData && dataInicio && dataFim && dataFim < dataInicio) {
      errs.data_fim = "A data de fim não pode ser anterior à de início.";
    }
    setErroCampo(errs);
    return Object.keys(errs).length === 0;
  }

  const bloqueado = faltaEvidencia || !destino;

  async function handleConfirmar() {
    if (enviando || bloqueado) return;
    if (!validar()) return;

    setErro(null);
    setEnviando(true);
    try {
      const atualizada = await transicionarStatus(atividade.id, {
        status: destino,
        ...(exigencias.justificativa ? { justificativa: justificativa.trim() } : {}),
        ...(exigencias.novaData && dataInicio ? { data_inicio: dataInicio } : {}),
        ...(exigencias.novaData && dataFim ? { data_fim: dataFim } : {}),
      });
      onTransicionado(atualizada);
      onClose();
    } catch (e: unknown) {
      // O preenchimento NÃO é limpo: o critério pede que o erro do servidor
      // apareça sem custar ao usuário o que ele já escreveu.
      if (e instanceof ApiError && e.fieldErrors?.length) {
        const mapa: Record<string, string> = {};
        for (const fe of e.fieldErrors) mapa[fe.field] = fe.message;
        setErroCampo(mapa);
        setErro(e.message);
      } else {
        setErro(
          e instanceof ApiError
            ? e.message
            : "Não foi possível alterar o status. Tente novamente.",
        );
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <SlideOver
      open={open}
      onClose={enviando ? () => {} : onClose}
      title="Alterar status da atividade"
      modal
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={enviando}
            data-testid="transicao-cancelar"
          >
            Cancelar
          </Button>
          <Button
            onClick={handleConfirmar}
            loading={enviando}
            disabled={bloqueado}
            data-testid="transicao-confirmar"
          >
            Confirmar
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4 p-4" data-testid="transicao-dialog">
        {/* De → para, para o usuário confirmar o que está prestes a fazer. */}
        <div className="flex flex-wrap items-center gap-2 text-sm text-text-muted">
          <Badge
            status={badgeStatusFor(atividade.status)}
            label={statusLabel(atividade.status)}
          />
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
          {destino ? (
            <Badge status={badgeStatusFor(destino)} label={statusLabel(destino)} />
          ) : (
            <span className="text-text-muted">escolha abaixo</span>
          )}
        </div>

        <div data-testid="transicao-destino">
          <Select
            label="Novo status"
            required
            options={opcoes}
            value={destino}
            onChange={(v) => {
              setDestino(v);
              setErroCampo({});
              setErro(null);
            }}
            placeholder="Selecione..."
            error={erroCampo.status}
            disabled={enviando}
            helperText="Só aparecem os destinos válidos a partir do status atual."
          />
        </div>

        {exigencias.justificativa && (
          <div data-testid="transicao-justificativa">
            <Textarea
              label="Justificativa"
              required
              rows={4}
              value={justificativa}
              onChange={(e) => setJustificativa(e.target.value)}
              error={erroCampo.justificativa}
              disabled={enviando}
              helperText={`Obrigatória para "${statusLabel(destino)}".`}
            />
          </div>
        )}

        {exigencias.novaData && (
          <div className="flex flex-col gap-3" data-testid="transicao-nova-data">
            <p className="text-xs text-text-muted">
              Reagendar exige uma nova data — sem ela a atividade voltaria a
              &quot;Agendado&quot; mantendo a data que já passou.
            </p>
            <div className="flex flex-wrap gap-3">
              <Input
                type="datetime-local"
                label="Nova data de início"
                required
                className="min-w-48 flex-1"
                value={dataInicio}
                onChange={(e) => setDataInicio(e.target.value)}
                error={erroCampo.data_inicio}
                disabled={enviando}
                data-testid="transicao-data-inicio"
              />
              <Input
                type="datetime-local"
                label="Nova data de fim"
                className="min-w-48 flex-1"
                value={dataFim}
                onChange={(e) => setDataFim(e.target.value)}
                error={erroCampo.data_fim}
                disabled={enviando}
                data-testid="transicao-data-fim"
              />
            </div>
          </div>
        )}

        {faltaEvidencia && (
          <div
            className="flex flex-col gap-2 rounded-md border border-warning-text bg-warning-bg px-3 py-2.5 text-sm text-warning-text"
            role="alert"
            data-testid="transicao-aviso-evidencia"
          >
            <span className="inline-flex items-center gap-1.5 font-medium">
              <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
              Falta evidência para concluir
            </span>
            <p className="text-xs leading-relaxed">
              Concluir exige ao menos uma foto ou documento anexado. Anexe a
              evidência e volte aqui — ou registre como &quot;Concluído sem
              evidência&quot;, se for o caso.
            </p>
            {onIrParaEvidencias && (
              <Button
                size="sm"
                variant="secondary"
                leftIcon={<ImagePlus className="h-3.5 w-3.5" />}
                onClick={() => {
                  onClose();
                  onIrParaEvidencias();
                }}
                data-testid="transicao-ir-evidencias"
              >
                Anexar evidência
              </Button>
            )}
          </div>
        )}

        {erro && (
          <p
            className="rounded-md bg-error-bg px-3 py-2 text-sm text-error-text"
            role="alert"
            data-testid="transicao-erro"
          >
            {erro}
          </p>
        )}
      </div>
    </SlideOver>
  );
}
