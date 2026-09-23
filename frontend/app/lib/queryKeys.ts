/**
 * Factory central das query keys do TanStack Query.
 *
 * Chaves montadas por escopo → recurso → sub-recurso: `invalidateQueries` com
 * um prefixo mais curto atinge todos os descendentes de uma vez. Ex.:
 * `queryClient.invalidateQueries({ queryKey: qk.upf(id).all })` invalida
 * membros, produção, documentos e histórico daquela UPF sem precisar listar.
 *
 * Sempre acessar via este arquivo: chaves cruas espalhadas pelo código levam
 * a strings divergentes entre o `useQuery` e o `invalidate`, e o bug só
 * aparece em runtime.
 */
export const qk = {
  upf: (id: string | number) => {
    const upfId = String(id);
    return {
      /** Todas as consultas dessa UPF — usar para invalidação em massa. */
      all: ["upf", upfId] as const,
      membros: ["upf", upfId, "membros"] as const,
      membrosResumo: ["upf", upfId, "membros", "resumo"] as const,
      producao: ["upf", upfId, "producao"] as const,
      documentos: ["upf", upfId, "documentos"] as const,
      historico: (page: number, pageSize: number) =>
        ["upf", upfId, "historico", { page, pageSize }] as const,
    };
  },
  /** Tarefa assíncrona de exportação da listagem de UPFs (#240). */
  exportacaoUpfs: (id: string) => ["upfs", "exportacao", id] as const,
} as const;
