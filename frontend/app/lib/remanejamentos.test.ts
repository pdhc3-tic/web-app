import { describe, expect, it } from "vitest";
import { ApiError } from "@/app/lib/api";
import type { Demanda, SolicitacaoDemanda } from "@/app/lib/demandas";
import { bloqueioDeRecursoExtra } from "@/app/lib/remanejamentos";
import type { ErroSaldoInsuficiente } from "@/app/lib/solicitacoes";

/**
 * Leitura do 400 `INSUFFICIENT_BALANCE` da submissão para o atalho
 * "Solicitar recurso extra" (#321, #359).
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

function bloqueio(trava: "individual" | "territorial", extra: Partial<ErroSaldoInsuficiente> = {}): ErroSaldoInsuficiente {
  return {
    code: "INSUFFICIENT_BALANCE",
    trava,
    rubrica: "locacao-veiculo",
    disponivel: "1000.00",
    solicitado: "1200.00",
    acao_sugerida: trava === "individual" ? "solicitar_recurso_extra" : "acionar_articulador",
    detail: "Texto do backend.",
    ...extra,
  };
}

function erro400(bloqueadas: Record<string, ErroSaldoInsuficiente>): ApiError {
  const [id, primeiro] = Object.entries(bloqueadas)[0];
  return new ApiError(
    400,
    { code: "INSUFFICIENT_BALANCE", message: "x" },
    { ...primeiro, solicitacao_id: Number(id), solicitacoes_bloqueadas: bloqueadas },
  );
}

describe("bloqueioDeRecursoExtra", () => {
  it("devolve a solicitação barrada pelo limite individual com o disponível e o solicitado", () => {
    expect(bloqueioDeRecursoExtra(erro400({ "11": bloqueio("individual") }), demanda)).toEqual({
      solicitacaoId: 11,
      rubrica: { slug: "locacao-veiculo", nome: "Locação de veículo" },
      disponivel: "1000.00",
      solicitado: "1200.00",
      valorFaltante: null,
    });
  });

  it("leva o valor que falta na rubrica quando o backend o envia", () => {
    const erro = erro400({ "11": bloqueio("individual", { valor_faltante: "200.00" }) });
    expect(bloqueioDeRecursoExtra(erro, demanda)?.valorFaltante).toBe("200.00");
  });

  it("pula a trava territorial, que pede o Articulador e não recurso extra", () => {
    const erro = erro400({ "10": bloqueio("territorial"), "11": bloqueio("individual") });
    expect(bloqueioDeRecursoExtra(erro, demanda)?.solicitacaoId).toBe(11);
  });

  it("devolve null sem bloqueio individual, em outro 400 ou fora de ApiError", () => {
    expect(bloqueioDeRecursoExtra(erro400({ "10": bloqueio("territorial") }), demanda)).toBeNull();
    expect(
      bloqueioDeRecursoExtra(new ApiError(400, { code: "x", message: "x" }, { solicitacoes: "vazia" }), demanda),
    ).toBeNull();
    expect(
      bloqueioDeRecursoExtra(new ApiError(403, { code: "x", message: "x" }, {}), demanda),
    ).toBeNull();
    expect(bloqueioDeRecursoExtra(new Error("rede"), demanda)).toBeNull();
  });
});
