import { apiClient } from "@/app/lib/api";
import type { Paginated } from "@/app/lib/users";
import type { Territorio } from "@/app/lib/auth/types";
import type { SelectOption } from "@/app/components/ui/Select/Select";

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Espelha apps/sgp/serializers.py::UPFListSerializer. */
/**
 * Município como vem nas listagens de UPF (`MunicipioNestedSerializer`).
 *
 * Era `string` até 5b63bde (21/07), quando o backend trocou o
 * `CharField(source="municipio.nome")` pelo serializer aninhado. O tipo do
 * front seguiu dizendo `string`, e a listagem passou a renderizar o objeto
 * direto — "Objects are not valid as a React child" derrubava /sgp/upfs.
 * Não havia E2E cobrindo a listagem, então ninguém percebeu.
 */
export type MunicipioResumo = {
  id: number;
  nome: string;
  estado?: { id: number; sigla: string; nome: string };
};

export type UpfListItem = {
  id: number;
  nome_titular: string;
  /** Já vem mascarado do backend: "XXX.***.***-XX". */
  cpf: string;
  /**
   * Objeto, NÃO string — o `UPFListSerializer` usa `MunicipioNestedSerializer`
   * desde 5b63bde (21/07), que substituiu um `CharField(source="municipio.nome")`.
   * O tipo seguiu dizendo `string` e a listagem renderizava o objeto direto,
   * derrubando a página com "Objects are not valid as a React child".
   */
  municipio: MunicipioResumo;
  territorio: string | null;
  criado_em: string;
  ativo: boolean;
  /**
   * Opcional: UPFListSerializer ainda não expõe este campo (pendente no
   * backend). Quando ausente, o avatar da listagem cai para as iniciais.
   */
  foto_url?: string | null;
};

/** Filtro de status mapeado para o parâmetro `ativo` do backend. */
export type StatusUpfFilter = "ativas" | "inativas" | "todas";

export type ListUpfsParams = {
  limit: number;
  offset: number;
  search?: string;
  municipio?: string;
  territorio?: string;
  projeto?: string;
  status?: StatusUpfFilter;
  /** Datas no formato YYYY-MM-DD (input nativo). */
  cadastradoDe?: string;
  cadastradoAte?: string;
  ordering?: string;
};

/** Município para o select de filtro (subset dos campos do endpoint). */
type MunicipalityOption = {
  id: number;
  nome: string;
};

// ─── Helpers ────────────────────────────────────────────────────────────────

function buildUpfsQuery(params: ListUpfsParams): string {
  const qs = new URLSearchParams();
  qs.set("limit", String(params.limit));
  qs.set("offset", String(params.offset));

  if (params.search?.trim()) qs.set("q", params.search.trim());
  if (params.municipio) qs.set("municipio", params.municipio);
  if (params.territorio) qs.set("territorio", params.territorio);
  if (params.projeto) qs.set("projeto", params.projeto);
  if (params.ordering) qs.set("ordering", params.ordering);

  // Status → parâmetro `ativo`.
  // O UPFViewSet só retorna inativas quando `ativo` aparece na query
  // (default: ativo=True). "todas" passa string vazia para desligar o default.
  if (params.status === "ativas") qs.set("ativo", "true");
  else if (params.status === "inativas") qs.set("ativo", "false");
  else if (params.status === "todas") qs.set("ativo", "");

  // Range de "cadastrado em": o "YYYY-MM-DD" do input vai cru. Desde a #212 o
  // backend recorta o dia no TIME_ZONE do servidor — converter para ISO em UTC
  // aqui era justamente o que deslocava a janela em horas.
  if (params.cadastradoDe) qs.set("cadastrado_de", params.cadastradoDe);
  if (params.cadastradoAte) qs.set("cadastrado_ate", params.cadastradoAte);

  return qs.toString();
}

// ─── API ────────────────────────────────────────────────────────────────────

/** GET /api/v1/upfs/?page_size=1 — retorna apenas o total de UPFs no escopo do usuário. */
export async function fetchUpfCount(signal?: AbortSignal): Promise<number> {
  const res = await apiClient("/api/v1/upfs/?page_size=1", { signal });
  const data = (await res.json()) as { count: number };
  return data.count;
}

