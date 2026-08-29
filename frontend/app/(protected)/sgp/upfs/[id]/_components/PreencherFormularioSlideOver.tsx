"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ClipboardList } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime, formatDate } from "@/app/lib/datetime";
import {
  listAvailableForms,
  type AvailableForm,
} from "@/app/lib/formularios";

type Props = {
  open: boolean;
  onClose: () => void;
  upfId: string | number;
};

/**
 * Seletor de formulários publicados que a UPF pode responder (#181).
 *
 * Consome `GET /api/v1/sgp/formularios-disponiveis/` (BE-18). Ao escolher um
 * formulário, redireciona para o placeholder do motor de preenchimento do
 * SGF: `/sgf/formularios/{id}/preencher?upf={upfId}` — namespace `/sgf/`
 * reserva o caminho pra quando o motor real for entregue.
 */
export function PreencherFormularioSlideOver({
  open,
  onClose,
  upfId,
}: Props) {
  const router = useRouter();
  const [forms, setForms] = useState<AvailableForm[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    listAvailableForms(controller.signal)
      .then(setForms)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar os formulários disponíveis.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [open, reloadKey]);

  function escolher(form: AvailableForm) {
    onClose();
    router.push(
      `/sgf/formularios/${form.id}/preencher?upf=${encodeURIComponent(String(upfId))}`,
    );
  }

  const footer = (
    <div className="flex justify-end">
      <Button variant="secondary" onClick={onClose}>
        Cancelar
      </Button>
    </div>
  );

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title="Preencher novo formulário"
      footer={footer}
    >
      <div
        className="flex flex-col gap-4 px-4 py-4"
        data-testid="preencher-formulario-slideover"
      >
        <p className="text-sm text-text-muted">
          Escolha um formulário publicado. O preenchimento acontece no motor do
          SGF; a UPF é passada como contexto.
        </p>

        {loading ? (
          <div className="flex min-h-[20vh] items-center justify-center">
            <Spinner className="h-6 w-6 animate-spin text-text-muted" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-12 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <p className="max-w-sm text-sm text-text-muted">{error}</p>
            <Button
              variant="secondary"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              Tentar novamente
            </Button>
          </div>
        ) : forms.length === 0 ? (
          <EmptyState
            icon={<ClipboardList className="h-7 w-7" />}
            title="Nenhum formulário disponível"
            description="Publique ao menos um formulário com escopo UPF no SGF para que ele apareça aqui."
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {forms.map((form) => (
              <li key={form.id}>
                <button
                  type="button"
                  data-testid={`formulario-disponivel-${form.id}`}
                  onClick={() => escolher(form)}
                  className="w-full rounded-lg border border-border bg-surface px-4 py-3 text-left transition hover:border-primary hover:bg-surface-muted/40 focus-visible:border-2 focus-visible:border-primary focus-visible:outline-none"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="text-sm font-medium text-text">
                      {form.nome}
                    </p>
                    <span className="text-2xs text-text-muted">
                      v{form.versao}
                    </span>
                  </div>
                  {form.descricao ? (
                    <p className="mt-1 text-xs text-text-muted">
                      {form.descricao}
                    </p>
                  ) : null}
                  <p
                    className="mt-1 text-2xs text-text-muted"
                    title={absoluteDateTime(form.atualizado_em)}
                  >
                    Atualizado em {formatDate(form.atualizado_em)}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </SlideOver>
  );
}
