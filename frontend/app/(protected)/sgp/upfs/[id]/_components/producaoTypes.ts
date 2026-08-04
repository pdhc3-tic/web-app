export const TIPO_OPTIONS = [
  { value: "agricola", label: "Agrícola" },
  { value: "pecuaria", label: "Pecuária" },
  { value: "outra", label: "Outra" },
] as const;

export type TipoProducao = (typeof TIPO_OPTIONS)[number]["value"];

export const SISTEMA_CRIACAO_OPTIONS = [
  { value: "extensivo", label: "Extensivo" },
  { value: "semi_intensivo", label: "Semi-intensivo" },
  { value: "intensivo", label: "Intensivo" },
] as const;

export type SistemaCriacao = (typeof SISTEMA_CRIACAO_OPTIONS)[number]["value"];

export const TIPO_OUTRA_OPTIONS = [
  { value: "artesanato", label: "Artesanato" },
  { value: "beneficiamento", label: "Beneficiamento" },
  { value: "extrativismo", label: "Extrativismo" },
  { value: "outro", label: "Outro" },
] as const;

export type TipoOutra = (typeof TIPO_OUTRA_OPTIONS)[number]["value"];

export type CatalogoItem = {
  id: number;
  nome: string;
  categoria: string;
};

export type Producao = {
  id: number;
  tipo: TipoProducao;

  cultura: CatalogoItem | null;
  area_ha: string | null;
  producao_estimada: string | null;
  unidade_producao: string | null;
  sementes_crioulas: boolean;

  especie: CatalogoItem | null;
  n_matrizes: number | null;
  n_reprodutores: number | null;
  n_jovens: number | null;
  area_pastejo_ha: string | null;
  sistema_criacao: SistemaCriacao | null;

  tipo_outra: TipoOutra | null;
  descricao_outra: string | null;
  quantidade_produzida: string | null;
  renda_estimada_mensal: string | null;

  custo_anual: string | null;
  observacoes: string | null;
};

export type ProducaoWritePayload = {
  tipo: TipoProducao;

  cultura_id?: number | null;
  area_ha?: string | null;
  producao_estimada?: string | null;
  unidade_producao?: string | null;
  sementes_crioulas?: boolean;

  especie_id?: number | null;
  n_matrizes?: number | null;
  n_reprodutores?: number | null;
  n_jovens?: number | null;
  area_pastejo_ha?: string | null;
  sistema_criacao?: SistemaCriacao | null;

  tipo_outra?: TipoOutra | null;
  descricao_outra?: string | null;
  quantidade_produzida?: string | null;
  renda_estimada_mensal?: string | null;

  custo_anual?: string | null;
  observacoes?: string | null;
};
