import type { ChaveChoice } from "@/app/lib/choices";
import { formatCpfInput, isValidCpf } from "@/app/lib/format";
import type { PropriedadeSchema, SchemaCampos } from "@/app/lib/tiposSolicitacao";

/**
 * SGD — campos de cada tipo de solicitação de recurso (#295, SGD §3.1 a §3.6).
 *
 * Espelha os validadores de `apps/sgd/services/demand_request.py`: as chaves são
 * as do `campos_json`, e obrigatório/condicional segue a mesma regra. As opções
 * dos selects vêm do `/api/v1/choices/` (`choice`), sem lista no front.
 *
 * Desde a #365 o formulário é guiado pelo catálogo de tipos do backend: estes
 * seis layouts valem como override pelo slug, e um tipo novo é desenhado a
 * partir do `schema_campos` (`configDoSchema`). `configDoTipo` escolhe.
 */

/** Os seis tipos de origem, com layout próprio. Um tipo novo do catálogo é só uma string. */
export type TipoSolicitacao = "diaria" | "passagem" | "veiculo" | "grafico" | "alimentacao" | "equipamento";

export type TipoCampo =
  | "texto"
  | "textarea"
  | "cpf"
  | "data"
  | "dataHora"
  | "inteiro"
  | "booleano"
  | "choice"
  | "municipio"
  /** Número de um tipo do catálogo: inteiro ou decimal, com mínimo opcional. */
  | "numero";

/** O estado do formulário: tudo string, como os inputs entregam. */
export type ValoresCampos = Record<string, string>;

export type CampoSolicitacao = {
  chave: string;
  rotulo: string;
  tipo: TipoCampo;
  /** Para `choice`: a lista do `/choices/`. */
  choice?: ChaveChoice;
  /** Para `choice` de um tipo do catálogo: as opções do `enum`/`oneOf` do schema. */
  opcoes?: { value: string; label: string; original: string | number }[];
  /** Para `numero`: só inteiros, e o menor valor aceito. */
  inteiro?: boolean;
  minimo?: number;
  /** Para `dataHora` de um tipo do catálogo: vai como ISO completo, o `date-time` do JSON Schema. */
  isoCompleto?: boolean;
  /** Mensagem própria do schema para valor fora da regra. */
  mensagem?: string;
  obrigatorio: boolean;
  /** Campo condicional: só aparece (e só vai no payload) quando devolve true. */
  visivel?: (valores: ValoresCampos) => boolean;
  ajuda?: string;
  /** Ocupa a linha inteira na grade de duas colunas. */
  largo?: boolean;
};

export type ConfigTipo = {
  campos: CampoSolicitacao[];
  /**
   * O valor estimado é digitado pelo solicitante. Na diária, não: o backend
   * calcula (nº de diárias × valor da diária) e ignora o que vier.
   */
  valorDigitado: boolean;
};

const SIM = "sim";
const NAO = "nao";

export const OPCOES_SIM_NAO = [
  { value: SIM, label: "Sim" },
  { value: NAO, label: "Não" },
];

const idaEVolta = (v: ValoresCampos) => v.ida_e_volta === SIM;
const classeExecutiva = (v: ValoresCampos) => v.classe === "executiva";

