import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AtividadeDetail } from "@/app/lib/atividades";
import { ContextoAtividade } from "./ContextoAtividade";

vi.mock("@/app/providers/SgpChoicesProvider", () => ({
  useRotuloChoice: () => (valor: string) => valor,
}));

describe("ContextoAtividade (#294)", () => {
  it("sem território e sem a cadeia do Plano de Trabalho, diz “Não disponível” em vez de inventar", () => {
    const atividade = {
      titulo: "Oficina",
      status: "agendado",
      data_inicio: "2026-12-01T10:00:00-03:00",
      municipio: { id: 1, nome: "Caicó" },
      tecnico_responsavel: { id: 1, nome: "Técnico" },
      acao: { id: 1, numero: "1.1.1", descricao: "Ação" },
    } as unknown as AtividadeDetail;

    render(<ContextoAtividade atividade={atividade} />);

    for (const rotulo of ["Território", "Submeta", "Meta", "Indicador"]) {
      const termo = screen.getByText(rotulo, { selector: "dt" });
      expect(termo.nextElementSibling?.textContent).toContain("Não disponível");
    }
  });
});
