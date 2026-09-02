"use client";

import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Wifi } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime, relativeTime } from "@/app/lib/datetime";
import {
  getSyncEvent,
  type SyncErroDetalhe,
  type SyncEventListItem,
  type TipoConexao,
} from "@/app/lib/sca";
import { SyncEventTipoBadge } from "./SyncEventTipoBadge";

type Props = {
  events: SyncEventListItem[];
  loading: boolean;
};

const CONEXAO_LABEL: Record<Exclude<TipoConexao, null>, string> = {
  wifi: "Wi-Fi",
  "5g": "5G",
  "4g": "4G",
  "3g": "3G",
  "2g": "2G",
  offline: "Offline",
};

/**
 * Tabela do log de sincronização (#157). Cada linha com erro fica em destaque
 * (paleta error do design system) e pode ser expandida para exibir
 * `erros_detalhes`, buscado por demanda no endpoint de detalhe — a lista já
 * traz `contagem_erros`, mas o array só chega no /sync-events/{id}/.
 */
export function SyncEventsTable({ events, loading }: Props) {
  return (
    <div className="relative overflow-hidden rounded-lg border border-border bg-surface">
      {loading && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-surface/60">
          <Spinner className="h-5 w-5 animate-spin text-text-muted" />
        </div>
      )}
      <div className="overflow-x-auto">
        {/* min-width acompanha a coluna "Fim": abaixo disso as datas quebravam
            em duas linhas. O wrapper `overflow-x-auto` mantém todos os campos
            alcançáveis por rolagem horizontal em telas menores. */}
        <table className="w-full min-w-280 border-collapse text-sm">
          <thead className="bg-surface-muted text-left text-2xs font-semibold uppercase tracking-wide text-text-muted">
            <tr>
              <th className="w-6 px-2 py-2.5" aria-label="Expandir" />
              <th className="px-4 py-2.5">Início</th>
              <th className="px-4 py-2.5">Fim</th>
              <th className="px-4 py-2.5">Duração</th>
              <th className="px-4 py-2.5">Tipo</th>
              <th className="px-4 py-2.5">Técnico</th>
              <th className="px-4 py-2.5">Dispositivo</th>
              <th className="px-4 py-2.5 text-right">Enviados</th>
              <th className="px-4 py-2.5 text-right">Recebidos</th>
              <th className="px-4 py-2.5 text-right">Erros</th>
              <th className="px-4 py-2.5">Conexão</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <LinhaEvento key={e.id} evento={e} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LinhaEvento({ evento }: { evento: SyncEventListItem }) {
  const [expanded, setExpanded] = useState(false);
  const [erros, setErros] = useState<SyncErroDetalhe[] | null>(null);
  const [loadingErros, setLoadingErros] = useState(false);
  const [erroFetch, setErroFetch] = useState<string | null>(null);

  const temErro = evento.has_erros;
  const podeExpandir = temErro;

  async function toggle() {
    if (!podeExpandir) return;
    const next = !expanded;
    setExpanded(next);
    if (next && erros === null && !loadingErros) {
      setLoadingErros(true);
      setErroFetch(null);
      try {
        const detail = await getSyncEvent(evento.id);
        setErros(detail.erros_detalhes);
      } catch (err) {
        setErroFetch(
          err instanceof ApiError
            ? err.message
            : "Não foi possível carregar os erros deste evento.",
        );
      } finally {
        setLoadingErros(false);
      }
    }
  }

  const inicio = evento.iniciado_em ?? evento.finalizado_em;
  // Data e hora absolutas nas duas colunas — o critério pede o término legível,
  // não só o tempo relativo; o "há N minutos" migrou para o tooltip. Evento em
  // andamento não tem `finalizado_em`: cai no travessão, sem data inventada.
  const fim = absoluteDateTime(evento.finalizado_em);
  const dur = duracao(evento.iniciado_em, evento.finalizado_em);
  const rowBase =
    "border-t border-border align-middle transition hover:bg-surface-muted/40";
  const rowErro = temErro
    ? "bg-error-bg/40 hover:bg-error-bg/60"
    : "";

  return (
    <>
      <tr
        className={`${rowBase} ${rowErro} ${podeExpandir ? "cursor-pointer" : ""}`}
        onClick={toggle}
        onKeyDown={(e) => {
          if (!podeExpandir) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
          }
        }}
        tabIndex={podeExpandir ? 0 : -1}
        role={podeExpandir ? "button" : undefined}
        aria-expanded={podeExpandir ? expanded : undefined}
        aria-controls={podeExpandir ? `erros-${evento.id}` : undefined}
        data-testid={`sync-event-row-${evento.id}`}
        data-has-erros={temErro ? "true" : "false"}
      >
        <td className="px-2 py-3 text-text-muted">
          {podeExpandir ? (
            expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )
          ) : null}
        </td>
        <td className="px-4 py-3 whitespace-nowrap" data-testid="sync-event-inicio">
          <span title={relativeTime(inicio)}>
            {absoluteDateTime(inicio) ?? "—"}
          </span>
        </td>
        <td
          className="px-4 py-3 whitespace-nowrap"
          data-testid="sync-event-fim"
        >
          {fim ? (
            <span title={relativeTime(evento.finalizado_em)}>{fim}</span>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </td>
        <td className="px-4 py-3 text-text-muted">{dur}</td>
        <td className="px-4 py-3">
          <SyncEventTipoBadge tipo={evento.tipo} />
        </td>
        <td className="px-4 py-3" data-testid="sync-event-tecnico">
          <span className="block truncate text-text">{evento.tecnico.nome}</span>
          <span className="block truncate text-2xs text-text-muted">
            {evento.tecnico.email}
          </span>
        </td>
        <td className="px-4 py-3">
          {evento.dispositivo ? (
            <span className="block truncate">
              {evento.dispositivo.nome || evento.dispositivo.device_id}
            </span>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </td>
        <td className="px-4 py-3 text-right font-mono tabular-nums">
          {evento.contagem_enviados}
        </td>
        <td className="px-4 py-3 text-right font-mono tabular-nums">
          {evento.contagem_recebidos}
        </td>
        <td className="px-4 py-3 text-right font-mono tabular-nums">
          {temErro ? (
            <span className="inline-flex items-center gap-1 text-error-text">
              <AlertTriangle className="h-3.5 w-3.5" />
              {evento.contagem_erros}
            </span>
          ) : (
            <span className="text-text-muted">0</span>
          )}
        </td>
        <td className="px-4 py-3 text-text-muted">
          <span className="inline-flex items-center gap-1">
            <Wifi className="h-3.5 w-3.5" />
            {evento.tipo_conexao
              ? CONEXAO_LABEL[evento.tipo_conexao]
              : "—"}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr
          id={`erros-${evento.id}`}
          className="border-t border-border bg-error-bg/20"
          data-testid={`sync-event-erros-${evento.id}`}
        >
          <td className="px-2 py-3" />
          <td className="px-4 py-3" colSpan={10}>
            {loadingErros ? (
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <Spinner className="h-4 w-4 animate-spin" />
                Carregando detalhes dos erros…
              </div>
            ) : erroFetch ? (
              <p className="text-sm text-error-text">{erroFetch}</p>
            ) : erros && erros.length > 0 ? (
              <ul className="flex flex-col gap-2">
                {erros.map((e, idx) => (
                  <li
                    key={`${e.uuid_local}-${idx}`}
                    className="rounded-md border border-error-text/30 bg-surface px-3 py-2"
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded bg-error-bg px-1.5 py-0.5 font-mono font-medium text-error-text">
                        {e.codigo}
                      </span>
                      <span className="text-text-muted">
                        entidade: <span className="text-text">{e.entidade}</span>
                      </span>
                      <span className="text-text-muted">
                        uuid_local: <span className="font-mono text-text">{e.uuid_local}</span>
                      </span>
                    </div>
                    {e.mensagem && (
                      <p className="mt-1 text-sm text-text">{e.mensagem}</p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-text-muted">
                Este evento não tem detalhes de erro registrados.
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

/**
 * Duração legível ("2min 34s") entre início e fim; devolve "—" quando não
 * dá pra calcular (evento sem iniciado_em, ou datas inválidas).
 */
function duracao(inicio: string | null, fim: string | null): string {
  if (!inicio || !fim) return "—";
  const a = Date.parse(inicio);
  const b = Date.parse(fim);
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return "—";
  const s = Math.round((b - a) / 1000);
  if (s < 60) return `${s}s`;
  const min = Math.floor(s / 60);
  const rest = s % 60;
  return rest > 0 ? `${min}min ${rest}s` : `${min}min`;
}
