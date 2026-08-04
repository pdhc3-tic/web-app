import type { CatalogoItem, Producao, ProducaoWritePayload } from "./producaoTypes";

export const CULTURAS_MOCK: CatalogoItem[] = [
  { id: 1, nome: "Milho", categoria: "Grãos" },
  { id: 2, nome: "Feijão-caupi", categoria: "Leguminosas" },
  { id: 3, nome: "Mandioca", categoria: "Raízes" },
  { id: 4, nome: "Melancia", categoria: "Frutas" },
  { id: 5, nome: "Alface", categoria: "Hortaliças" },
  { id: 6, nome: "Coentro", categoria: "Hortaliças" },
  { id: 7, nome: "Amendoim", categoria: "Oleaginosas" },
  { id: 8, nome: "Capim-elefante", categoria: "Forrageiras" },
  { id: 9, nome: "Erva-doce", categoria: "Medicinais" },
];

export const ESPECIES_MOCK: CatalogoItem[] = [
  { id: 1, nome: "Bovino de corte", categoria: "Bovino" },
  { id: 2, nome: "Ovino Santa Inês", categoria: "Ovino" },
  { id: 3, nome: "Caprino leiteiro", categoria: "Caprino" },
  { id: 4, nome: "Galinha caipira", categoria: "Aves" },
  { id: 5, nome: "Suíno", categoria: "Suíno" },
  { id: 6, nome: "Tilápia", categoria: "Piscicultura" },
  { id: 7, nome: "Abelha jandaíra", categoria: "Apicultura" },
];

const STORE = new Map<string, Producao[]>();
let NEXT_ID = 1000;

function seedFor(): Producao[] {
  return [
    make("agricola", {
      cultura: CULTURAS_MOCK[0],
      area_ha: "5",
      producao_estimada: "80",
      unidade_producao: "sacas",
      sementes_crioulas: true,
      custo_anual: "1200.00",
      observacoes: "Plantio em consórcio com feijão.",
    }),
    make("pecuaria", {
      especie: ESPECIES_MOCK[1],
      n_matrizes: 20,
      n_reprodutores: 2,
      n_jovens: 10,
      area_pastejo_ha: "3",
      sistema_criacao: "semi_intensivo",
    }),
    make("outra", {
      tipo_outra: "beneficiamento",
      descricao_outra: "Polpa de fruta congelada.",
      quantidade_produzida: "60 unid/mês",
      renda_estimada_mensal: "480.00",
      custo_anual: "800.00",
    }),
  ];
}

function make(tipo: Producao["tipo"], overrides: Partial<Producao>): Producao {
  return {
    id: NEXT_ID++,
    tipo,
    cultura: null,
    area_ha: null,
    producao_estimada: null,
    unidade_producao: null,
    sementes_crioulas: false,
    especie: null,
    n_matrizes: null,
    n_reprodutores: null,
    n_jovens: null,
    area_pastejo_ha: null,
    sistema_criacao: null,
    tipo_outra: null,
    descricao_outra: null,
    quantidade_produzida: null,
    renda_estimada_mensal: null,
    custo_anual: null,
    observacoes: null,
    ...overrides,
  };
}

function ensure(upfId: string): Producao[] {
  const key = String(upfId);
  if (!STORE.has(key)) STORE.set(key, seedFor());
  return STORE.get(key)!;
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function listProducoesMock(upfId: string, signal?: AbortSignal) {
  await delay(350);
  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
  return [...ensure(upfId)];
}

export async function createProducaoMock(
  upfId: string,
  payload: ProducaoWritePayload,
): Promise<Producao> {
  await delay(300);
  const list = ensure(upfId);
  const saved = make(payload.tipo, payloadToPartial(payload));
  list.unshift(saved);
  return saved;
}

export async function updateProducaoMock(
  upfId: string,
  id: number,
  payload: ProducaoWritePayload,
): Promise<Producao> {
  await delay(300);
  const list = ensure(upfId);
  const idx = list.findIndex((p) => p.id === id);
  if (idx === -1) throw new Error("Registro não encontrado.");
  const updated: Producao = { ...make(payload.tipo, payloadToPartial(payload)), id };
  list[idx] = updated;
  return updated;
}

export async function deleteProducaoMock(upfId: string, id: number): Promise<void> {
  await delay(300);
  const list = ensure(upfId);
  const idx = list.findIndex((p) => p.id === id);
  if (idx === -1) throw new Error("Registro não encontrado.");
  list.splice(idx, 1);
}

export async function searchCulturasMock(q: string, signal?: AbortSignal) {
  await delay(200);
  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
  return filterCatalogo(CULTURAS_MOCK, q);
}

export async function searchEspeciesMock(q: string, signal?: AbortSignal) {
  await delay(200);
  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
  return filterCatalogo(ESPECIES_MOCK, q);
}

function filterCatalogo(list: CatalogoItem[], q: string): CatalogoItem[] {
  const term = q.trim().toLowerCase();
  if (!term) return list;
  return list.filter(
    (c) => c.nome.toLowerCase().includes(term) || c.categoria.toLowerCase().includes(term),
  );
}

function payloadToPartial(payload: ProducaoWritePayload): Partial<Producao> {
  const cultura =
    payload.cultura_id != null
      ? CULTURAS_MOCK.find((c) => c.id === payload.cultura_id) ?? null
      : null;
  const especie =
    payload.especie_id != null
      ? ESPECIES_MOCK.find((e) => e.id === payload.especie_id) ?? null
      : null;
  return {
    cultura,
    especie,
    area_ha: payload.area_ha ?? null,
    producao_estimada: payload.producao_estimada ?? null,
    unidade_producao: payload.unidade_producao ?? null,
    sementes_crioulas: payload.sementes_crioulas ?? false,
    n_matrizes: payload.n_matrizes ?? null,
    n_reprodutores: payload.n_reprodutores ?? null,
    n_jovens: payload.n_jovens ?? null,
    area_pastejo_ha: payload.area_pastejo_ha ?? null,
    sistema_criacao: payload.sistema_criacao ?? null,
    tipo_outra: payload.tipo_outra ?? null,
    descricao_outra: payload.descricao_outra ?? null,
    quantidade_produzida: payload.quantidade_produzida ?? null,
    renda_estimada_mensal: payload.renda_estimada_mensal ?? null,
    custo_anual: payload.custo_anual ?? null,
    observacoes: payload.observacoes ?? null,
  };
}