/** GET /api/v1/upfs/ — listagem paginada com filtros. */
export async function listUpfs(
  params: ListUpfsParams,
  signal?: AbortSignal,
): Promise<Paginated<UpfListItem>> {
  const res = await apiClient(`/api/v1/upfs/?${buildUpfsQuery(params)}`, {
    signal,
  });
  return res.json();
}

/** Opções de município para o filtro (GET /api/v1/municipalities/). */
export async function fetchMunicipalityOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/municipalities/?limit=1000", { signal });
  const data: Paginated<MunicipalityOption> = await res.json();
  return data.results.map((m) => ({
    value: String(m.id),
    label: m.nome,
  }));
}

/** Opções de território para o filtro (GET /api/v1/territories/). */
export async function fetchTerritoryOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/territories/?limit=500&ativo=true", {
    signal,
  });
  const data: Paginated<Territorio> = await res.json();
  return data.results.map((t) => ({
    value: String(t.id),
    label: t.nome,
  }));
}

// ─── Mapa de UPFs ─────────────────────────────────────────────────────────────

/**
 * UPF georreferenciada, achatada a partir do GeoJSON devolvido por
 * `GET /api/v1/upfs/mapa/` (apps/sgp/views::UPFViewSet.mapa). As properties da
 * feature trazem apenas o mínimo para desenhar e rotular o marcador — CPF e foto
 * não vêm aqui; a mini-ficha busca o detalhe da UPF sob demanda.
 */
export type UpfMapa = {
  id: number;
  nome_titular: string;
  municipio: MunicipioResumo;
  territorio: string | null;
  latitude: number;
  longitude: number;
  ativo: boolean;
};

export type UpfMapaResponse = {
  results: UpfMapa[];
  truncated: boolean;
  /** Aviso do backend quando o resultado estoura o limite de features. */
  message?: string;
};

export type UpfMapaFilters = {
  search?: string;
  /** Ids (não nomes) — mesmos valores dos selects de filtro. */
  municipio?: string;
  territorio?: string;
  projeto?: string;
  status?: StatusUpfFilter;
  /** bbox no formato lng_sw,lat_sw,lng_ne,lat_ne. */
  bbox?: string;
};

/** Feature GeoJSON como o backend a monta em `_build_mapa_feature`. */
type UpfMapaFeature = {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    id: number;
    nome_titular: string;
    municipio: MunicipioResumo;
    territorio: string | null;
    ativo: boolean;
  };
};

type UpfMapaFeatureCollection = {
  type: "FeatureCollection";
  features: UpfMapaFeature[];
  truncated: boolean;
  message?: string;
};

/** GET /api/v1/upfs/mapa/ — UPFs com coordenadas, em GeoJSON. */
export async function fetchUpfsMapa(
  filters: UpfMapaFilters,
  signal?: AbortSignal,
): Promise<UpfMapaResponse> {
  const qs = new URLSearchParams();
  if (filters.search?.trim()) qs.set("q", filters.search.trim());
  if (filters.municipio) qs.set("municipio", filters.municipio);
  if (filters.territorio) qs.set("territorio", filters.territorio);
  if (filters.projeto) qs.set("projeto", filters.projeto);
  if (filters.bbox) qs.set("bbox", filters.bbox);

  // Mesmo mapeamento status → `ativo` da listagem: o UPFViewSet.filter_queryset
  // aplica ativo=True por padrão, e "todas" desliga esse default.
  if (filters.status === "ativas") qs.set("ativo", "true");
  else if (filters.status === "inativas") qs.set("ativo", "false");
  else if (filters.status === "todas") qs.set("ativo", "");

  const query = qs.toString();
  const res = await apiClient(`/api/v1/upfs/mapa/${query ? `?${query}` : ""}`, {
    signal,
  });
  const data: UpfMapaFeatureCollection = await res.json();

  return {
    results: data.features.map((f) => ({
      ...f.properties,
      // GeoJSON é [lng, lat]; o mapa consome [lat, lng].
      longitude: f.geometry.coordinates[0],
      latitude: f.geometry.coordinates[1],
    })),
    truncated: data.truncated,
    message: data.message,
  };
}

