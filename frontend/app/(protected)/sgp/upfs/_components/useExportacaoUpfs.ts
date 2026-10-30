"use client";

import { useExportacao, type TarefaExportacao } from "@/app/lib/hooks/useExportacao";
import { iniciarExportacaoUpfs, type ExportUpfsParams } from "@/app/lib/upfs";

export type TarefaExportacaoUpfs = TarefaExportacao<ExportUpfsParams>;

function avisoNaFila({ total_registros: total }: { total_registros: number | null }): string {
  return total
    ? `O conjunto filtrado tem ${total.toLocaleString("pt-BR")} registros. A exportação será gerada em segundo plano.`
    : "A exportação será gerada em segundo plano.";
}

/**
 * Exportação da listagem de UPFs (#240). Quem decide entre o arquivo na hora e
 * a geração em segundo plano é o backend (`/upfs/exportar/`, pelo limite que
 * ele configura); a partir do job, o fluxo é o genérico do `useExportacao`.
 */
export function useExportacaoUpfs() {
  return useExportacao<ExportUpfsParams>({
    chave: "sgp.upfs.exportacao",
    iniciar: iniciarExportacaoUpfs,
    erroAoIniciar: "Não foi possível exportar as UPFs.",
    avisoNaFila,
  });
}
