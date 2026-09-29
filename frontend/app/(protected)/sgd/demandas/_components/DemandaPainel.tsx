"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { Tabs } from "@/app/components/ui/Tabs/Tabs";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime, formatDate } from "@/app/lib/datetime";
import {
  badgeStatusDaDemanda,
  getDemanda,
  type Demanda,
} from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import { AcoesDecisao, type Desfecho } from "./AcoesDecisao";
import { NomeDoSolicitante } from "./NomeDoSolicitante";

function Solicitacoes({ demanda }: { demanda: Demanda }) {
  if (demanda.solicitacoes.length === 0) {
    return <p className="text-sm text-text-muted">Esta demanda ainda não tem solicitações de recurso.</p>;
  }
  return (
    <ul className="flex list-none flex-col gap-2" data-testid="painel-solicitacoes">
      {demanda.solicitacoes.map((s) => (
        <li key={s.id} className="rounded-md border border-border px-3 py-2.5 text-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-medium text-text">{s.tipo_display}</span>
            <span className="tabular-nums text-text">{formatCurrencyBRL(s.valor_estimado)}</span>
          </div>
          <p className="mt-0.5 text-xs text-text-muted">
            Rubrica: {s.rubrica_nome}
            {s.valor_autorizado !== null && ` · autorizado ${formatCurrencyBRL(s.valor_autorizado)}`}
            {s.valor_pago !== null && ` · pago ${formatCurrencyBRL(s.valor_pago)}`}
          </p>
          {s.alerta_rubrica_fora_do_previsto && (
            // RF22: alerta, não bloqueio — a decisão continua possível.
            <p
              className="mt-2 flex items-start gap-1.5 rounded border border-warning-text bg-warning-bg px-2 py-1.5 text-xs text-warning-text"
              data-testid={`alerta-rubrica-${s.id}`}
            >
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              A rubrica “{s.rubrica_nome}” não está entre as previstas na Ação desta atividade.
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

/**
 * Linha do tempo. A criação e o status atual vêm da própria demanda; as
 * decisões (quem, quando, com que justificativa) dependem de `etapas`, que o
 * backend ainda não envia (docs/pendencias-backend-sprint-10.md, item 11).
 */
function LinhaDoTempo({ demanda }: { demanda: Demanda }) {
  return (
    <ol className="flex list-none flex-col gap-3 border-l border-border pl-4" data-testid="painel-timeline">
      <li className="relative">
        <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full bg-border" aria-hidden />
        <p className="text-sm text-text">Demanda criada</p>
        <p className="text-xs text-text-muted">{absoluteDateTime(demanda.criado_em)}</p>
      </li>
      {demanda.etapas === undefined ? (
        <li className="relative text-sm italic text-text-muted" data-testid="timeline-indisponivel">
          <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full bg-border" aria-hidden />
          O histórico de decisões ainda não é enviado pela API.
        </li>
      ) : (
        demanda.etapas.map((e) => (
          <li key={e.id} className="relative">
            <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full bg-primary" aria-hidden />
            <p className="text-sm text-text">
              {e.etapa_display}: {e.acao_display}
              {e.responsavel_nome && <span className="text-text-muted"> · {e.responsavel_nome}</span>}
            </p>
            <p className="text-xs text-text-muted">{absoluteDateTime(e.criado_em)}</p>
            {e.justificativa && (
              <p className="mt-1 whitespace-pre-wrap text-xs text-text">{e.justificativa}</p>
            )}
          </li>
        ))
      )}
      <li className="relative">
        <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full bg-primary" aria-hidden />
        <p className="flex items-center gap-2 text-sm text-text">
          Status atual
          <Badge status={badgeStatusDaDemanda(demanda.status)} label={demanda.status_display} />
        </p>
      </li>
    </ol>
  );
}

/**
 * Painel de detalhe da demanda (#296, seção 11.2 do UX/UI): contexto,
 * solicitações, linha do tempo e as decisões do perfil logado no rodapé.
 */
export function DemandaPainel({
  demandaId,
  onFechar,
}: {
  demandaId: number;
  onFechar: () => void;
}) {
  const [aba, setAba] = useState("solicitacoes");
  const [desfecho, setDesfecho] = useState<Desfecho | null>(null);

  const { data: demanda, isPending, error, refetch } = useQuery({
    queryKey: qk.demandas.detalhe(demandaId),
    queryFn: ({ signal }) => getDemanda(demandaId, signal),
  });

  return (
    <aside
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5 lg:sticky lg:top-4"
      aria-label="Detalhe da demanda"
      data-testid="demanda-painel"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-text">
            {demanda?.titulo ?? "Demanda"}
          </h2>
          {demanda && (
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <Badge status={badgeStatusDaDemanda(demanda.status)} label={demanda.status_display} />
              {demanda.despesa_posterior && (
                <span className="text-xs text-warning-text">Despesa posterior à execução</span>
              )}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onFechar}
          aria-label="Fechar detalhe"
          className="rounded p-1 text-text-muted hover:text-text focus-visible:outline-2 focus-visible:outline-primary"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {desfecho && (
        // br-message: sucesso em verde, informativo em azul (seção 11.2).
        <p
          role="status"
          data-testid={`painel-mensagem-${desfecho.tipo}`}
          className={`flex items-start gap-2 rounded-md border px-3 py-2.5 text-sm ${
            desfecho.tipo === "sucesso"
              ? "border-success-text bg-success-bg text-success-text"
              : "border-info-text bg-info-bg text-info-text"
          }`}
        >
          {desfecho.tipo === "sucesso" ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          ) : (
            <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          )}
          {desfecho.texto}
        </p>
      )}

      {isPending ? (
        <p role="status" className="flex items-center gap-2 text-sm text-text-muted">
          <Spinner className="h-4 w-4 animate-spin" /> Carregando…
        </p>
      ) : error ? (
        <TabErroSection
          message={error instanceof ApiError ? error.message : "Não foi possível carregar a demanda."}
          onRetry={() => void refetch()}
        />
      ) : demanda ? (
        <>
          <DefinitionList
            items={[
              {
                label: "Atividade",
                value: (
                  <Link
                    href={`/sgp/atividades/${demanda.activity}?tab=demandas`}
                    className="text-primary hover:underline"
                  >
                    Abrir ficha da atividade
                  </Link>
                ),
              },
              { label: "Solicitante", value: <NomeDoSolicitante demanda={demanda} /> },
              { label: "Território", value: demanda.contexto.territorio_nome },
              { label: "Município", value: demanda.contexto.municipio_nome },
              {
                label: "Plano de Trabalho",
                value: `Meta ${demanda.contexto.meta_numero} · Ação ${demanda.contexto.acao_numero}`,
              },
              { label: "Data prevista", value: formatDate(demanda.contexto.data_prevista) },
              { label: "Valor estimado", value: formatCurrencyBRL(demanda.valor_estimado_total) },
              { label: "Justificativa", value: demanda.justificativa || undefined },
            ]}
          />

          <Tabs
            value={aba}
            onValueChange={setAba}
            aria-label="Seções da demanda"
            items={[
              {
                id: "solicitacoes",
                label: `Solicitações (${demanda.solicitacoes.length})`,
                content: <Solicitacoes demanda={demanda} />,
              },
              { id: "timeline", label: "Linha do tempo", content: <LinhaDoTempo demanda={demanda} /> },
            ]}
          />

          <AcoesDecisao
            demanda={demanda}
            onDecidido={setDesfecho}
            onIniciar={() => setDesfecho(null)}
          />
        </>
      ) : null}
    </aside>
  );
}
