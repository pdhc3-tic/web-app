"use client";

import { Pencil } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { ProgressBar } from "@/app/components/ui/ProgressBar/ProgressBar";
import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { formatQtd, progressoLabel } from "@/app/lib/acoes";
import { formatDate } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import { formatPercentual } from "@/app/lib/semaforo";
import type { AcaoAvaliada } from "./tipos";

type Props = {
  item: AcaoAvaliada | null;
  onClose: () => void;
  /** Espelha o `IsSuperAdmin | IsUGP` do backend — só afeta a afordância. */
  canManage: boolean;
};

/**
 * Detalhe da Ação em painel lateral, somente leitura.
 *
 * A issue aceita "navega até a tela de edição (FE-7) OU exibe painel lateral de
 * detalhe" — aqui são os dois: o painel responde na hora e o botão de editar
 * leva à tela da Meta com a Ação já aberta no formulário. Editar dentro do
 * painel duplicaria o AcaoSlideOver, que é o dono desse formulário.
 */
export function AcaoDetalheSlideOver({ item, onClose, canManage }: Props) {
  const acao = item?.acao;
  const avaliacao = item?.avaliacao;
  // Tipo de unidade e valores não vêm na resposta do painel: saem do
  // cruzamento com /acoes/ e ficam de fora da lista quando ele falta.
  const detalhe = item?.detalhe ?? null;

  const hrefEdicao =
    item?.meta && acao ? `/sgp/metas/${item.meta.id}?acao=${acao.id}` : null;

  return (
    <SlideOver
      open={item !== null}
      onClose={onClose}
      title={acao ? `Ação ${acao.numero}` : "Ação"}
      badge={avaliacao ? <SemaforoBadge nivel={avaliacao.nivel} /> : undefined}
      footer={
        hrefEdicao && canManage ? (
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>
              Fechar
            </Button>
            <Button
              as="a"
              href={hrefEdicao}
              variant="primary"
              leftIcon={<Pencil className="h-4 w-4" />}
              data-testid="painel-acao-editar"
            >
              Editar na Meta
            </Button>
          </div>
        ) : undefined
      }
    >
      {acao && avaliacao && (
        <div
          className="flex flex-col gap-5 px-4 py-6"
          data-testid="painel-acao-detalhe"
        >
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-[0.08em] text-text-muted">
              {item.meta ? `Meta ${item.meta.numero}` : "Meta"}
            </span>
            <p className="text-sm leading-relaxed text-text">
              {acao.descricao}
            </p>
          </div>

          <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface-muted p-4">
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="tabular-nums text-text">
                {progressoLabel(acao)}
              </span>
              <span className="tabular-nums text-text-muted">
                {formatPercentual(avaliacao.realizado)} realizado
              </span>
            </div>
            <ProgressBar
              value={avaliacao.realizado}
              label={`Progresso da Ação ${acao.numero}`}
              valueText={
                detalhe
                  ? `${progressoLabel(acao)} — ${detalhe.tipo_unidade_display}`
                  : progressoLabel(acao)
              }
            />
            <p className="text-xs leading-relaxed text-text-muted">
              Esperado {formatPercentual(avaliacao.esperado)} pelo tempo já
              decorrido do período
              {avaliacao.periodoHerdado ? " da Meta" : ""}. O realizado conta
              Atividades de Campo concluídas vinculadas à Ação.
            </p>
          </div>

          <DefinitionList
            items={[
              {
                label: "Tipo / unidade",
                value: detalhe?.tipo_unidade_display ?? null,
              },
              {
                label: "Quantidade planejada",
                value: (
                  <span className="tabular-nums">
                    {formatQtd(acao.quantidade_planejada)}
                  </span>
                ),
              },
              {
                label: "Quantidade realizada",
                value: (
                  <span className="tabular-nums">
                    {formatQtd(acao.quantidade_realizada)}
                  </span>
                ),
              },
              {
                label: "Valor unitário",
                value: detalhe ? (
                  <span className="tabular-nums">
                    {formatCurrencyBRL(detalhe.valor_unitario)}
                  </span>
                ) : null,
              },
              {
                label: "Valor total",
                value: detalhe ? (
                  <span className="tabular-nums">
                    {formatCurrencyBRL(detalhe.valor_total)}
                  </span>
                ) : null,
              },
              {
                label: avaliacao.periodoHerdado ? "Período (da Meta)" : "Período",
                value:
                  avaliacao.periodo.data_inicio || avaliacao.periodo.data_fim
                    ? `${formatDate(avaliacao.periodo.data_inicio)} – ${formatDate(avaliacao.periodo.data_fim)}`
                    : null,
              },
            ]}
          />
        </div>
      )}
    </SlideOver>
  );
}
