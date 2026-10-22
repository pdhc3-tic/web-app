import { describe, expect, it } from "vitest";
import { ApiError } from "@/app/lib/api";
import type { Demanda, SolicitacaoDemanda } from "@/app/lib/demandas";
import { bloqueioDeRecursoExtra } from "@/app/lib/remanejamentos";

/**
 * Leitura do 400 da submissão para o atalho "Solicitar recurso extra" (#321),
 * que a tela de submissão da #295 vai chamar.
 */

function solicitacao(id: number, slug: string, nome: string): SolicitacaoDemanda {
  return { id, rubrica_slug: slug, rubrica_nome: nome } as SolicitacaoDemanda;
}

const demanda = {
  id: 47,
  solicitacoes: [
    solicitacao(10, "diarias", "Diárias"),
    solicitacao(11, "locacao-veiculo", "Locação de veículo"),
  ],
} as Demanda;

function erro400(raw: unknown): ApiError {
  return new ApiError(400, { code: "validation_error", message: "x" }, raw);
}

describe("bloqueioDeRecursoExtra", () => {
  it("lê o contrato do PR #343 e devolve a solicitação barrada pelo limite individual", () => {
    const erro = erro400({
      detail: "Limite individual insuficiente. Use a opção 'Solicitar recurso extra'.",
      code: "trava_individual",
      solicitacao_id: 11,
      solicitacoes_bloqueadas: {
        "11": {
          trava: "individual",
          motivo: "Limite individual insuficiente. Use a opção 'Solicitar recurso extra'.",
          acao_sugerida: "solicitar_recurso_extra",
        },
      },
    });

    expect(bloqueioDeRecursoExtra(erro, demanda)).toEqual({
      solicitacaoId: 11,
      rubrica: { slug: "locacao-veiculo", nome: "Locação de veículo" },
      motivo: "Limite individual insuficiente. Use a opção 'Solicitar recurso extra'.",
    });
  });

  it("aceita o contrato atual da main, só com `solicitacoes_bloqueadas`", () => {
    const erro = erro400({
      solicitacoes_bloqueadas: {
        "10": { trava: "individual", motivo: "Sem limite.", acao_sugerida: "solicitar_recurso_extra" },
      },
    });

    expect(bloqueioDeRecursoExtra(erro, demanda)?.rubrica.slug).toBe("diarias");
  });

  it("pula a trava territorial, que pede o Articulador e não recurso extra", () => {
    const erro = erro400({
      code: "trava_territorial",
      solicitacoes_bloqueadas: {
        "10": { trava: "territorial", motivo: "Pool esgotado.", acao_sugerida: "acionar_articulador" },
        "11": { trava: "individual", motivo: "Sem limite.", acao_sugerida: "solicitar_recurso_extra" },
      },
    });

    expect(bloqueioDeRecursoExtra(erro, demanda)?.solicitacaoId).toBe(11);
  });

  it("devolve null sem bloqueio individual, em outro status ou fora de ApiError", () => {
    const soTerritorial = erro400({
      solicitacoes_bloqueadas: {
        "10": { trava: "territorial", motivo: null, acao_sugerida: "acionar_articulador" },
      },
    });
    expect(bloqueioDeRecursoExtra(soTerritorial, demanda)).toBeNull();
    expect(bloqueioDeRecursoExtra(erro400({ solicitacoes: "vazia" }), demanda)).toBeNull();
    expect(
      bloqueioDeRecursoExtra(new ApiError(403, { code: "x", message: "x" }, {}), demanda),
    ).toBeNull();
    expect(bloqueioDeRecursoExtra(new Error("rede"), demanda)).toBeNull();
  });
});
