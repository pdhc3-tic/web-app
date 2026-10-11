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
  /** Choices do SGP — uma carga por sessão (#272). */
  choices: ["sgp", "choices"] as const,
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
  /** Detalhe de uma atividade — contexto herdado pela nova demanda (#294). */
  atividade: (id: string | number) => ["sgp", "atividade", String(id)] as const,
  /** Ações do Plano de Trabalho para selects (#294). */
  acoesPT: ["sgp", "acoes"] as const,
  /** Municípios de um território (#294). */
  municipiosDoTerritorio: (territorioId: string) =>
    ["core", "municipios", { territorio: territorioId }] as const,
  /** Territórios ativos para selects (#294). */
  territorios: ["core", "territorios"] as const,
  /** Painel de demandas do SGD (#296) — tudo sob "sgd/demandas" invalida junto. */
  demandas: {
    all: ["sgd", "demandas"] as const,
    lista: (status: readonly string[]) =>
      ["sgd", "demandas", "lista", { status: [...status] }] as const,
    detalhe: (id: string | number) => ["sgd", "demandas", "detalhe", String(id)] as const,
    contagemFila: ["sgd", "demandas", "fila", "contagem"] as const,
    preview: (id: number, solicitacaoId: number, valor: string) =>
      ["sgd", "demandas", "preview", { id, solicitacaoId, valor }] as const,
  },
  /** Demandas do SGD vinculadas a uma atividade (#294). */
  demandasDaAtividade: (atividadeId: string | number) =>
    ["sgd", "demandas", { atividade: String(atividadeId) }] as const,
  /** Busca de atividades elegíveis no formulário de nova demanda (#294). */
  atividadesElegiveis: (tecnicoId: string, busca: string) =>
    ["sgp", "atividades", "elegiveis", { tecnicoId, busca }] as const,
  /** Tarefa assíncrona de exportação da listagem de UPFs (#240). */
  exportacaoUpfs: (id: string) => ["upfs", "exportacao", id] as const,
  /** Integração Arlo (#298): histórico de operações e o acompanhamento de uma. */
  arlo: {
    all: ["sgd", "arlo"] as const,
    operacoes: ["sgd", "arlo", "operacoes"] as const,
    operacao: (id: number) => ["sgd", "arlo", "operacao", id] as const,
  },
} as const;
