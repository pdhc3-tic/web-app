"use client";

import { ExportacaoStatus } from "@/app/components/sgp/Exportacao/ExportacaoStatus";
import type { TarefaExportacaoUpfs } from "./useExportacaoUpfs";

function descreverTotal(total: number | null): string {
  if (!total) return "das UPFs filtradas";
  return `de ${total.toLocaleString("pt-BR")} UPF${total === 1 ? "" : "s"}`;
}

/** Faixa de acompanhamento da exportação de UPFs em segundo plano (#240). */
export function ExportacaoUpfsStatus(
  props: Omit<Parameters<typeof ExportacaoStatus>[0], "tarefa" | "objeto" | "prefixo"> & {
    tarefa: TarefaExportacaoUpfs;
  },
) {
  return (
    <ExportacaoStatus
      {...props}
      objeto={descreverTotal(props.tarefa.exportacao.total_registros)}
      prefixo="upfs"
    />
  );
}
