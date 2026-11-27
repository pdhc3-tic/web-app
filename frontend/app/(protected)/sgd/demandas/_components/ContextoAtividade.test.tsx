import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AtividadeElegivelDetalhe } from "@/app/lib/demandas";
import { ContextoAtividade } from "./ContextoAtividade";

vi.mock("@/app/providers/SgpChoicesProvider", () => ({
  useRotuloChoice: () => (valor: string) => valor,
}));

const atividade = {
  titulo: "Oficina",
  status: "agendado",
  data_inicio: "2026-12-01T10:00:00-03:00",
  territorio: null,
  municipio: { id: 1, nome: "Caicó" },
  tecnico_responsavel: { id: 1, nome: "Técnico" },
  acao: {
    id: 1,
    numero: "1.1.1",
    descricao: "Realizar oficinas",
    meta: { id: 10, numero: 1, titulo: "Organização produtiva" },
    submeta: { id: 20, numero: "1.1", titulo: "Formação" },
    indicador: { id: 2, codigo: "IND-OFI", nome: "Oficina", unidade_medida: "evento" },
  },
} as unknown as AtividadeElegivelDetalhe;

function valorDe(rotulo: string) {
  return screen.getByText(rotulo, { selector: "dt" }).nextElementSibling?.textContent;
}

describe("ContextoAtividade (#294, #446)", () => {
  it("sem território, diz “Não disponível” em vez de inventar", () => {
    render(<ContextoAtividade atividade={atividade} />);
    expect(valorDe("Território")).toContain("Não disponível");
  });

  it("mostra a cadeia do Plano de Trabalho no formato da ficha e do painel da demanda", () => {
    render(<ContextoAtividade atividade={atividade} />);
    expect(valorDe("Ação")).toBe("1.1.1 — Realizar oficinas");
    expect(valorDe("Submeta")).toBe("1.1 — Formação");
    expect(valorDe("Meta")).toBe("Meta 1 — Organização produtiva");
    expect(valorDe("Indicador")).toBe("IND-OFI — Oficina (unidade: evento)");
  });
});
