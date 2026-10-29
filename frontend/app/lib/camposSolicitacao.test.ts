import { describe, expect, it } from "vitest";
import {
  camposVisiveis,
  montarCamposJson,
  resumoSolicitacao,
  validarCampos,
  valoresDoCamposJson,
} from "@/app/lib/camposSolicitacao";
import { ApiError } from "@/app/lib/api";
import {
  COTACOES_CONFERINDO,
  COTACOES_SEM_DOCUMENTOS,
  bloqueiosDaSubmissao,
  pendenciaDeCotacoes,
} from "@/app/lib/solicitacoes";

const chaves = (tipo: Parameters<typeof camposVisiveis>[0], valores = {}) =>
  camposVisiveis(tipo, valores).map((c) => c.chave);

describe("camposVisiveis", () => {
  it("passagem: a volta só aparece com ida e volta = Sim", () => {
    expect(chaves("passagem")).not.toContain("data_hora_volta");
    expect(chaves("passagem", { ida_e_volta: "sim" })).toContain("data_hora_volta");
    expect(chaves("passagem", { ida_e_volta: "nao" })).not.toContain("data_hora_volta");
  });

  it("passagem: a classe executiva pede justificativa", () => {
    expect(chaves("passagem", { classe: "economica" })).not.toContain("justificativa_executiva");
    expect(chaves("passagem", { classe: "executiva" })).toContain("justificativa_executiva");
  });
});

describe("validarCampos", () => {
  it("aponta os obrigatórios visíveis, e só eles", () => {
    const erros = validarCampos("passagem", {});
    expect(erros.passageiro_nome).toBe("Campo obrigatório.");
    expect(erros).not.toHaveProperty("data_hora_volta");
    expect(validarCampos("passagem", { ida_e_volta: "sim" })).toHaveProperty("data_hora_volta");
  });

  it("confere CPF, inteiro positivo e a ordem das datas da diária", () => {
    const erros = validarCampos("diaria", {
      beneficiario_cpf: "111.111.111-11",
      data_inicio: "2026-11-12",
      data_fim: "2026-11-10",
    });
    expect(erros.beneficiario_cpf).toBe("CPF inválido.");
    expect(erros.data_fim).toBe("Não pode ser anterior à data de ida.");
    expect(validarCampos("veiculo", { estimativa_km: "0" }).estimativa_km).toMatch(/maior que zero/);
  });

  it("campos opcionais vazios não são erro", () => {
    expect(validarCampos("alimentacao", { tipo_refeicao: "almoco", numero_pessoas: "40", data_horario_servico: "2026-11-10T12:00" })).toEqual({});
  });
});

describe("montarCamposJson e valoresDoCamposJson", () => {
  it("converte os tipos e deixa de fora o que está oculto ou vazio", () => {
    const json = montarCamposJson("passagem", {
      passageiro_cpf: "529.982.247-25",
      ida_e_volta: "nao",
      data_hora_volta: "2026-11-21T18:00",
      bagagem_despachada: "sim",
      aeroporto_origem: "  NAT ",
      classe: "",
    });
    expect(json).toEqual({
      passageiro_cpf: "52998224725",
      ida_e_volta: false,
      bagagem_despachada: true,
      aeroporto_origem: "NAT",
    });
    expect(montarCamposJson("diaria", { municipio_destino_id: "12" })).toEqual({ municipio_destino_id: 12 });
  });

  it("volta ao formulário: booleano, CPF mascarado e data e hora no formato do input", () => {
    expect(
      valoresDoCamposJson("passagem", {
        ida_e_volta: true,
        passageiro_cpf: "52998224725",
        data_hora_ida: "2026-11-20T08:00:00",
      }),
    ).toEqual({ ida_e_volta: "sim", passageiro_cpf: "529.982.247-25", data_hora_ida: "2026-11-20T08:00" });
  });
});

describe("resumoSolicitacao", () => {
  it("identifica a solicitação pelos campos que a distinguem", () => {
    expect(resumoSolicitacao("diaria", { beneficiario_nome: "Paulo", numero_diarias: 2 })).toBe("Paulo · 2 diária(s)");
    expect(resumoSolicitacao("equipamento", { quantidade: 5, descricao_equipamento: "Kit" })).toBe("5 × Kit");
    expect(resumoSolicitacao("desconhecido", {})).toBe("");
  });
});

describe("pendenciaDeCotacoes", () => {
  const comEquipamento = { solicitacoes: [{ tipo: "equipamento" }] } as Parameters<typeof pendenciaDeCotacoes>[0];
  const cotacao = (fornecedor: string) => ({ tipo: "cotacao", fornecedor });

  it("sem equipamento, não exige cotação", () => {
    expect(pendenciaDeCotacoes({ solicitacoes: [] }, [])).toBeNull();
  });

  it("exige 3 cotações de fornecedores distintos", () => {
    expect(pendenciaDeCotacoes(comEquipamento, [cotacao("A"), cotacao("B")])).toMatch(/há 2/);
    expect(pendenciaDeCotacoes(comEquipamento, [cotacao("A"), cotacao("A"), cotacao("B")])).toMatch(/distintos/);
    expect(pendenciaDeCotacoes(comEquipamento, [cotacao("A"), cotacao("B"), cotacao("C")])).toBeNull();
  });

  it("com equipamento, bloqueia enquanto os documentos não carregaram e se a consulta falhou", () => {
    expect(pendenciaDeCotacoes(comEquipamento, undefined)).toBe(COTACOES_CONFERINDO);
    expect(pendenciaDeCotacoes(comEquipamento, undefined, true)).toBe(COTACOES_SEM_DOCUMENTOS);
  });

  it("sem equipamento, não espera os documentos", () => {
    expect(pendenciaDeCotacoes({ solicitacoes: [] }, undefined, true)).toBeNull();
  });
});

describe("bloqueiosDaSubmissao", () => {
  const individual = {
    code: "INSUFFICIENT_BALANCE",
    trava: "individual",
    rubrica: "passagens-aereas",
    disponivel: "5000.00",
    solicitado: "6000.00",
    acao_sugerida: "solicitar_recurso_extra",
    detail: "Limite individual insuficiente.",
  } as const;
  const territorial = {
    ...individual,
    trava: "territorial",
    rubrica: "locacao-veiculo",
    disponivel: "0.00",
    solicitado: "700.00",
    acao_sugerida: "acionar_articulador",
    detail: "Saldo territorial zerado nesta rubrica.",
  } as const;

  it("lê todas as solicitações barradas do INSUFFICIENT_BALANCE da submissão", () => {
    const raw = {
      ...individual,
      solicitacao_id: 11,
      solicitacoes_bloqueadas: { "11": individual, "12": territorial },
    };
    const erro = new ApiError(400, { code: "INSUFFICIENT_BALANCE", message: "x" }, raw);
    expect(bloqueiosDaSubmissao(erro)).toEqual({ 11: individual, 12: territorial });
  });

  it("outro 400, ou outro erro, não é bloqueio de saldo", () => {
    expect(bloqueiosDaSubmissao(new ApiError(400, { code: "x", message: "x" }, { documentos: "faltam" }))).toBeNull();
    // Sem o code, nem o formato antigo (motivo em texto) vale como bloqueio.
    const semCode = { solicitacoes_bloqueadas: { "11": { trava: "individual", motivo: "Sem limite." } } };
    expect(bloqueiosDaSubmissao(new ApiError(400, { code: "x", message: "x" }, semCode))).toBeNull();
    expect(bloqueiosDaSubmissao(new Error("rede"))).toBeNull();
  });
});
