import {
  STATUS_EXIGE_JUSTIFICATIVA,
  type AcaoPT,
  type AtividadeDetail,
  type AtividadeWritePayload,
} from "@/app/lib/atividades";

/** UPF selecionada como participante (o backend só devolve o id na leitura). */
export type UpfRef = {
  id: number;
  nome: string;
  /** Já mascarado pelo backend na listagem; "" quando desconhecido. */
  cpf: string;
};

/**
 * upfId de um membro carregado da API mas ainda não associado à sua UPF —
 * acontece no prefill de edição, onde o backend só devolve o id do membro.
 */
export const PENDING_UPF_ID = -1;

/** Membro selecionado como participante, com a UPF de origem para agrupar na UI. */
export type MembroRef = {
  id: number;
  nome: string;
  upfId: number;
};

/**
 * Estado do formulário de atividade.
 *
 * Convenções herdadas do wizard de UPF: campos de select guardam o id como
 * string; `estado` existe só para dirigir a cascata e não vai no payload.
 * `acao`, `upfs_participantes` e `membros_participantes` guardam objetos (e não
 * ids) porque a UI precisa exibir rótulo — a conversão para PK acontece em
 * formToPayload().
 */
export type AtividadeFormData = {
  // Identificação
  titulo: string;
  tipo_atividade: string;
  // Vínculo com o PT
  acao: AcaoPT | null;
  // Atuação
  forma_atuacao: string;
  // Equipe
  tecnico_responsavel: string;
  equipe_adicional: number[];
  // Localização
  estado: string;
  municipio: string;
  comunidade: string;
  ambito: string;
  latitude: string;
  longitude: string;
  // Datas
  data_inicio: string;
  data_fim: string;
  // Participantes
  upfs_participantes: UpfRef[];
  membros_participantes: MembroRef[];
  // Parceiros e narrativa
  parceiros: string;
  descricao_narrativa: string;
  resultados_alcancados: string;
  // Status
  status: string;
  justificativa: string;
};

export const EMPTY_FORM: AtividadeFormData = {
  titulo: "",
  tipo_atividade: "",
  acao: null,
  forma_atuacao: "",
  tecnico_responsavel: "",
  equipe_adicional: [],
  estado: "",
  municipio: "",
  comunidade: "",
  ambito: "",
  latitude: "",
  longitude: "",
  data_inicio: "",
  data_fim: "",
  upfs_participantes: [],
  membros_participantes: [],
  parceiros: "",
  descricao_narrativa: "",
  resultados_alcancados: "",
  status: "planejado",
  justificativa: "",
};

/**
 * Preenche o formulário a partir do detalhe (edição).
 *
 * O serializer devolve apenas os ids de UPFs e membros participantes, sem os
 * nomes. As UPFs são resolvidas pelo formulário (fetch por id) e os membros
 * entram aqui como placeholders (`upfId: -1`), que o ParticipantesSection
 * reconcilia assim que carrega os membros de cada UPF. `estado` também é
 * resolvido à parte, a partir do município.
 */
export function detailToForm(atividade: AtividadeDetail): AtividadeFormData {
  return {
    ...EMPTY_FORM,
    titulo: atividade.titulo,
    tipo_atividade: atividade.tipo_atividade,
    acao: {
      id: atividade.acao.id,
      meta: 0,
      numero: atividade.acao.numero,
      descricao: atividade.acao.descricao,
    },
    forma_atuacao: atividade.forma_atuacao,
    tecnico_responsavel: String(atividade.tecnico_responsavel.id),
    equipe_adicional: atividade.equipe_adicional,
    municipio: String(atividade.municipio.id),
    comunidade: atividade.comunidade ? String(atividade.comunidade.id) : "",
    ambito: atividade.ambito,
    latitude: atividade.latitude ?? "",
    longitude: atividade.longitude ?? "",
    data_inicio: atividade.data_inicio,
    data_fim: atividade.data_fim,
    membros_participantes: atividade.membros_participantes.map((id) => ({
      id,
      nome: `Membro #${id}`,
      upfId: PENDING_UPF_ID,
    })),
    parceiros: atividade.parceiros,
    descricao_narrativa: atividade.descricao_narrativa,
    resultados_alcancados: atividade.resultados_alcancados,
    status: atividade.status,
    justificativa: atividade.justificativa,
  };
}

function nullIfBlank(value: string): string | null {
  const t = value.trim();
  return t === "" ? null : t;
}