// ─── Detalhe da UPF ───────────────────────────────────────────────────────────

/** Objeto aninhado {id, nome} usado no detalhe (município, território, etc.). */
export type NestedRef = { id: number; nome: string };

/**
 * Titular aninhado no detalhe da UPF. Espelha
 * apps/sgp/serializers.py::TitularNestedSerializer. O titular é um MembroFamilia
 * (grau_parentesco="titular"). CPF vem CRU (sem máscara) — mascarar na exibição.
 * Campos de choice (genero, cor_raca, escolaridade) são inteiros + `*_display`.
 *
 * `cor_raca`/`cor_raca_display` são omitidos pelo backend (BE-25/#187) quando o
 * perfil do usuário não tem permissão de leitura — a ausência da chave é o
 * sinal usado pelo frontend para não renderizar o campo (#192).
 */
export type TitularNested = {
  id: number;
  nome_completo: string;
  cpf: string;
  rg: string;
  data_nascimento: string | null;
  genero: number | null;
  genero_display: string;
  cor_raca?: number | null;
  cor_raca_display?: string;
  escolaridade: number | null;
  escolaridade_display: string;
  nis: string;
  idade: number | null;
};

/**
 * Espelha apps/sgp/serializers.py::UPFDetailSerializer (leitura).
 * Os campos de choice da UPF (pct, posse_terra, dispositivo, tipo_moradia,
 * situacao_moradia, material_construcao, energia, agua) vêm como id inteiro cru,
 * sem `*_display` — usar labelForValue() na exibição. Os dados do titular ficam
 * no objeto aninhado `titular`.
 */
export type UpfDetail = {
  id: number;
  projeto: NestedRef;
  titular: TitularNested;
  apelido: string;
  celular: string;
  whatsapp: string;
  internet: boolean;
  dispositivo: number | null;
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  municipio: NestedRef;
  territorio: NestedRef | null;
  comunidade: NestedRef | null;
  latitude: string | null;
  longitude: string | null;
  pct: number | null;
  posse_terra: number | null;
  area_terra_ha: string | null;
  situacao_moradia: number | null;
  tipo_moradia: number | null;
  material_construcao: number | null;
  num_comodos: number | null;
  energia: number | null;
  agua: number | null;
  daf_caf: string;
  seguridade_social: string[];
  foto_url: string;
  criado_por: string | null;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
  // ── Procedência SCA ────────────────────────────────────────────────────────
  // Espelham os campos de sync do backend. `ultima_origem` é o que vale para a
  // badge: `device_id` fica preenchido para sempre depois do primeiro sync,
  // inclusive quando a última edição veio da web.
  device_id: string;
  uuid_local: string | null;
  ultima_origem: "sca" | "web";
  ultimo_sync_em: string | null;

};

/** GET /api/v1/upfs/{id}/ — detalhe completo da UPF. Lança ApiError (404/403). */
export async function getUpfDetail(
  id: string | number,
  signal?: AbortSignal,
): Promise<UpfDetail> {
  const res = await apiClient(`/api/v1/upfs/${id}/`, { signal });
  return res.json();
}

// ─── Histórico da UPF ─────────────────────────────────────────────────────────

/** Espelha apps/sgp/serializers.py::HistoricoEntrySerializer. */
export type HistoricoEntry = {
  id: string;
  campo: string | null;
  valor_anterior: unknown;
  valor_novo: unknown;
  usuario: { id: number; nome: string } | null;
  timestamp: string;
};

export type HistoricoParams = {
  page: number;
  pageSize: number;
};

/** GET /api/v1/upfs/{id}/historico/ — alterações em ordem cronológica decrescente. */
export async function fetchUpfHistorico(
  id: string | number,
  { page, pageSize }: HistoricoParams,
  signal?: AbortSignal,
): Promise<Paginated<HistoricoEntry>> {
  const qs = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const res = await apiClient(`/api/v1/upfs/${id}/historico/?${qs}`, { signal });
  return res.json();
}

