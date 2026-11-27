"use client";

import { useRotuloChoice } from "@/app/providers/SgpChoicesProvider";
import { Lock } from "lucide-react";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { cadeiaDaAtividade, itensDaCadeia } from "@/app/components/sgp/CadeiaPlanoTrabalho/CadeiaPlanoTrabalho";
import { badgeStatusFor } from "@/app/lib/atividades";
import { formatDate } from "@/app/lib/datetime";
import type { AtividadeElegivelDetalhe } from "@/app/lib/demandas";

/**
 * Território que a atividade não tem. Diz isso em vez de cair em "—", que
 * sugeriria "não preenchido".
 */
function NaoDisponivel() {
  return <span className="text-text-muted italic">Não disponível</span>;
}

/**
 * Contexto herdado da atividade — somente leitura (#294, SGD-RF02): território,
 * município, comunidade, data, técnico e a cadeia Ação → Submeta → Meta →
 * Indicador do Plano de Trabalho.
 *
 * Sem território, mostra "Não disponível". A cadeia usa o mesmo formato da
 * ficha da atividade e do painel da demanda (#446).
 */
export function ContextoAtividade({ atividade }: { atividade: AtividadeElegivelDetalhe }) {
  const statusLabel = useRotuloChoice("status_atividade");

  return (
    <section
      className="rounded-lg border border-border bg-surface-muted/40 p-5"
      data-testid="demanda-contexto"
      aria-labelledby="demanda-contexto-titulo"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2
          id="demanda-contexto-titulo"
          className="flex items-center gap-2 text-sm font-medium text-text"
        >
          <Lock className="h-3.5 w-3.5 text-text-muted" aria-hidden />
          Herdado da atividade
        </h2>
        <Badge
          status={badgeStatusFor(atividade.status)}
          label={atividade.status_display || statusLabel(atividade.status)}
        />
      </div>

      <DefinitionList
        items={[
          { label: "Atividade", value: atividade.titulo },
          {
            label: "Território",
            value: atividade.territorio?.nome ?? <NaoDisponivel />,
          },
          {
            label: "Município",
            // Com a UF: a atividade pode ser de outro estado (#361).
            value: atividade.municipio.estado?.sigla
              ? `${atividade.municipio.nome}/${atividade.municipio.estado.sigla}`
              : atividade.municipio.nome,
          },
          { label: "Comunidade", value: atividade.comunidade?.nome },
          { label: "Data prevista", value: formatDate(atividade.data_inicio) },
          { label: "Técnico", value: atividade.tecnico_responsavel.nome },
          ...itensDaCadeia(cadeiaDaAtividade(atividade.acao), "contexto-cadeia"),
        ]}
      />
    </section>
  );
}