export const CONFIG_POR_TIPO: Record<TipoSolicitacao, ConfigTipo> = {
  // §3.1 — `_validar_diaria`
  diaria: {
    valorDigitado: false,
    campos: [
      { chave: "beneficiario_nome", rotulo: "Nome do beneficiário", tipo: "texto", obrigatorio: true, largo: true },
      { chave: "beneficiario_cpf", rotulo: "CPF do beneficiário", tipo: "cpf", obrigatorio: true },
      { chave: "beneficiario_cargo", rotulo: "Cargo ou função", tipo: "texto", obrigatorio: true },
      { chave: "beneficiario_vinculo", rotulo: "Vínculo", tipo: "choice", choice: "beneficiario_vinculo", obrigatorio: true },
      { chave: "meio_transporte", rotulo: "Meio de transporte", tipo: "choice", choice: "meio_transporte", obrigatorio: true },
      { chave: "municipio_destino_id", rotulo: "Município de destino", tipo: "municipio", obrigatorio: true, largo: true },
      { chave: "data_inicio", rotulo: "Data de ida", tipo: "data", obrigatorio: true },
      { chave: "data_fim", rotulo: "Data de volta", tipo: "data", obrigatorio: true },
      { chave: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, largo: true },
    ],
  },
  // §3.2 — `_validar_passagem`
  passagem: {
    valorDigitado: true,
    campos: [
      { chave: "passageiro_nome", rotulo: "Nome do passageiro", tipo: "texto", obrigatorio: true, largo: true },
      { chave: "passageiro_cpf", rotulo: "CPF do passageiro", tipo: "cpf", obrigatorio: true },
      { chave: "passageiro_data_nascimento", rotulo: "Data de nascimento", tipo: "data", obrigatorio: true },
      { chave: "aeroporto_origem", rotulo: "Aeroporto de origem", tipo: "texto", obrigatorio: true },
      { chave: "aeroporto_destino", rotulo: "Aeroporto de destino", tipo: "texto", obrigatorio: true },
      { chave: "data_hora_ida", rotulo: "Data e hora da ida", tipo: "dataHora", obrigatorio: true },
      { chave: "ida_e_volta", rotulo: "Viagem de ida e volta?", tipo: "booleano", obrigatorio: true },
      {
        chave: "data_hora_volta",
        rotulo: "Data e hora da volta",
        tipo: "dataHora",
        obrigatorio: true,
        visivel: idaEVolta,
      },
      { chave: "bagagem_despachada", rotulo: "Bagagem despachada?", tipo: "booleano", obrigatorio: true },
      { chave: "classe", rotulo: "Classe", tipo: "choice", choice: "classe", obrigatorio: true },
      {
        chave: "justificativa_executiva",
        rotulo: "Justificativa da classe executiva",
        tipo: "textarea",
        obrigatorio: true,
        visivel: classeExecutiva,
        largo: true,
      },
      { chave: "urgencia", rotulo: "Urgência", tipo: "choice", choice: "urgencia", obrigatorio: true },
    ],
  },
  // §3.3 — `_validar_veiculo`
  veiculo: {
    valorDigitado: true,
    campos: [
      { chave: "tipo_veiculo", rotulo: "Tipo de veículo", tipo: "choice", choice: "tipo_veiculo", obrigatorio: true },
      { chave: "numero_passageiros", rotulo: "Número de passageiros", tipo: "inteiro", obrigatorio: true },
      { chave: "data_hora_retirada", rotulo: "Retirada", tipo: "dataHora", obrigatorio: true },
      { chave: "data_hora_devolucao", rotulo: "Devolução", tipo: "dataHora", obrigatorio: true },
      { chave: "destino_rota", rotulo: "Destino e rota", tipo: "texto", obrigatorio: true, largo: true },
      { chave: "estimativa_km", rotulo: "Estimativa de km", tipo: "inteiro", obrigatorio: true },
      { chave: "motorista_incluso", rotulo: "Motorista incluso?", tipo: "booleano", obrigatorio: true },
      { chave: "combustivel_incluso", rotulo: "Combustível incluso?", tipo: "booleano", obrigatorio: true },
      {
        chave: "finalidade",
        rotulo: "Finalidade",
        tipo: "textarea",
        obrigatorio: false,
        largo: true,
        ajuda: "Se ficar em branco, vale a descrição da atividade.",
      },
    ],
  },
  // §3.4 — `_validar_grafico`
  grafico: {
    valorDigitado: true,
    campos: [
      { chave: "tipo_material", rotulo: "Tipo de material", tipo: "choice", choice: "tipo_material", obrigatorio: true },
      { chave: "quantidade", rotulo: "Quantidade", tipo: "inteiro", obrigatorio: true },
      {
        chave: "especificacoes_tecnicas",
        rotulo: "Especificações técnicas",
        tipo: "textarea",
        obrigatorio: true,
        largo: true,
      },
      { chave: "prazo_entrega", rotulo: "Prazo de entrega", tipo: "data", obrigatorio: true },
      {
        chave: "finalidade_evento",
        rotulo: "Finalidade ou evento",
        tipo: "textarea",
        obrigatorio: false,
        largo: true,
        ajuda: "Se ficar em branco, vale a descrição da atividade.",
      },
    ],
  },
  // §3.5 — `_validar_alimentacao`
  alimentacao: {
    valorDigitado: true,
    campos: [
      { chave: "tipo_refeicao", rotulo: "Tipo de refeição", tipo: "choice", choice: "tipo_refeicao", obrigatorio: true },
      { chave: "numero_pessoas", rotulo: "Número de pessoas", tipo: "inteiro", obrigatorio: true },
      { chave: "data_horario_servico", rotulo: "Data e horário do serviço", tipo: "dataHora", obrigatorio: true },
      {
        chave: "local_entrega",
        rotulo: "Local de entrega",
        tipo: "texto",
        obrigatorio: false,
        ajuda: "Se ficar em branco, vale a comunidade ou o município da atividade.",
      },
    ],
  },
  // §3.6 — `_validar_equipamento`; as 3 cotações são documentos da demanda.
  equipamento: {
    valorDigitado: true,
    campos: [
      {
        chave: "descricao_equipamento",
        rotulo: "Equipamento",
        tipo: "texto",
        obrigatorio: true,
        largo: true,
      },
      {
        chave: "especificacao_tecnica_detalhada",
        rotulo: "Especificação técnica detalhada",
        tipo: "textarea",
        obrigatorio: true,
        largo: true,
      },
      { chave: "quantidade", rotulo: "Quantidade", tipo: "inteiro", obrigatorio: true },
      { chave: "urgencia", rotulo: "Urgência", tipo: "choice", choice: "urgencia", obrigatorio: true },
      {
        chave: "finalidade_justificativa",
        rotulo: "Finalidade e justificativa",
        tipo: "textarea",
        obrigatorio: true,
        largo: true,
      },
    ],
  },
};

