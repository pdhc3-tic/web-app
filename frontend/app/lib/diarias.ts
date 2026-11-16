import { apiClient } from "./api";

/**
 * Tabela de diárias do SGD (#366, SGD-REF-BE-12 / #358): faixas de destino,
 * valores com vigência e parâmetros de contagem.
 *
 * Leitura para qualquer usuário autenticado; escrita só Super Admin e FGD.
 */

const BASE = "/api/v1/sgd/config/diarias";

export type OrigemValorDiaria = "federal" | "fgd";

export const ORIGEM_LABEL: Record<OrigemValorDiaria, string> = {
  federal: "Federal",
  fgd: "Valor FGD",
};

export const OPCOES_DE_ORIGEM: { value: OrigemValorDiaria; label: string }[] = [
  { value: "federal", label: "Federal (Decreto 5.992/2006)" },
  { value: "fgd", label: "Valor FGD" },
];

export type Enquadramento = { codigo_ibge: string; nome_referencia: string };

export type FaixaDestino = {
  id: number;
  nome: string;
  ordem: number;
  /** A faixa que recebe os municípios sem enquadramento explícito. */
  padrao: "capitais" | "demais" | null;
  ativo: boolean;
  enquadramentos: Enquadramento[];
};

export const PADRAO_LABEL: Record<NonNullable<FaixaDestino["padrao"]>, string> = {
  capitais: "Recebe as capitais sem enquadramento",
  demais: "Recebe as demais localidades",
};

export type ValorDiaria = {
  id: number;
  faixa_destino: number;
  faixa_destino_nome: string;
  categoria_beneficiario: string;
  /** Datas `AAAA-MM-DD`; início e fim são inclusivos. */
  vigencia_inicio: string;
  vigencia_fim: string | null;
  valor: string;
  origem: OrigemValorDiaria;
  criado_por_nome: string | null;
  criado_em: string;
};

export type ParametrosDiarias = {
  regra_inteira_por_pernoite: boolean;
  regra_meia_no_retorno: boolean;
  regra_meia_sem_pernoite: boolean;
  regra_meia_hospedagem_custeada: boolean;
  adicional_embarque_ativo: boolean;
  adicional_embarque_valor: string;
};

export type RegraDeContagem = Exclude<keyof ParametrosDiarias, "adicional_embarque_ativo" | "adicional_embarque_valor">;

/** As regras de contagem, na ordem em que o backend as aplica. */
export const REGRAS_DE_CONTAGEM: { chave: RegraDeContagem; rotulo: string; ajuda: string }[] = [
  {
    chave: "regra_inteira_por_pernoite",
    rotulo: "Diária inteira por pernoite",
    ajuda: "Desligada, conta uma diária por dia de viagem e as regras de meia diária não se aplicam.",
  },
  {
    chave: "regra_meia_no_retorno",
    rotulo: "Meia diária no dia do retorno",
    ajuda: "Desligada, o dia do retorno conta como diária inteira.",
  },
  {
    chave: "regra_meia_sem_pernoite",
    rotulo: "Meia diária em viagem sem pernoite",
    ajuda: "Ida e volta no mesmo dia. Desligada, conta uma diária inteira.",
  },
  {
    chave: "regra_meia_hospedagem_custeada",
    rotulo: "Meia diária quando a hospedagem é custeada por outro meio",
    ajuda: "Vale para cada pernoite da solicitação marcada com hospedagem custeada. Desligada, conta inteira.",
  },
];

export async function listarFaixas(signal?: AbortSignal): Promise<FaixaDestino[]> {
  const res = await apiClient(`${BASE}/faixas/`, { signal });
  return res.json();
}

export async function listarValores(signal?: AbortSignal): Promise<ValorDiaria[]> {
  const res = await apiClient(`${BASE}/tabela/`, { signal });
  return res.json();
}

export async function lerParametros(signal?: AbortSignal): Promise<ParametrosDiarias> {
  const res = await apiClient(`${BASE}/parametros/`, { signal });
  return res.json();
}

export type NovoValor = { valor: string; vigencia_inicio: string; origem: OrigemValorDiaria };

/** POST /tabela/ — o primeiro valor de uma faixa (ou o de um período sem valor). */
export async function criarValor(faixaId: number, dados: NovoValor): Promise<ValorDiaria> {
  const res = await apiClient(`${BASE}/tabela/`, {
    method: "POST",
    body: JSON.stringify({ faixa_destino: faixaId, ...dados }),
  });
  return res.json();
}

/**
 * PATCH /tabela/{id}/ — editar não sobrescreve: a vigência atual termina na
 * véspera de `vigencia_inicio` e uma linha nova começa nessa data.
 */
export async function registrarNovaVigencia(valorId: number, dados: NovoValor): Promise<ValorDiaria> {
  const res = await apiClient(`${BASE}/tabela/${valorId}/`, { method: "PATCH", body: JSON.stringify(dados) });
  return res.json();
}

/** DELETE /tabela/{id}/ — só o valor que ainda não vigorou e que nenhuma solicitação usou. */
export async function excluirValor(valorId: number): Promise<void> {
  await apiClient(`${BASE}/tabela/${valorId}/`, { method: "DELETE" });
}

/** PATCH /faixas/{id}/ — a lista enviada substitui os municípios da faixa. */
export async function salvarEnquadramentos(faixaId: number, enquadramentos: Enquadramento[]): Promise<FaixaDestino> {
  const res = await apiClient(`${BASE}/faixas/${faixaId}/`, {
    method: "PATCH",
    body: JSON.stringify({ enquadramentos }),
  });
  return res.json();
}