// ─── Escrita (cadastro / edição) ──────────────────────────────────────────────

/**
 * Campos graváveis de UPF (POST/PATCH). `territorio` é derivado no backend e não
 * é enviado. Os dados do titular são enviados achatados (nome, cpf, rg, ...),
 * conforme os campos write_only do UPFDetailSerializer que alimentam o
 * MembroFamilia titular. Campos de choice vão como id inteiro.
 */
export type UpfWritePayload = {
  projeto: number | null;
  municipio: number | null;
  comunidade: number | null;
  // Titular (write_only → _titular_* no backend)
  nome: string;
  cpf: string;
  rg?: string;
  data_nascimento?: string | null;
  genero?: number | null;
  cor_raca?: number | null;
  escolaridade?: number | null;
  nis?: string;
  // UPF
  apelido?: string;
  celular?: string;
  whatsapp?: string;
  internet?: boolean;
  dispositivo?: number | null;
  cep?: string;
  logradouro?: string;
  numero?: string;
  complemento?: string;
  bairro?: string;
  latitude?: string | null;
  longitude?: string | null;
  pct?: number | null;
  posse_terra?: number | null;
  area_terra_ha?: string | null;
  situacao_moradia?: number | null;
  tipo_moradia?: number | null;
  material_construcao?: number | null;
  num_comodos?: number | null;
  energia?: number | null;
  agua?: number | null;
  daf_caf?: string;
  seguridade_social?: string[];
};

