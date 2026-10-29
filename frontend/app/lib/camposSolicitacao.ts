import type { ChaveChoice } from "@/app/lib/choices";
import { formatCpfInput, isValidCpf } from "@/app/lib/format";

/**
 * SGD — campos de cada tipo de solicitação de recurso (#295, SGD §3.1 a §3.6).
 *
 * Espelha os validadores de `apps/sgd/services/demand_request.py`: as chaves são
 * as do `campos_json`, e obrigatório/condicional segue a mesma regra. As opções
 * dos selects vêm do `/api/v1/choices/` (`choice`), sem lista no front.
 *
 * É o layout por tipo que a SGD-REF-FE-07 (#365) mantém como override quando o
 * formulário passar a ser guiado pelo catálogo de tipos do backend.
 */

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
  | "municipio";

/** O estado do formulário: tudo string, como os inputs entregam. */
export type ValoresCampos = Record<string, string>;

export type CampoSolicitacao = {
  chave: string;
  rotulo: string;
  tipo: TipoCampo;
  /** Para `choice`: a lista do `/choices/`. */
  choice?: ChaveChoice;
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

export function camposVisiveis(tipo: TipoSolicitacao, valores: ValoresCampos): CampoSolicitacao[] {
  return CONFIG_POR_TIPO[tipo].campos.filter((c) => !c.visivel || c.visivel(valores));
}

/**
 * Os erros que dá para apontar antes de enviar — os mesmos que o backend
 * devolveria. O resto (município inexistente, valor da diária não configurado)
 * chega no 400 e aparece no campo.
 */
export function validarCampos(tipo: TipoSolicitacao, valores: ValoresCampos): Record<string, string> {
  const erros: Record<string, string> = {};
  for (const campo of camposVisiveis(tipo, valores)) {
    const valor = (valores[campo.chave] ?? "").trim();
    if (!valor) {
      if (campo.obrigatorio) erros[campo.chave] = "Campo obrigatório.";
      continue;
    }
    if (campo.tipo === "cpf" && !isValidCpf(valor)) erros[campo.chave] = "CPF inválido.";
    if (campo.tipo === "inteiro" && !(/^\d+$/.test(valor) && Number(valor) > 0)) {
      erros[campo.chave] = "Informe um número inteiro maior que zero.";
    }
  }
  if (tipo === "diaria" && valores.data_inicio && valores.data_fim && valores.data_fim < valores.data_inicio) {
    erros.data_fim = "Não pode ser anterior à data de ida.";
  }
  return erros;
}

/** Estado do formulário → `campos_json`. Campos ocultos e vazios ficam de fora. */
export function montarCamposJson(tipo: TipoSolicitacao, valores: ValoresCampos): Record<string, unknown> {
  const json: Record<string, unknown> = {};
  for (const campo of camposVisiveis(tipo, valores)) {
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
      case "cpf":
        json[campo.chave] = valor.replace(/\D/g, "");
        break;
      default:
        json[campo.chave] = valor;
    }
  }
  return json;
}

/** Uma linha que identifica a solicitação no cartão, pelos campos que a distinguem. */
export function resumoSolicitacao(tipo: string, json: Record<string, unknown>): string {
  const t = (chave: string) => (json[chave] === undefined || json[chave] === null ? "" : String(json[chave]));
  const partes: string[] = (() => {
    switch (tipo) {
      case "diaria":
        return [t("beneficiario_nome"), t("numero_diarias") && `${t("numero_diarias")} diária(s)`];
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
        return [];
    }
  })();
  return partes.filter(Boolean).join(" · ");
}

/** `campos_json` de uma solicitação salva → estado do formulário, para editar. */
export function valoresDoCamposJson(tipo: TipoSolicitacao, json: Record<string, unknown>): ValoresCampos {
  const valores: ValoresCampos = {};
  for (const campo of CONFIG_POR_TIPO[tipo].campos) {
    const bruto = json[campo.chave];
    if (bruto === undefined || bruto === null) continue;
    if (campo.tipo === "booleano") valores[campo.chave] = bruto === true ? SIM : NAO;
    else if (campo.tipo === "cpf") valores[campo.chave] = formatCpfInput(String(bruto));
    // `datetime-local` só aceita "AAAA-MM-DDTHH:mm".
    else if (campo.tipo === "dataHora") valores[campo.chave] = String(bruto).slice(0, 16);
    else valores[campo.chave] = String(bruto);
  }
  return valores;
}
