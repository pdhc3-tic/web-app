import type { UpfDetail, UpfWritePayload } from "@/app/lib/upfs";
import { formatCepInput } from "@/app/lib/format";

/**
 * Estado do formulário do wizard. Todos os campos de input são strings (ids de
 * relacionamento também), exceto `seguridade_social` (array) e `internet` (bool).
 * `estado` é apenas de UI (dirige a cascata; não vai no payload).
 */
export type UpfFormData = {
  // Passo 1 — Localização
  estado: string;
  municipio: string;
  comunidade: string;
  projeto: string;
  latitude: string;
  longitude: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cep: string;
  // Passo 2 — Dados Básicos
  nome_titular: string;
  cpf: string;
  rg: string;
  apelido: string;
  data_nasc: string;
  genero: string;
  cor_raca: string;
  pct: string;
  nis: string;
  daf_caf: string;
  escolaridade: string;
  seguridade_social: string[];
  posse_terra: string;
  area_terra_ha: string;
  // Passo 3 — Comunicação (telefone → celular no backend)
  telefone: string;
  whatsapp: string;
  internet: boolean;
  dispositivo: string;
  // Passo 4 — Moradia
  tipo_moradia: string;
  situacao_moradia: string;
  material_construcao: string;
  num_comodos: string;
  energia: string;
  agua: string;
};

export const EMPTY_FORM: UpfFormData = {
  estado: "",
  municipio: "",
  comunidade: "",
  projeto: "",
  latitude: "",
  longitude: "",
  logradouro: "",
  numero: "",
  complemento: "",
  bairro: "",
  cep: "",
  nome_titular: "",
  cpf: "",
  rg: "",
  apelido: "",
  data_nasc: "",
  genero: "",
  cor_raca: "",
  pct: "",
  nis: "",
  daf_caf: "",
  escolaridade: "",
  seguridade_social: [],
  posse_terra: "",
  area_terra_ha: "",
  telefone: "",
  whatsapp: "",
  internet: false,
  dispositivo: "",
  tipo_moradia: "",
  situacao_moradia: "",
  material_construcao: "",
  num_comodos: "",
  energia: "",
  agua: "",
};

/** "" ↔ null para choices inteiros vindos/indo do formulário (value string). */
function intToStr(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

function strToInt(value: string): number | null {
  return value ? Number(value) : null;
}

/** Preenche o formulário a partir do detalhe (edição). `estado` é resolvido à parte. */
export function detailToForm(upf: UpfDetail): UpfFormData {
  return {
    ...EMPTY_FORM,
    municipio: String(upf.municipio.id),
    comunidade: upf.comunidade ? String(upf.comunidade.id) : "",
    projeto: String(upf.projeto.id),
    latitude: upf.latitude ?? "",
    longitude: upf.longitude ?? "",
    logradouro: upf.logradouro,
    numero: upf.numero,
    complemento: upf.complemento,
    bairro: upf.bairro,
    cep: formatCepInput(upf.cep),
    // Titular (objeto aninhado)
    nome_titular: upf.titular.nome_completo,
    cpf: upf.titular.cpf,
    rg: upf.titular.rg,
    data_nasc: upf.titular.data_nasc ?? "",
    genero: intToStr(upf.titular.genero),
    cor_raca: intToStr(upf.titular.cor_raca),
    escolaridade: intToStr(upf.titular.escolaridade),
    nis: upf.titular.nis,
    // UPF
    apelido: upf.apelido,
    pct: intToStr(upf.pct),
    daf_caf: upf.daf_caf,
    posse_terra: intToStr(upf.posse_terra),
    area_terra_ha: upf.area_terra_ha ?? "",
    seguridade_social: upf.seguridade_social ?? [],
    telefone: upf.celular,
    whatsapp: upf.whatsapp,
    internet: upf.internet,
    dispositivo: intToStr(upf.dispositivo),
    tipo_moradia: intToStr(upf.tipo_moradia),
    situacao_moradia: intToStr(upf.situacao_moradia),
    material_construcao: intToStr(upf.material_construcao),
    num_comodos:
      upf.num_comodos !== null && upf.num_comodos !== undefined
        ? String(upf.num_comodos)
        : "",
    energia: intToStr(upf.energia),
    agua: intToStr(upf.agua),
  };
}

function digits(value: string): string {
  return value.replace(/\D/g, "");
}

function numOrNull(value: string): string | null {
  const t = value.trim();
  return t === "" ? null : t;
}

/** Converte o formulário no payload de escrita (sem `territorio`, CPF só dígitos). */
export function formToPayload(form: UpfFormData): UpfWritePayload {
  return {
    projeto: form.projeto ? Number(form.projeto) : null,
    municipio: form.municipio ? Number(form.municipio) : null,
    comunidade: form.comunidade ? Number(form.comunidade) : null,
    // Titular
    nome: form.nome_titular.trim(),
    cpf: digits(form.cpf),
    rg: form.rg,
    data_nasc: form.data_nasc || null,
    genero: strToInt(form.genero),
    cor_raca: strToInt(form.cor_raca),
    escolaridade: strToInt(form.escolaridade),
    nis: form.nis,
    // UPF
    apelido: form.apelido,
    celular: form.telefone,
    whatsapp: form.whatsapp,
    internet: form.internet,
    dispositivo: strToInt(form.dispositivo),
    cep: digits(form.cep),
    logradouro: form.logradouro,
    numero: form.numero,
    complemento: form.complemento,
    bairro: form.bairro,
    latitude: numOrNull(form.latitude),
    longitude: numOrNull(form.longitude),
    pct: strToInt(form.pct),
    posse_terra: strToInt(form.posse_terra),
    area_terra_ha: numOrNull(form.area_terra_ha),
    situacao_moradia: strToInt(form.situacao_moradia),
    tipo_moradia: strToInt(form.tipo_moradia),
    material_construcao: strToInt(form.material_construcao),
    num_comodos: form.num_comodos.trim() ? Number(form.num_comodos) : null,
    energia: strToInt(form.energia),
    agua: strToInt(form.agua),
    daf_caf: form.daf_caf,
    seguridade_social: form.seguridade_social,
  };
}

/** Mapeia o nome do campo (inclusive vindo de erro do backend) para o passo (0–3). */
export const FIELD_STEP: Record<string, number> = {
  estado: 0,
  municipio: 0,
  comunidade: 0,
  projeto: 0,
  territorio: 0,
  latitude: 0,
  longitude: 0,
  logradouro: 0,
  numero: 0,
  complemento: 0,
  bairro: 0,
  cep: 0,
  nome_titular: 1,
  nome: 1,
  cpf: 1,
  rg: 1,
  apelido: 1,
  data_nasc: 1,
  genero: 1,
  cor_raca: 1,
  pct: 1,
  nis: 1,
  daf_caf: 1,
  escolaridade: 1,
  seguridade_social: 1,
  posse_terra: 1,
  area_terra_ha: 1,
  telefone: 2,
  celular: 2,
  whatsapp: 2,
  internet: 2,
  dispositivo: 2,
  tipo_moradia: 3,
  situacao_moradia: 3,
  material_construcao: 3,
  num_comodos: 3,
  energia: 3,
  agua: 3,
};

export const STEP_LABELS = [
  "Localização",
  "Dados Básicos",
  "Comunicação",
  "Moradia",
];
