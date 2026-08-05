"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, ExternalLink, MapPin, User } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import {
  getAtividade,
  statusLabel,
  type AtividadeDetail,
} from "@/app/lib/atividades";
import { formatDate } from "@/app/lib/datetime";
import type { CalendarActivityEvent } from "@/app/lib/atividadesCalendario";
import { statusHexColor } from "./statusColor";

type Props = {
  /** Evento clicado no calendário; provê preview instantâneo. */
  event: CalendarActivityEvent | null;
  open: boolean;
  onClose: () => void;
};

/**
 * Painel lateral com resumo do evento. O clique já traz os dados básicos vindos
 * do calendário, então mostramos preview enquanto buscamos o detalhe completo.
 */
export function EventoDetailsSlideOver({ event, open, onClose }: Props) {
  const [detalhe, setDetalhe] = useState<AtividadeDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !event) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDetalhe(null);
    setLoading(true);
    setError(null);
    getAtividade(event.id, controller.signal)
      .then((d) => {
        if (!controller.signal.aborted) setDetalhe(d);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar os dados da atividade.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [open, event]);

  const cor = event ? event.cor : statusHexColor("planejado");
  const linkFicha = event ? `/sgp/atividades/${event.id}/editar/` : "#";

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title="Detalhes da atividade"
      width="wide"
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Fechar
          </Button>
          <Button
            as="a"
            href={linkFicha}
            rightIcon={<ExternalLink className="h-4 w-4" />}
          >
            Abrir ficha completa
          </Button>
        </div>
      }
    >
      {event ? (
        <div className="flex flex-col gap-4 px-4 py-4">
          {/* Cabeçalho com título e status */}
          <div
            className="rounded-lg border border-border bg-surface p-4"
            style={{ borderLeftWidth: 4, borderLeftColor: cor }}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-semibold text-white"
                style={{ backgroundColor: cor }}
              >
                {event.status_display}
              </span>
              {event.atrasada && (
                <span className="inline-flex items-center gap-1 rounded-full bg-error-bg px-2 py-0.5 text-2xs font-semibold text-error-text">
                  <AlertTriangle className="h-3 w-3" />
                  Atrasada
                </span>
              )}
              <span className="text-2xs uppercase tracking-wide text-text-muted">
                {event.tipo_atividade_display}
              </span>
            </div>
            <h3 className="mt-2 text-lg font-semibold leading-snug text-text">
              {event.titulo}
            </h3>
            <p className="mt-1 text-sm text-text-muted">
              {formatDate(event.data_inicio)}
              {event.data_inicio !== event.data_fim && (
                <> — {formatDate(event.data_fim)}</>
              )}
            </p>
          </div>

          {/* Contexto do evento */}
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <InfoItem
              icon={<User className="h-4 w-4" aria-hidden="true" />}
              label="Técnico responsável"
              value={event.tecnico_responsavel.nome}
            />
            <InfoItem
              icon={<MapPin className="h-4 w-4" aria-hidden="true" />}
              label="Local"
              value={
                event.comunidade
                  ? `${event.municipio.nome} · ${event.comunidade.nome}`
                  : event.municipio.nome
              }
            />
          </dl>

          {/* Detalhes carregados */}
          <div className="rounded-lg border border-border bg-surface p-4">
            <h4 className="text-sm font-semibold text-text">Resumo</h4>

            {loading && (
              <p className="mt-3 inline-flex items-center gap-2 text-sm text-text-muted">
                <Spinner className="h-4 w-4 animate-spin" />
                Carregando resumo…
              </p>
            )}

            {error && !loading && (
              <p
                role="alert"
                className="mt-3 inline-flex items-start gap-2 text-sm text-error-text"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                {error}
              </p>
            )}

            {detalhe && !loading && !error && (
              <div className="mt-3 flex flex-col gap-3 text-sm text-text">
                <ResumoLinha label="Ação do PT">
                  <span className="font-medium">{detalhe.acao.numero}</span>
                  <span className="ml-2 text-text-muted">
                    {detalhe.acao.descricao}
                  </span>
                </ResumoLinha>
                <ResumoLinha label="Âmbito">
                  {detalhe.ambito_display}
                </ResumoLinha>
                <ResumoLinha label="Forma de atuação">
                  {detalhe.forma_atuacao_display}
                </ResumoLinha>
                <ResumoLinha label="Participantes">
                  {detalhe.total_participantes} pessoas
                </ResumoLinha>
                {detalhe.descricao_narrativa && (
                  <div>
                    <p className="text-2xs uppercase tracking-wide text-text-muted">
                      Descrição
                    </p>
                    <p className="mt-1 line-clamp-4 whitespace-pre-wrap text-sm">
                      {detalhe.descricao_narrativa}
                    </p>
                  </div>
                )}
                {detalhe.status !== event.status && (
                  <p className="rounded-md bg-warning-bg px-2 py-1 text-xs text-warning-text">
                    Status na ficha: {statusLabel(detalhe.status)}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="text-xs text-text-muted">
            <Link
              href={linkFicha}
              className="inline-flex items-center gap-1 text-primary hover:underline"
            >
              Ver ficha completa
              <ExternalLink className="h-3 w-3" />
            </Link>
          </div>
        </div>
      ) : null}
    </SlideOver>
  );
}

function InfoItem({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-border bg-surface px-3 py-2">
      <span className="mt-0.5 text-text-muted">{icon}</span>
      <div className="min-w-0">
        <dt className="text-2xs uppercase tracking-wide text-text-muted">
          {label}
        </dt>
        <dd className="mt-0.5 truncate text-sm text-text">{value}</dd>
      </div>
    </div>
  );
}

function ResumoLinha({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-2xs uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-0.5">{children}</p>
    </div>
  );
}
