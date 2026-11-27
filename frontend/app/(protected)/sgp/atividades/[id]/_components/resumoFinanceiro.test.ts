import { describe, expect, it } from "vitest";
import type { Demanda, SolicitacaoDemanda, StatusDemanda } from "@/app/lib/demandas";
import { resumoFinanceiro } from "./DemandasTab";

function demanda(status: StatusDemanda, rubricas: string[]) {
  return {
    status,
    solicitacoes: rubricas.map((rubrica_nome) => ({ rubrica_nome }) as SolicitacaoDemanda),
    valor_estimado_total: "1000.00",
    valor_autorizado_total: "900.00",
    valor_pago_total: "850.00",
  } as Pick<Demanda, "status" | "solicitacoes" | "valor_estimado_total" | "valor_autorizado_total" | "valor_pago_total">;
}

describe("resumoFinanceiro da aba Demandas (#464)", () => {
  it("rubricas sem repetição, na ordem das solicitações", () => {
    expect(resumoFinanceiro(demanda("rascunho", ["Diárias", "Combustível", "Diárias"])).rubricas).toEqual([
      "Diárias",
      "Combustível",
    ]);
  });

  it.each<[StatusDemanda, string | null, string | null]>([
    ["rascunho", null, null],
    ["submetida", null, null],
    ["pre_autorizada", null, null],
    ["autorizada", "900.00", null],
    ["em_atendimento", "900.00", null],
    ["concluida", "900.00", "850.00"],
    ["recusada", null, null],
    ["cancelada", null, null],
  ])("%s: autorizado %s, executado %s", (status, autorizado, executado) => {
    const r = resumoFinanceiro(demanda(status, ["Diárias"]));
    expect(r.estimado).toBe("1000.00");
    expect(r.autorizado).toBe(autorizado);
    expect(r.executado).toBe(executado);
  });
});