/** Converte o formulário no payload de escrita (FKs e M2M como PK). */
export function formToPayload(
  form: AtividadeFormData,
): AtividadeWritePayload {
  return {
    titulo: form.titulo.trim(),
    tipo_atividade: form.tipo_atividade,
    acao: form.acao ? form.acao.id : null,
    forma_atuacao: form.forma_atuacao,
    tecnico_responsavel: form.tecnico_responsavel
      ? Number(form.tecnico_responsavel)
      : null,
    equipe_adicional: form.equipe_adicional,
    municipio: form.municipio ? Number(form.municipio) : null,
    comunidade: form.comunidade ? Number(form.comunidade) : null,
    ambito: form.ambito,
    latitude: nullIfBlank(form.latitude),
    longitude: nullIfBlank(form.longitude),
    data_inicio: form.data_inicio,
    data_fim: form.data_fim,
    upfs_participantes: form.upfs_participantes.map((u) => u.id),
    membros_participantes: form.membros_participantes.map((m) => m.id),
    parceiros: form.parceiros.trim(),
    descricao_narrativa: form.descricao_narrativa.trim(),
    resultados_alcancados: form.resultados_alcancados.trim(),
    status: form.status,
    justificativa: form.justificativa.trim(),
  };
}

/** True quando o status escolhido torna a Justificativa obrigatória. */
export function exigeJustificativa(status: string): boolean {
  return STATUS_EXIGE_JUSTIFICATIVA.includes(status);
}

function isValidCoord(value: string, max: number): boolean {
  const n = Number(value);
  return Number.isFinite(n) && Math.abs(n) <= max;
}

/**
 * Validação client-side. Retorna um mapa campo → mensagem; vazio significa
 * formulário válido. As chaves usam o nome do campo no backend, de modo que
 * erros de validação da API caem no mesmo lugar.
 */
export function validate(
  form: AtividadeFormData,
): Record<string, string> {
  const errs: Record<string, string> = {};

  // ── Obrigatórios (campos sem blank=True no model) ──────────────────────────
  if (!form.titulo.trim()) errs.titulo = "Informe o título da atividade.";
  if (!form.tipo_atividade) errs.tipo_atividade = "Selecione o tipo de atividade.";
  if (!form.acao) errs.acao = "Selecione a Ação do PT.";
  if (!form.forma_atuacao) errs.forma_atuacao = "Selecione a forma de atuação.";
  if (!form.tecnico_responsavel)
    errs.tecnico_responsavel = "Selecione o técnico responsável.";
  if (!form.municipio) errs.municipio = "Selecione o município.";
  if (!form.ambito) errs.ambito = "Selecione o âmbito.";
  if (!form.data_inicio) errs.data_inicio = "Informe a data de início.";
  if (!form.data_fim) errs.data_fim = "Informe a data de fim.";
  if (!form.descricao_narrativa.trim())
    errs.descricao_narrativa = "Descreva a atividade.";
  if (!form.status) errs.status = "Selecione o status.";

  // ── Datas ─────────────────────────────────────────────────────────────────
  if (form.data_inicio && form.data_fim && form.data_fim < form.data_inicio) {
    errs.data_fim = "A data de fim não pode ser anterior à data de início.";
  }

  // ── Geolocalização: par completo ou nenhum ────────────────────────────────
  const temLat = form.latitude.trim() !== "";
  const temLng = form.longitude.trim() !== "";
  if (temLat !== temLng) {
    const campo = temLat ? "longitude" : "latitude";
    errs[campo] = "Informe latitude e longitude juntas.";
  } else if (temLat && temLng) {
    if (!isValidCoord(form.latitude, 90))
      errs.latitude = "Latitude inválida (entre -90 e 90).";
    if (!isValidCoord(form.longitude, 180))
      errs.longitude = "Longitude inválida (entre -180 e 180).";
  }

  // ── Justificativa condicional ─────────────────────────────────────────────
  if (exigeJustificativa(form.status) && !form.justificativa.trim()) {
    errs.justificativa =
      "Justificativa é obrigatória quando o status é Não realizada ou Cancelada.";
  }

  return errs;
}

/**
 * Ordem dos campos no formulário — usada para focar o primeiro campo com erro
 * após um submit inválido. Inclui os aliases que o backend pode devolver.
 */
export const FIELD_ORDER: string[] = [
  "titulo",
  "tipo_atividade",
  "acao",
  "forma_atuacao",
  "tecnico_responsavel",
  "equipe_adicional",
  "estado",
  "municipio",
  "comunidade",
  "ambito",
  "data_inicio",
  "data_fim",
  "latitude",
  "longitude",
  "upfs_participantes",
  "membros_participantes",
  "parceiros",
  "descricao_narrativa",
  "resultados_alcancados",
  "status",
  "justificativa",
];

/** id do elemento DOM de cada campo, para foco e para os testes. */
export function fieldId(field: string): string {
  return `atividade-${field.replace(/_/g, "-")}`;
}

/** Primeiro campo com erro na ordem visual do formulário. */
export function firstErrorField(
  errors: Record<string, string>,
): string | undefined {
  return FIELD_ORDER.find((f) => errors[f]);
}
