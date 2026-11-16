"use client";

import { ExportacaoStatus } from "@/app/components/sgp/Exportacao/ExportacaoStatus";
import type { TarefaExportacaoUfpas } from "./useExportacaoUfpas";

function descreverTotal(total: number | null): string {
  if (!total) return "das UFPAs filtradas";
  return `de ${total.toLocaleString("pt-BR")} UFPA${total === 1 ? "" : "s"}`;
}

/** Faixa de acompanhamento da exportação de UFPAs em segundo plano (#240). */
export function ExportacaoUfpasStatus(
  props: Omit<Parameters<typeof ExportacaoStatus>[0], "tarefa" | "objeto" | "prefixo"> & {
    tarefa: TarefaExportacaoUfpas;
  },
) {
  return (
    <ExportacaoStatus
      {...props}
      objeto={descreverTotal(props.tarefa.exportacao.total_registros)}
      prefixo="ufpas"
    />
  );
}