export async function salvarParametros(dados: Partial<ParametrosDiarias>): Promise<ParametrosDiarias> {
  const res = await apiClient(`${BASE}/parametros/`, { method: "PATCH", body: JSON.stringify(dados) });
  return res.json();
}

type MunicipioApi = { id: number; nome: string; codigo_ibge: string };

/** GET /api/v1/municipalities/?search= — município com o código IBGE, que é a chave do enquadramento. */
export async function buscarMunicipiosComIbge(
  texto: string,
  signal?: AbortSignal,
): Promise<{ value: string; label: string; item: Enquadramento }[]> {
  const qs = new URLSearchParams({ limit: "20" });
  if (texto.trim()) qs.set("search", texto.trim());
  const res = await apiClient(`/api/v1/municipalities/?${qs}`, { signal });
  const data: { results: MunicipioApi[] } = await res.json();
  return data.results
    .filter((m) => /^\d{7}$/.test(String(m.codigo_ibge ?? "")))
    .map((m) => ({
      value: String(m.codigo_ibge),
      label: m.nome,
      item: { codigo_ibge: String(m.codigo_ibge), nome_referencia: m.nome },
    }));
}

// ─── Regras de tela ──────────────────────────────────────────────────────────

const FORMATO_QUANTIDADE = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

/** "2.5" → "2,5 diárias"; "0.5" → "0,5 diária"; "1.0" → "1 diária". */
export function formatarQuantidadeDeDiarias(numero: string | number): string {
  const n = Number(numero);
  return `${FORMATO_QUANTIDADE.format(n)} ${n > 1 ? "diárias" : "diária"}`;
}

/** Hoje em `AAAA-MM-DD`, no fuso de quem usa a tela. */
export function hojeIso(agora: Date = new Date()): string {
  const mes = String(agora.getMonth() + 1).padStart(2, "0");
  const dia = String(agora.getDate()).padStart(2, "0");
  return `${agora.getFullYear()}-${mes}-${dia}`;
}

export function vigoraEm(valor: Pick<ValorDiaria, "vigencia_inicio" | "vigencia_fim">, data: string): boolean {
  return valor.vigencia_inicio <= data && (valor.vigencia_fim === null || valor.vigencia_fim >= data);
}

export type SituacaoDoValor = "vigente" | "futuro" | "encerrado";

export function situacaoDoValor(valor: Pick<ValorDiaria, "vigencia_inicio" | "vigencia_fim">, hoje: string): SituacaoDoValor {
  if (valor.vigencia_inicio > hoje) return "futuro";
  return vigoraEm(valor, hoje) ? "vigente" : "encerrado";
}

export type CelulaDaGrade = {
  valor: ValorDiaria;
  /** A vigência começa nesta coluna; se não, o valor vem de uma vigência anterior ainda em curso. */
  iniciaAqui: boolean;
} | null;

export type GradeDeDiarias = {
  /** Inícios de vigência de qualquer faixa, do mais recente para o mais antigo. */
  vigencias: string[];
  linhas: { faixa: FaixaDestino; celulas: CelulaDaGrade[]; historico: ValorDiaria[] }[];
};

/**
 * Grade faixa de destino × vigência. Cada coluna é uma data em que algum valor
 * passou a valer; a célula traz o valor da faixa naquela data, mesmo que ele
 * tenha começado antes.
 */
export function montarGrade(faixas: FaixaDestino[], valores: ValorDiaria[]): GradeDeDiarias {
  const vigencias = [...new Set(valores.map((v) => v.vigencia_inicio))].sort().reverse();
  const linhas = [...faixas]
    .sort((a, b) => a.ordem - b.ordem || a.nome.localeCompare(b.nome, "pt-BR"))
    .map((faixa) => {
      const historico = valores
        .filter((v) => v.faixa_destino === faixa.id)
        .sort((a, b) => b.vigencia_inicio.localeCompare(a.vigencia_inicio) || b.id - a.id);
      const celulas = vigencias.map((data): CelulaDaGrade => {
        const valor = historico.find((v) => vigoraEm(v, data));
        return valor ? { valor, iniciaAqui: valor.vigencia_inicio === data } : null;
      });
      return { faixa, celulas, historico };
    });
  return { vigencias, linhas };
}

/** O valor que uma edição encerra: o vigente hoje ou, sem ele, o mais recente ainda em aberto. */
export function valorEditavel(historico: ValorDiaria[], hoje: string): ValorDiaria | null {
  return historico.find((v) => vigoraEm(v, hoje)) ?? historico.find((v) => v.vigencia_fim === null) ?? null;
}

/** Validação do diálogo de valor antes do envio; o backend confere a sobreposição. */
export function validarNovoValor(
  dados: { valor: string | null; vigencia_inicio: string },
  atual: Pick<ValorDiaria, "vigencia_inicio"> | null,
): { valor?: string; vigencia_inicio?: string } {
  const erros: { valor?: string; vigencia_inicio?: string } = {};
  if (!dados.valor || Number(dados.valor) <= 0) erros.valor = "Informe um valor maior que zero.";
  if (!dados.vigencia_inicio) {
    erros.vigencia_inicio = "Informe a data de início da vigência.";
  } else if (atual && dados.vigencia_inicio <= atual.vigencia_inicio) {
    erros.vigencia_inicio = "A nova vigência precisa começar depois do início da vigência atual.";
  }
  return erros;
}
