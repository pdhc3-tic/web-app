import type { UpfDetail, UpfWritePayload } from "@/app/lib/upfs";

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
  estado_civil: string;
  escolaridade: string;
  seguridade_social: string[];
  posse_terra: string;
  area_terra_ha: string;
  // Passo 3 — Comunicação
  telefone: string;
  whatsapp: string;
  email: string;
  internet: boolean;
  dispositivo: string;
  // Passo 4 — Moradia
  tipo_moradia: string;
  situacao_moradia: string;
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
  estado_civil: "",
  escolaridade: "",
  seguridade_social: [],
  posse_terra: "",
  area_terra_ha: "",
  telefone: "",
  whatsapp: "",
  email: "",
  internet: false,
  dispositivo: "",
  tipo_moradia: "",
  situacao_moradia: "",
  energia: "",
  agua: "",
};

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
    cep: upf.cep,
    nome_titular: upf.nome_titular,
    cpf: upf.cpf,
    rg: upf.rg,
    apelido: upf.apelido,
    data_nasc: upf.data_nasc ?? "",
    genero: upf.genero,
    cor_raca: upf.cor_raca,
    pct: upf.pct,
    nis: upf.nis,
    daf_caf: upf.daf_caf,
    estado_civil: upf.estado_civil,
    escolaridade: upf.escolaridade,
    seguridade_social: upf.seguridade_social ?? [],
    posse_terra: upf.posse_terra,
    area_terra_ha: upf.area_terra_ha ?? "",
    telefone: upf.telefone,
    whatsapp: upf.whatsapp,
    email: upf.email,
    internet: upf.internet,
    dispositivo: upf.dispositivo,
    tipo_moradia: upf.tipo_moradia,
    situacao_moradia: upf.situacao_moradia,
    energia: upf.energia,
    agua: upf.agua,
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
    nome_titular: form.nome_titular.trim(),
    cpf: digits(form.cpf),
    apelido: form.apelido,
    rg: form.rg,
    data_nasc: form.data_nasc || null,
    genero: form.genero,
    cor_raca: form.cor_raca,
    estado_civil: form.estado_civil,
    escolaridade: form.escolaridade,
    pct: form.pct,
    nis: form.nis,
    daf_caf: form.daf_caf,
    posse_terra: form.posse_terra,
    area_terra_ha: numOrNull(form.area_terra_ha),
    seguridade_social: form.seguridade_social,
    telefone: form.telefone,
    whatsapp: form.whatsapp,
    email: form.email,
    internet: form.internet,
    dispositivo: form.dispositivo,
    cep: digits(form.cep),
    logradouro: form.logradouro,
    numero: form.numero,
    complemento: form.complemento,
    bairro: form.bairro,
    latitude: numOrNull(form.latitude),
    longitude: numOrNull(form.longitude),
    tipo_moradia: form.tipo_moradia,
    situacao_moradia: form.situacao_moradia,
    energia: form.energia,
    agua: form.agua,
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
  cpf: 1,
  rg: 1,
  apelido: 1,
  data_nasc: 1,
  genero: 1,
  cor_raca: 1,
  pct: 1,
  nis: 1,
  daf_caf: 1,
  estado_civil: 1,
  escolaridade: 1,
  seguridade_social: 1,
  posse_terra: 1,
  area_terra_ha: 1,
  telefone: 2,
  whatsapp: 2,
  email: 2,
  internet: 2,
  dispositivo: 2,
  tipo_moradia: 3,
  situacao_moradia: 3,
  energia: 3,
  agua: 3,
};

export const STEP_LABELS = [
  "Localização",
  "Dados Básicos",
  "Comunicação",
  "Moradia",
];
