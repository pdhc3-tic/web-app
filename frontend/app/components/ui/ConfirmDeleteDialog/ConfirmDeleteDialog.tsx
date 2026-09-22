"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { ApiError } from "@/app/lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Título do SlideOver — ex.: "Remover membro". */
  title: string;
  /** Nome/descrição do item que aparece em negrito na pergunta. */
  itemName: string;
  /**
   * Frase abaixo da pergunta. Default cobre a maioria dos casos; passe uma
   * versão específica quando a ação tiver efeito colateral (ex.: "registra
   * no histórico" para membros da UPF).
   */
  description?: string;
  /**
   * Executa a operação assíncrona de exclusão. O diálogo gerencia loading,
   * erro (com fallback para `ApiError.message`) e fechamento em caso de
   * sucesso — o caller só passa o efeito colateral (chamar a API + limpar
   * cache local).
   */
  onConfirm: () => Promise<void>;
};

const DESCRICAO_PADRAO = "Esta ação não pode ser desfeita.";

/**
 * Diálogo de confirmação para exclusões destrutivas (SGP e demais módulos).
 *
 * Substitui os antigos `RemoverMembroDialog`, `RemoverProducaoDialog` e
 * `RemoverDocumentoDialog`, que reproduziam a mesma estrutura com pequenas
 * divergências de texto e tratamento de erro. Aqui:
 *
 * - `title` e `itemName` são os únicos textos obrigatórios; `description`
 *   tem default sensato.
 * - Erros são normalizados por `ApiError.message` — sem mais mensagens
 *   genéricas quando o backend explica o motivo (era a divergência entre
 *   RemoverMembro, que usava ApiError, e os outros dois, que engoliam).
 * - Fechar durante o loading é ignorado; o botão de cancelar fica desabilitado.
 */
export function ConfirmDeleteDialog({
  open,
  onClose,
  title,
  itemName,
  description = DESCRICAO_PADRAO,
  onConfirm,
}: Props) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    if (deleting) return;
    setError(null);
    setDeleting(true);
    try {
      await onConfirm();
    } catch (e: unknown) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Não foi possível remover. Tente novamente.",
      );
    } finally {
      setDeleting(false);
    }
  }

  return (
    <SlideOver
      open={open}
      onClose={deleting ? () => {} : onClose}
      title={title}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={deleting}>
            Cancelar
          </Button>
          <Button variant="danger" onClick={handleConfirm} loading={deleting}>
            Confirmar
          </Button>
        </div>
      }
    >
      <div
        className="flex flex-col gap-4 px-4 py-6"
        data-testid="confirm-delete-dialog"
      >
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium text-text">
              Remover <span className="font-semibold">{itemName}</span>?
            </p>
            <p className="mt-1 text-sm leading-relaxed text-text-muted">
              {description}
            </p>
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text"
          >
            {error}
          </div>
        )}
      </div>
    </SlideOver>
  );
}
