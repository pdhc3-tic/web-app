"use client";

import { Lock } from "lucide-react";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import {
  badgeStatusFor,
  statusLabel,
  type AtividadeDetail,
} from "@/app/lib/atividades";
import { formatDate } from "@/app/lib/datetime";

/**
 * Campo que a API ainda não entrega. Diz isso em vez de cair em "—", que
 * sugeriria "não preenchido" (docs/pendencias-backend-sprint-10.md, item 8).
 */
function NaoDisponivel() {
  return <span className="text-text-muted italic">Não disponível</span>;
}

/**
 * Contexto herdado da atividade — somente leitura (#294, SGD-RF02).
 *
 * A cadeia do Plano de Trabalho para em Ação → Meta: o SGP não modela Submeta
 * nem Indicador, então as duas linhas não existem aqui
 * (docs/pendencias-backend-sprint-10.md, item 7).
 */
export function ContextoAtividade({ atividade }: { atividade: AtividadeDetail }) {
  const meta = atividade.acao.meta;

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
          { label: "Município", value: atividade.municipio.nome },
          { label: "Comunidade", value: atividade.comunidade?.nome },
          { label: "Data prevista", value: formatDate(atividade.data_inicio) },
          { label: "Técnico", value: atividade.tecnico_responsavel.nome },
          {
            label: "Ação",
            value: `${atividade.acao.numero} — ${atividade.acao.descricao}`,
          },
          {
            label: "Meta",
            value: meta ? `Meta ${meta.numero} — ${meta.titulo}` : <NaoDisponivel />,
          },
        ]}
      />
    </section>
  );
}
