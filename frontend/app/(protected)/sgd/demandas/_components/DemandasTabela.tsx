"use client";

import { Badge } from "@/app/components/ui/Badge/Badge";
import { formatDate } from "@/app/lib/datetime";
import { badgeStatusDaDemanda, type Demanda } from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { NomeDoSolicitante } from "./NomeDoSolicitante";

type DemandasTabelaProps = {
  demandas: Demanda[];
  selecionada: number | null;
  /** Painel aberto: só as colunas mantidas (tabela 6.3 do UX/UI). */
  compacta: boolean;
  onSelecionar: (id: number) => void;
};

const TH = "px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-[0.06em] text-text-muted";
const TD = "px-4 py-3 align-middle";

/**
 * Lista master das demandas. Com o painel aberto, Território, Meta PT, Data de
 * criação e Valor estimado saem de cena; Título, Status e Solicitante ficam.
 */
export function DemandasTabela({
  demandas,
  selecionada,
  compacta,
  onSelecionar,
}: DemandasTabelaProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full text-sm" data-testid="demandas-tabela">
        <thead className="border-b border-border bg-surface-muted/50">
          <tr>
            <th className={TH}>Título</th>
            <th className={TH}>Status</th>
            <th className={TH}>Solicitante</th>
            {!compacta && (
              <>
                <th className={TH}>Território</th>
                <th className={TH}>Meta PT</th>
                <th className={TH}>Criada em</th>
                <th className={`${TH} text-right`}>Valor estimado</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {demandas.map((d) => {
            const ativa = d.id === selecionada;
            return (
              <tr
                key={d.id}
                data-testid={`demanda-linha-${d.id}`}
                aria-selected={ativa}
                className={`cursor-pointer border-b border-border last:border-b-0 transition-colors ${
                  ativa ? "bg-primary/10" : "hover:bg-surface-muted/60"
                }`}
                onClick={() => onSelecionar(d.id)}
              >
                <td className={TD}>
                  {/* O botão dá foco e Enter à linha; o clique na linha inteira é atalho. */}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelecionar(d.id);
                    }}
                    className="text-left font-medium text-text hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  >
                    {d.titulo}
                  </button>
                </td>
                <td className={TD}>
                  <Badge status={badgeStatusDaDemanda(d.status)} label={d.status_display} />
                </td>
                <td className={`${TD} text-text-muted`}>
                  <NomeDoSolicitante demanda={d} />
                </td>
                {!compacta && (
                  <>
                    <td className={`${TD} text-text-muted`}>
                      {d.contexto.territorio_nome ?? "—"}
                    </td>
                    <td className={`${TD} text-text-muted`} title={d.contexto.meta_titulo}>
                      Meta {d.contexto.meta_numero}
                    </td>
                    <td className={`${TD} tabular-nums text-text-muted`}>
                      {formatDate(d.criado_em)}
                    </td>
                    <td className={`${TD} text-right tabular-nums text-text`}>
                      {formatCurrencyBRL(d.valor_estimado_total)}
                    </td>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