/** POST /api/v1/upfs/ — cria uma UPF; retorna o detalhe com id. */
export async function createUpf(payload: UpfWritePayload): Promise<UpfDetail> {
  const res = await apiClient("/api/v1/upfs/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** PATCH /api/v1/upfs/{id}/ — atualiza uma UPF; retorna o detalhe. */
export async function updateUpf(
  id: string | number,
  payload: UpfWritePayload,
): Promise<UpfDetail> {
  const res = await apiClient(`/api/v1/upfs/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return res.json();
}

// ─── Cascata (Estado → Município → Comunidade) e Projeto ──────────────────────

export type StateItem = { id: number; sigla: string; nome: string };

/**
 * GET /api/v1/states/ — os estados inteiros, id e sigla juntos.
 *
 * Existe porque as duas chaves são necessárias ao mesmo tempo na distribuição
 * orçamentária: o painel identifica o estado por SIGLA (`estado=PE`), mas
 * `BudgetAllocationCreateSerializer.estado_id` é uma PK. Um select alimentado
 * só por sigla não consegue montar o payload de criação, e um alimentado só por
 * id não consegue casar com o pai que veio do detalhamento.
 */
export async function fetchStates(signal?: AbortSignal): Promise<StateItem[]> {
  const res = await apiClient("/api/v1/states/?limit=1000", { signal });
  const data: Paginated<StateItem> = await res.json();
  return data.results;
}

/** GET /api/v1/states/ — UFs para o primeiro nível da cascata. */
export async function fetchStateOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/states/?limit=1000", { signal });
  const data: Paginated<StateItem> = await res.json();
  return data.results.map((s) => ({
    value: String(s.id),
    label: `${s.nome} (${s.sigla})`,
  }));
}

/**
 * GET /api/v1/states/ — UFs identificadas pela SIGLA, não pelo id.
 *
 * A cascata da UPF manda o id do estado (`?state={id}`), mas nem toda API do
 * projeto trabalha assim: o painel de orçamento (§5.3.3) valida `estado` por
 * sigla e responde 400 a um id. Um `<Select>` alimentado por
 * `fetchStateOptions` ali fica quebrado das duas pontas — o valor da URL
 * ("PE") não casa com nenhuma opção e o select cai no placeholder, e o que
 * ele grava de volta ("6") é descartado na leitura seguinte.
 *
 * Duas funções em vez de um parâmetro porque o que muda é o CONTRATO de quem
 * consome o valor, não uma preferência de exibição: quem chama precisa
 * escolher conscientemente qual chave vai mandar para a API.
 */
export async function fetchStateSiglaOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/states/?limit=1000", { signal });
  const data: Paginated<StateItem> = await res.json();
  return data.results.map((s) => ({
    value: s.sigla,
    label: `${s.nome} (${s.sigla})`,
  }));
}

/** Município para o select da cascata, carregando também seu território. */
export type MunicipalityOpt = SelectOption & { territoryId: number | null };

type MunicipalityItem = {
  id: number;
  nome: string;
  state: number;
  territory: number | null;
};

/** GET /api/v1/municipalities/?state={id} — municípios do estado, com território. */
export async function fetchMunicipalitiesByState(
  stateId: string | number,
  signal?: AbortSignal,
): Promise<MunicipalityOpt[]> {
  const res = await apiClient(
    `/api/v1/municipalities/?state=${stateId}&limit=1000`,
    { signal },
  );
  const data: Paginated<MunicipalityItem> = await res.json();
  return data.results.map((m) => ({
    value: String(m.id),
    label: m.nome,
    territoryId: m.territory,
  }));
}

/** GET /api/v1/municipalities/{id}/ — usado no prefill de edição (descobre o estado). */
export async function fetchMunicipality(
  id: string | number,
  signal?: AbortSignal,
): Promise<MunicipalityItem> {
  const res = await apiClient(`/api/v1/municipalities/${id}/`, { signal });
  return res.json();
}

/** GET /api/v1/territories/ — mapa id→nome para exibir o território derivado. */
export async function fetchTerritoryMap(
  signal?: AbortSignal,
): Promise<Map<number, string>> {
  const res = await apiClient("/api/v1/territories/?limit=500", { signal });
  const data: Paginated<Territorio> = await res.json();
  return new Map(data.results.map((t) => [t.id, t.nome]));
}

/**
 * GET /api/v1/territories/ — os territórios inteiros, com as siglas que cobrem.
 *
 * `fetchTerritoryMap` joga `estados` fora, e há tela que precisa dele: a
 * distribuição orçamentária (§5.3.2) só pode oferecer ao Articulador os
 * territórios que intersectam os estados dele, que é exatamente o teste de
 * `BudgetAllocationViewSet._autorizar`
 * (`territorio.estados & allowed_states_for_user`). Um território pode cobrir
 * mais de um estado, então o campo é uma lista e a comparação é de interseção,
 * nunca de igualdade.
 */
export async function fetchTerritorios(
  signal?: AbortSignal,
): Promise<Territorio[]> {
  const res = await apiClient("/api/v1/territories/?limit=500", { signal });
  const data: Paginated<Territorio> = await res.json();
  return data.results;
}

/** GET /api/v1/municipios/{id}/comunidades/ — comunidades ativas do município. */
export async function fetchComunidadeOptions(
  municipioId: string | number,
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient(
    `/api/v1/municipios/${municipioId}/comunidades/?limit=100`,
    { signal },
  );
  const data: Paginated<{ id: number; nome: string }> = await res.json();
  return data.results.map((c) => ({ value: String(c.id), label: c.nome }));
}

/** POST /api/v1/municipios/{id}/comunidades/ — cria comunidade (nome + lat/lng opcionais). */
export async function createComunidade(
  municipioId: string | number,
  payload: { nome: string; lat?: string | null; lng?: string | null },
): Promise<{ id: number; nome: string }> {
  const res = await apiClient(
    `/api/v1/municipios/${municipioId}/comunidades/`,
    { method: "POST", body: JSON.stringify(payload) },
  );
  return res.json();
}

/**
 * GET /api/v1/projetos/ — opções de projeto. O endpoint ainda não existe no
 * backend; em erro/404 retorna [] (forward-compatible), mantendo o wizard pronto
 * para quando a rota for criada.
 */
export async function fetchProjetoOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  try {
    const res = await apiClient("/api/v1/projetos/?ativo=true&limit=1000", {
      signal,
    });
    const data: Paginated<{ id: number; nome: string }> = await res.json();
    return data.results.map((p) => ({ value: String(p.id), label: p.nome }));
  } catch {
    return [];
  }
}
