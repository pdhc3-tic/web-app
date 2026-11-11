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
  /** Pools de uma rubrica num nível, da matriz Rubrica × Nível (#384): origem do excedente e do recurso extra. */
  poolsDaRubrica: (rubrica: string, nivel: string) => ["sgp", "orcamento", "pools", { rubrica, nivel }] as const,
  /** Movimentações do ledger de um pool, no detalhe do Painel de Orçamento (#398). */
  orcamentoPool: {
    transacoes: (poolId: number) => ["sgp", "orcamento", "pools", poolId, "transacoes"] as const,
  },
  /** Limites de gasto (#400): padrão por perfil e sobrescritas, vigentes numa data. */
  limites: {
    todos: ["sgp", "orcamento", "limites"] as const,
    lista: (escopo: string, data: string) => ["sgp", "orcamento", "limites", escopo, data] as const,
    periodicidade: ["core", "system-config", "budget_limit_period"] as const,
    perfisOperacionais: ["core", "roles", "operacionais"] as const,
  },
  /** "Meu saldo" (#401): os cards por rubrica e o extrato de cada uma. */
  meuSaldo: {
    cards: ["sgp", "orcamento", "meu-saldo", "cards"] as const,
    extrato: (rubrica: string, offset: number, limit: number, historico: boolean) =>
      ["sgp", "orcamento", "meu-saldo", "extrato", rubrica, { offset, limit, historico }] as const,
    demandasParaRecurso: (rubrica: string) =>
      ["sgp", "orcamento", "meu-saldo", "demandas-editaveis", rubrica] as const,
  },
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
    /** `pagina` (offset/limit) só no painel de demandas, que pagina a lista (#323). */
    lista: (
      status: readonly string[],
      pagina?: { offset: number; limit: number },
      ordenacao?: string,
    ) =>
      ["sgd", "demandas", "lista", { status: [...status], ...pagina, ordenacao: ordenacao ?? null }] as const,
    detalhe: (id: string | number) => ["sgd", "demandas", "detalhe", String(id)] as const,
    /** Prefixo da fila: invalida todas as páginas de uma vez. */
    fila: ["sgd", "demandas", "fila", "lista"] as const,
    filaPagina: (pagina: { offset: number; limit: number }, ordenacao?: string) =>
      ["sgd", "demandas", "fila", "lista", pagina, ordenacao ?? null] as const,
    contagemFila: ["sgd", "demandas", "fila", "contagem"] as const,
    /** Lista com o recorte vindo do drill-down do painel de execução (#297). */
    recorte: (
      filtros: Record<string, string | undefined>,
      pagina?: { offset: number; limit: number },
      ordenacao?: string,
    ) =>
      ["sgd", "demandas", "recorte", filtros, pagina ?? null, ordenacao ?? null] as const,
    preview: (id: number, solicitacaoId: number, valor: string, origem: string) =>
      ["sgd", "demandas", "preview", { id, solicitacaoId, valor, origem }] as const,
    /** Riscos de glosa da demanda (#360); sob "sgd/demandas", a decisão os invalida junto. */
    glosas: (id: string | number) => ["sgd", "demandas", "glosas", String(id)] as const,
    /** Riscos de glosa de uma atividade, para a ficha (#404). */
    glosasDaAtividade: (atividadeId: string | number) =>
      ["sgd", "demandas", "glosas", "atividade", String(atividadeId)] as const,
    auditoria: (id: string | number) =>
      ["sgd", "demandas", "auditoria", String(id)] as const,
    /** Documentos da demanda (#295). */
    documentos: (id: number) => ["sgd", "demandas", "documentos", String(id)] as const,
    /** Painel consolidado da home do SGD (#318): as decisões o invalidam junto. */
    dashboard: ["sgd", "demandas", "dashboard"] as const,
  },
  /** Configuração do SGD: o catálogo de tipos de solicitação (#365) e o de rubricas. */
  configSgd: {
    /** Todos os tipos, ativos e inativos; quem precisa só dos ativos filtra. */
    tiposSolicitacao: ["sgd", "config", "tipos-solicitacao"] as const,
    rubricas: ["sgp", "rubricas"] as const,
  },
  /** Montagem da demanda (#295): saldo, simulação de diárias e destinos. */
  solicitacao: {
    saldo: (tipo: string, valor: string) => ["sgd", "saldo", { tipo, valor }] as const,
    simulacaoDiarias: (municipioId: string, inicio: string, fim: string) =>
      ["sgd", "diarias", "simulacao", { municipioId, inicio, fim }] as const,
    municipios: (texto: string) => ["core", "municipios", "busca", texto] as const,
    municipio: (id: string) => ["core", "municipios", "detalhe", id] as const,
  },
  /** Recurso extra e Fila de Remanejamentos do SGD (#321). */
  remanejamentos: {
    all: ["sgd", "remanejamentos"] as const,
    lista: (status: readonly string[]) =>
      ["sgd", "remanejamentos", "lista", { status: [...status] }] as const,
    excedentes: ["sgd", "remanejamentos", "excedentes"] as const,
    detalhe: (id: string | number) => ["sgd", "remanejamentos", "detalhe", String(id)] as const,
    daDemanda: (demandaId: number) =>
      ["sgd", "remanejamentos", "demanda", String(demandaId)] as const,
  },
  /** Demandas do SGD vinculadas a uma atividade (#294). */
  demandasDaAtividade: (atividadeId: string | number) =>
    ["sgd", "demandas", { atividade: String(atividadeId) }] as const,
  /** Busca de atividades elegíveis no formulário de nova demanda (#294). */
  atividadesElegiveis: (busca: string) =>
    ["sgp", "atividades", "elegiveis", { busca }] as const,
  /** Tarefa assíncrona de exportação da listagem de UPFs (#240). */
  /** Job de exportação assíncrona do SGP (`/sgp/exportacoes/{id}/`), qualquer tipo. */
  exportacao: (id: string) => ["sgp", "exportacao", id] as const,
  /** Execução por rubrica e custo por atividade (#297) e as opções dos filtros. */
  execucao: {
    painel: (filtros: Record<string, string | undefined>) =>
      ["sgd", "execucao", "painel", filtros] as const,
    custo: (filtros: Record<string, string | undefined>) =>
      ["sgd", "execucao", "custo", filtros] as const,
    metas: ["sgp", "metas", "opcoes"] as const,
    submetas: ["sgp", "submetas", "opcoes"] as const,
    opcoesUsuarios: (papel: string) => ["sgd", "opcoes", "usuarios", papel] as const,
    buscaAtividade: (texto: string) => ["sgp", "atividades", "filtro", { texto }] as const,
  },
  /** Integração Arlo (#298): histórico de operações e o acompanhamento de uma. */
  arlo: {
    all: ["sgd", "arlo"] as const,
    operacoes: ["sgd", "arlo", "operacoes"] as const,
    operacao: (id: number) => ["sgd", "arlo", "operacao", id] as const,
  },
  /** Busca de usuários elegíveis a técnico (A2 da #302, SGP). */
  usuariosElegiveisTecnico: (busca: string) =>
    ["sgp", "tecnicos", "usuarios-elegiveis", busca] as const,
  /** Mapeamento Arlo ↔ SGD, por direção (#320, SGD-FE-9). */
  arloMapping: {
    all: ["sgd", "arlo-mapping"] as const,
    lista: (direcao: "exportacao" | "importacao") =>
      ["sgd", "arlo-mapping", "lista", direcao] as const,
    campos: ["sgd", "arlo-mapping", "campos"] as const,
    preview: (direcao: "exportacao" | "importacao") =>
      ["sgd", "arlo-mapping", "preview", direcao] as const,
  },
  /** Alertas orçamentários abertos, por filtro (#403). */
  alertasOrcamento: (filtros: { tipo: string; faixa: string }, limite: number) =>
    ["sgp", "orcamento", "alertas", filtros, limite] as const,
  /** Parâmetros globais em `SystemConfig` (#403). */
  systemConfig: ["core", "system-config"] as const,
} as const;
