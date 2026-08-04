export type UpfMapa = {
  id: number;
  nome_titular: string;
  cpf: string;
  municipio: string;
  territorio: string | null;
  foto_url: string | null;
  latitude: number;
  longitude: number;
  ativa: boolean;
};

export type UpfMapaResponse = {
  results: UpfMapa[];
  truncated: boolean;
  total: number;
};

export type UpfMapaFilters = {
  search?: string;
  municipio?: string;
  territorio?: string;
  projeto?: string;
  status?: "ativas" | "inativas" | "todas";
};

const SEED: UpfMapa[] = [
  { id: 1, nome_titular: "Maria Aparecida da Silva", cpf: "123.***.***-45", municipio: "Petrolina", territorio: "Sertão do São Francisco", foto_url: null, latitude: -9.3891, longitude: -40.5030, ativa: true },
  { id: 2, nome_titular: "João Batista dos Santos", cpf: "234.***.***-56", municipio: "Petrolina", territorio: "Sertão do São Francisco", foto_url: null, latitude: -9.4102, longitude: -40.5217, ativa: true },
  { id: 3, nome_titular: "Antônia Ferreira Lima", cpf: "345.***.***-67", municipio: "Juazeiro", territorio: "Sertão do São Francisco", foto_url: null, latitude: -9.4159, longitude: -40.4986, ativa: true },
  { id: 4, nome_titular: "Sebastião Rodrigues", cpf: "456.***.***-78", municipio: "Juazeiro", territorio: "Sertão do São Francisco", foto_url: null, latitude: -9.4278, longitude: -40.5133, ativa: false },
  { id: 5, nome_titular: "Rosa Maria de Souza", cpf: "567.***.***-89", municipio: "Salgueiro", territorio: "Sertão Central", foto_url: null, latitude: -8.0722, longitude: -39.1245, ativa: true },
  { id: 6, nome_titular: "Francisco das Chagas", cpf: "678.***.***-90", municipio: "Salgueiro", territorio: "Sertão Central", foto_url: null, latitude: -8.0801, longitude: -39.1301, ativa: true },
  { id: 7, nome_titular: "Josefa Cardoso", cpf: "789.***.***-01", municipio: "Serra Talhada", territorio: "Sertão do Pajeú", foto_url: null, latitude: -7.9884, longitude: -38.2925, ativa: true },
  { id: 8, nome_titular: "Manoel Alves Neto", cpf: "890.***.***-12", municipio: "Serra Talhada", territorio: "Sertão do Pajeú", foto_url: null, latitude: -7.9945, longitude: -38.3011, ativa: false },
  { id: 9, nome_titular: "Luzia Barbosa", cpf: "901.***.***-23", municipio: "Ouricuri", territorio: "Araripe", foto_url: null, latitude: -7.8811, longitude: -40.0819, ativa: true },
  { id: 10, nome_titular: "Raimundo Nonato", cpf: "012.***.***-34", municipio: "Ouricuri", territorio: "Araripe", foto_url: null, latitude: -7.8752, longitude: -40.0705, ativa: true },
  { id: 11, nome_titular: "Cícera Vieira", cpf: "111.***.***-11", municipio: "Arcoverde", territorio: "Sertão do Moxotó", foto_url: null, latitude: -8.4189, longitude: -37.0561, ativa: true },
  { id: 12, nome_titular: "Damião Gomes", cpf: "222.***.***-22", municipio: "Belém do São Francisco", territorio: "Sertão do São Francisco", foto_url: null, latitude: -8.7581, longitude: -38.9645, ativa: false },
];

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function fetchUpfsMapaMock(
  filters: UpfMapaFilters,
  signal?: AbortSignal,
): Promise<UpfMapaResponse> {
  await delay(400);
  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

  const term = filters.search?.trim().toLowerCase() ?? "";
  const results = SEED.filter((u) => {
    if (filters.status === "ativas" && !u.ativa) return false;
    if (filters.status === "inativas" && u.ativa) return false;
    if (filters.municipio && !u.municipio.toLowerCase().includes(filters.municipio.toLowerCase())) return false;
    if (filters.territorio && (u.territorio ?? "").toLowerCase() !== filters.territorio.toLowerCase()) return false;
    if (term) {
      const hay = `${u.nome_titular} ${u.cpf} ${u.municipio} ${u.territorio ?? ""}`.toLowerCase();
      if (!hay.includes(term)) return false;
    }
    return true;
  });

  return { results, truncated: false, total: results.length };
}
