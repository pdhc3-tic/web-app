"use client";

import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";
import { ProgressBar } from "@/app/components/ui/ProgressBar/ProgressBar";
import { formatDate } from "@/app/lib/datetime";
import {
  NIVEIS_SEMAFORO,
  contarNiveis,
  nivelLabel,
  type NivelSemaforo,
} from "@/app/lib/semaforo";
import { AcaoLinha } from "./AcaoLinha";
import type { AcaoAvaliada, MetaComAcoes } from "./tipos";

type Props = {
  item: MetaComAcoes;
  onSelect: (item: AcaoAvaliada) => void;
  /** Cards já nascem abertos quando o filtro reduziu a uma única Meta. */
  defaultExpandido?: boolean;
};

const contagemClass: Record<NivelSemaforo, string> = {
  verde: "bg-success-bg text-success-text",
  amarelo: "bg-warning-bg text-warning-text",
  vermelho: "bg-error-bg text-error-text",
  "sem-dado": "bg-neutral-bg text-neutral-text",
};

/** Pastilha de contagem — o resumo que se lê sem expandir o card. */
function Contagem({ nivel, total }: { nivel: NivelSemaforo; total: number }) {
  return (
    <span
      data-testid={`contagem-${nivel}`}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium tabular-nums ${contagemClass[nivel]}`}
    >
      <span aria-hidden className="text-sm leading-none">
        {total}
      </span>
      <span className="sr-only">{total} </span>
      {nivelLabel(nivel)}
    </span>
  );
}

/**
 * Card-resumo de uma Meta: contagens do semáforo sempre visíveis e as Ações
 * individuais atrás de um toggle.
 *
 * A expansão é estado local do card, não da página: com 7 Metas o gestor abre
 * uma, olha e fecha, e centralizar isso no pai só criaria prop drilling.
 */
export function MetaResumoCard({
  item,
  onSelect,
  defaultExpandido = false,
}: Props) {
  const [expandido, setExpandido] = useState(defaultExpandido);
  const painelId = useId();
  const { meta, acoes } = item;

  // A resposta do painel traz um `resumo` pronto, mas ele não conhece o nível
  // "sem-dado": Ações sem quantidade planejada entram lá como vermelhas. Contar
  // sobre os níveis já exibidos mantém a pastilha e a lista logo abaixo dizendo
  // a mesma coisa — que é o ponto de um card-resumo.
  const contagens = contarNiveis(acoes.map((a) => a.avaliacao));
  const semDado = contagens["sem-dado"];
  const periodo =
    meta.data_inicio || meta.data_fim
      ? `${formatDate(meta.data_inicio)} – ${formatDate(meta.data_fim)}`
      : null;

  // Progresso da Meta = média simples do realizado das Ações que têm
  // denominador. Não é ponderada por valor nem por quantidade de propósito:
  // as unidades das Ações são incomparáveis entre si (oficinas × famílias),
  // e somá-las produziria um total sem significado.
  const comPercentual = acoes
    .map((a) => a.avaliacao.realizado)
    .filter((p): p is number => p !== null);
  const mediaRealizado =
    comPercentual.length > 0
      ? comPercentual.reduce((s, p) => s + p, 0) / comPercentual.length
      : null;

  return (
    <div
      className="flex flex-col rounded-lg border border-border bg-surface"
      data-testid={`painel-meta-${meta.id}`}
    >
      <div className="flex flex-col gap-3 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-0.5">
            <span className="text-xs uppercase tracking-[0.08em] text-text-muted">
              Meta {meta.numero}
            </span>
            <h3 className="text-sm font-semibold leading-snug text-text">
              {meta.titulo}
            </h3>
            {periodo && (
              <span className="text-xs text-text-muted">{periodo}</span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            {NIVEIS_SEMAFORO.map((nivel) => (
              <Contagem key={nivel} nivel={nivel} total={contagens[nivel]} />
            ))}
            {semDado > 0 && <Contagem nivel="sem-dado" total={semDado} />}
          </div>
        </div>

        <ProgressBar
          value={mediaRealizado}
          label={`Progresso médio da Meta ${meta.numero}`}
          valueText={`${acoes.length} ${acoes.length === 1 ? "Ação" : "Ações"}`}
        />
      </div>

      <button
        type="button"
        aria-expanded={expandido}
        aria-controls={painelId}
        onClick={() => setExpandido((v) => !v)}
        data-testid={`painel-meta-toggle-${meta.id}`}
        className="flex items-center justify-between gap-2 border-t border-border px-4 py-2.5 text-xs font-medium text-text-muted transition-colors hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
      >
        <span>
          {expandido ? "Ocultar" : "Ver"} {acoes.length}{" "}
          {acoes.length === 1 ? "Ação" : "Ações"}
        </span>
        <ChevronDown
          aria-hidden
          className={`h-4 w-4 transition-transform duration-150 motion-reduce:transition-none ${
            expandido ? "rotate-180" : ""
          }`}
        />
      </button>

      {expandido && (
        <ul id={painelId} className="flex flex-col gap-2 px-4 pb-4">
          {acoes.map((a) => (
            <li key={a.acao.id}>
              <AcaoLinha item={a} onSelect={onSelect} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