export function isTipoSolicitacao(tipo: string): tipo is TipoSolicitacao {
  return tipo in CONFIG_POR_TIPO;
}

function ehObjeto(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

const ehPrimitivo = (v: unknown) => v === null || ["string", "number", "boolean"].includes(typeof v);

/**
 * O que impede o renderizador de desenhar o schema, numa frase para o editor
 * do catálogo (#365); `null` quando a estrutura serve. Não é um validador de
 * JSON Schema — quem valida a regra é o backend —: confere só o formato do que
 * o formulário lê, para que um JSON válido mas fora do lugar não derrube a tela.
 * Tipos que o formulário não desenha (object, array) passam e viram texto.
 */
export function problemasDoSchema(schema: unknown): string | null {
  if (!ehObjeto(schema)) return "O schema precisa ser um objeto JSON.";
  const { properties, required } = schema;
  if (properties !== undefined && !ehObjeto(properties)) {
    return "“properties” precisa ser um objeto, com um campo por chave.";
  }
  if (required !== undefined && !(Array.isArray(required) && required.every((r) => typeof r === "string"))) {
    return "“required” precisa ser uma lista de nomes de campo.";
  }
  for (const [chave, prop] of Object.entries(properties ?? {})) {
    if (!ehObjeto(prop)) return `O campo “${chave}” precisa ser um objeto, como {"type": "string"}.`;
    const { type, title, description, enum: opcoes, oneOf, minimum, maxLength } = prop;
    const tipos = Array.isArray(type) ? type : type === undefined ? [] : [type];
    if (!tipos.every((t) => typeof t === "string")) {
      return `O “type” do campo “${chave}” precisa ser um texto, como "string", ou uma lista de textos.`;
    }
    if (title !== undefined && typeof title !== "string") return `O “title” do campo “${chave}” precisa ser texto.`;
    if (description !== undefined && typeof description !== "string") {
      return `A “description” do campo “${chave}” precisa ser texto.`;
    }
    if (opcoes !== undefined && !(Array.isArray(opcoes) && opcoes.every(ehPrimitivo))) {
      return `O “enum” do campo “${chave}” precisa ser uma lista de valores simples (texto, número ou booleano).`;
    }
    if (
      oneOf !== undefined &&
      !(
        Array.isArray(oneOf) &&
        oneOf.every((o) => ehObjeto(o) && ehPrimitivo(o.const) && (o.title === undefined || typeof o.title === "string"))
      )
    ) {
      return `O “oneOf” do campo “${chave}” precisa ser uma lista de {"const": valor, "title": "rótulo"}.`;
    }
    if (minimum !== undefined && typeof minimum !== "number") return `O “minimum” do campo “${chave}” precisa ser número.`;
    if (maxLength !== undefined && typeof maxLength !== "number") {
      return `O “maxLength” do campo “${chave}” precisa ser número.`;
    }
  }
  return null;
}

/** O tipo do JSON Schema, sem o "null" de um campo que aceita vazio. */
function tipoJson(prop: PropriedadeSchema): string | undefined {
  const tipos = Array.isArray(prop.type) ? prop.type : prop.type ? [prop.type] : [];
  return tipos.find((t) => t !== "null" && t !== "string") ?? tipos.find((t) => t !== "null");
}

/** Uma propriedade do schema → um campo do formulário. */
function campoDoSchema(chave: string, prop: PropriedadeSchema, obrigatorio: boolean): CampoSolicitacao {
  const base = {
    chave,
    rotulo: typeof prop.title === "string" && prop.title ? prop.title : chave,
    obrigatorio,
    ajuda: typeof prop.description === "string" ? prop.description : undefined,
    mensagem: typeof prop.mensagem === "string" ? prop.mensagem : undefined,
  };
  if (Array.isArray(prop.oneOf) && prop.oneOf.length) {
    return {
      ...base,
      tipo: "choice",
      opcoes: prop.oneOf.filter(ehObjeto).map((o) => ({
        value: String(o.const),
        label: typeof o.title === "string" ? o.title : String(o.const),
        original: o.const,
      })),
    };
  }
  if (Array.isArray(prop.enum) && prop.enum.length) {
    return {
      ...base,
      tipo: "choice",
      opcoes: prop.enum.map((v) => ({ value: String(v), label: String(v), original: v })),
    };
  }
  const tipo = tipoJson(prop);
  if (tipo === "boolean") return { ...base, tipo: "booleano" };
  if (tipo === "integer" || tipo === "number") {
    return { ...base, tipo: "numero", inteiro: tipo === "integer", minimo: prop.minimum };
  }
  if (prop.format === "date") return { ...base, tipo: "data" };
  if (prop.format === "date-time") return { ...base, tipo: "dataHora", isoCompleto: true };
  // Texto longo vira área de texto; o resto, linha única. Um `format` desconhecido
  // (o anexo, por exemplo — pendencias-backend-sprint-12a.md, item 1) cai aqui.
  if ((prop.maxLength ?? 0) >= 200) return { ...base, tipo: "textarea", largo: true };
  return { ...base, tipo: "texto" };
}

/**
 * O formulário de um tipo do catálogo sem layout próprio, a partir do
 * `schema_campos` (#365). A ordem vem de `x-ordem` (o JSONB do backend não
 * guarda a ordem das chaves); sem ela, primeiro os obrigatórios, na ordem do
 * `required`, e depois os demais pela chave. O valor estimado é digitado.
 */
export function configDoSchema(schema: SchemaCampos | null | undefined): ConfigTipo {
  // Defesa para um schema salvo malformado: o que não é objeto fica de fora,
  // em vez de derrubar a montagem. O editor do catálogo barra antes (problemasDoSchema).
  const brutas = ehObjeto(schema?.properties) ? schema.properties : {};
  const props = Object.fromEntries(Object.entries(brutas).filter(([, p]) => ehObjeto(p))) as Record<
    string,
    PropriedadeSchema
  >;
  const obrigatorios = Array.isArray(schema?.required) ? schema.required : [];
  const posicao = (chave: string) => {
    const x = props[chave]?.["x-ordem"];
    if (typeof x === "number") return x;
    const i = obrigatorios.indexOf(chave);
    return i >= 0 ? 10_000 + i : 20_000;
  };
  const chaves = Object.keys(props).sort((a, b) => posicao(a) - posicao(b) || a.localeCompare(b));
  return {
    valorDigitado: true,
    campos: chaves.map((chave) => campoDoSchema(chave, props[chave], obrigatorios.includes(chave))),
  };
}

/** O layout próprio, para os seis tipos de origem, ou o desenhado pelo schema do catálogo. */
export function configDoTipo(slug: string, schema?: SchemaCampos | null): ConfigTipo {
  return isTipoSolicitacao(slug) ? CONFIG_POR_TIPO[slug] : configDoSchema(schema);
}

export function camposVisiveis(config: ConfigTipo, valores: ValoresCampos): CampoSolicitacao[] {
  return config.campos.filter((c) => !c.visivel || c.visivel(valores));
}

/** "AAAA-MM-DDTHH:mm" do `datetime-local` → ISO completo, no fuso do navegador. */
function isoDoLocal(valor: string): string {
  const data = new Date(valor);
  return Number.isNaN(data.getTime()) ? valor : data.toISOString();
}

/** ISO completo → "AAAA-MM-DDTHH:mm" no fuso do navegador, para o `datetime-local`. */
function localDoIso(valor: string): string {
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return valor.slice(0, 16);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${data.getFullYear()}-${p(data.getMonth() + 1)}-${p(data.getDate())}T${p(data.getHours())}:${p(data.getMinutes())}`;
}

/**
 * Os erros que dá para apontar antes de enviar — os mesmos que o backend
 * devolveria. O resto (município inexistente, valor da diária não configurado)
 * chega no 400 e aparece no campo.
 */
export function validarCampos(
  tipo: string,
  config: ConfigTipo,
  valores: ValoresCampos,
): Record<string, string> {
  const erros: Record<string, string> = {};
  for (const campo of camposVisiveis(config, valores)) {
    const valor = (valores[campo.chave] ?? "").trim();
    if (!valor) {
      if (campo.obrigatorio) erros[campo.chave] = "Campo obrigatório.";
      continue;
    }
    if (campo.tipo === "cpf" && !isValidCpf(valor)) erros[campo.chave] = "CPF inválido.";
    if (campo.tipo === "inteiro" && !(/^\d+$/.test(valor) && Number(valor) > 0)) {
      erros[campo.chave] = "Informe um número inteiro maior que zero.";
    }
    if (campo.tipo === "numero") {
      const n = Number(valor.replace(",", "."));
      if (!Number.isFinite(n) || (campo.inteiro && !Number.isInteger(n))) {
        erros[campo.chave] = campo.inteiro ? "Informe um número inteiro." : "Informe um número.";
      } else if (campo.minimo !== undefined && n < campo.minimo) {
        erros[campo.chave] = campo.mensagem ?? `Deve ser maior ou igual a ${campo.minimo}.`;
      }
    }
  }
  if (tipo === "diaria" && valores.data_inicio && valores.data_fim && valores.data_fim < valores.data_inicio) {
    erros.data_fim = "Não pode ser anterior à data de ida.";
  }
  return erros;
}

/** Estado do formulário → `campos_json`. Campos ocultos e vazios ficam de fora. */
export function montarCamposJson(config: ConfigTipo, valores: ValoresCampos): Record<string, unknown> {
  const json: Record<string, unknown> = {};
  for (const campo of camposVisiveis(config, valores)) {
    const valor = (valores[campo.chave] ?? "").trim();
    if (!valor) continue;
    switch (campo.tipo) {
      case "booleano":
        json[campo.chave] = valor === SIM;
        break;
      case "inteiro":
      case "municipio":
        json[campo.chave] = Number(valor);
        break;
      case "numero":
        json[campo.chave] = Number(valor.replace(",", "."));
        break;
      case "dataHora":
        json[campo.chave] = campo.isoCompleto ? isoDoLocal(valor) : valor;
        break;
      case "cpf":
        json[campo.chave] = valor.replace(/\D/g, "");
        break;
      case "choice":
        // O select trabalha com texto; um enum numérico volta ao número que o schema espera.
        json[campo.chave] = campo.opcoes?.find((o) => o.value === valor)?.original ?? valor;
        break;
      default:
        json[campo.chave] = valor;
    }
  }
  return json;
}

/**
 * Uma linha que identifica a solicitação no cartão, pelos campos que a
 * distinguem. Num tipo do catálogo, os dois primeiros campos preenchidos.
 */
const FORMATO_DIARIAS = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

export function resumoSolicitacao(
  tipo: string,
  json: Record<string, unknown>,
  schema?: SchemaCampos | null,
): string {
  const t = (chave: string) => (json[chave] === undefined || json[chave] === null ? "" : String(json[chave]));
  const partes: string[] = (() => {
    switch (tipo) {
      case "diaria":
        // Com a meia diária (#358), a quantidade vem "2.5": sai "2,5", como na simulação.
        return [
          t("beneficiario_nome"),
          t("numero_diarias") && `${FORMATO_DIARIAS.format(Number(t("numero_diarias")))} diária(s)`,
        ];
      case "passagem":
        return [t("passageiro_nome"), t("aeroporto_origem") && `${t("aeroporto_origem")} → ${t("aeroporto_destino")}`];
      case "veiculo":
        return [t("destino_rota"), t("numero_passageiros") && `${t("numero_passageiros")} passageiro(s)`];
      case "grafico":
        return [t("quantidade") && `${t("quantidade")} unidade(s)`, t("prazo_entrega") && `entrega até ${t("prazo_entrega")}`];
      case "alimentacao":
        return [t("numero_pessoas") && `${t("numero_pessoas")} pessoa(s)`, t("local_entrega")];
      case "equipamento":
        return [t("quantidade") && `${t("quantidade")} × ${t("descricao_equipamento")}`];
      default:
        return configDoSchema(schema)
          .campos.filter((c) => c.tipo !== "booleano" && t(c.chave))
          .slice(0, 2)
          .map((c) => c.opcoes?.find((o) => o.value === t(c.chave))?.label ?? t(c.chave));
    }
  })();
  return partes.filter(Boolean).join(" · ");
}

/** `campos_json` de uma solicitação salva → estado do formulário, para editar. */
export function valoresDoCamposJson(config: ConfigTipo, json: Record<string, unknown>): ValoresCampos {
  const valores: ValoresCampos = {};
  for (const campo of config.campos) {
    const bruto = json[campo.chave];
    if (bruto === undefined || bruto === null) continue;
    if (campo.tipo === "booleano") valores[campo.chave] = bruto === true ? SIM : NAO;
    else if (campo.tipo === "cpf") valores[campo.chave] = formatCpfInput(String(bruto));
    // `datetime-local` só aceita "AAAA-MM-DDTHH:mm".
    else if (campo.tipo === "dataHora") {
      valores[campo.chave] = campo.isoCompleto ? localDoIso(String(bruto)) : String(bruto).slice(0, 16);
    }
    else valores[campo.chave] = String(bruto);
  }
  return valores;
}
