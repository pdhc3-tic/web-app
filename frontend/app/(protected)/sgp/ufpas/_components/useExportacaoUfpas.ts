"use client";

import { useExportacao, type TarefaExportacao } from "@/app/lib/hooks/useExportacao";
import { iniciarExportacaoUfpas, type ExportUfpasParams } from "@/app/lib/ufpas";

export type TarefaExportacaoUfpas = TarefaExportacao<ExportUfpasParams>;

function avisoNaFila({ total_registros: total }: { total_registros: number | null }): string {
  return total
    ? `O conjunto filtrado tem ${total.toLocaleString("pt-BR")} registros. A exportação será gerada em segundo plano.`
    : "A exportação será gerada em segundo plano.";
}

/**
 * Exportação da listagem de UFPAs (#240). Quem decide entre o arquivo na hora e
 * a geração em segundo plano é o backend (`/ufpas/exportar/`, pelo limite que
 * ele configura); a partir do job, o fluxo é o genérico do `useExportacao`.
 */
export function useExportacaoUfpas() {
  return useExportacao<ExportUfpasParams>({
    chave: "sgp.ufpas.exportacao",
    iniciar: iniciarExportacaoUfpas,
    erroAoIniciar: "Não foi possível exportar as UFPAs.",
    avisoNaFila,
  });
}
