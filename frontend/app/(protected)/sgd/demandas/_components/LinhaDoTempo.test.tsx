import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Demanda } from "@/app/lib/demandas";
import { LinhaDoTempo } from "./DemandaPainel";

const demanda = {
  status: "concluida",
  status_display: "Concluída",
  criado_em: "2026-11-01T10:00:00-03:00",
  etapas: [],
  solicitacoes: [{ id: 42, tipo_display: "Passagem" }],
} as unknown as Demanda;

describe("LinhaDoTempo (#360)", () => {
  it("mostra o risco de glosa devolvido pelo backend", () => {
    render(
      <LinhaDoTempo
        demanda={{
          ...demanda,
          glosas: [
            {
              id: 7,
              demand_request_id: 42,
              valor_autorizado: "1200.00",
              valor_pago: "1400.00",
              excedente: "200.00",
              criado_em: "2026-11-01T10:30:00-03:00",
            },
          ],
        }}
      />,
    );
    const glosa = screen.getByTestId("glosa-7");
    expect(glosa.textContent).toContain("200,00 acima do autorizado");
    expect(glosa.textContent).toContain("Passagem");
  });

  it("sem o campo, não mostra registro de glosa", () => {
    render(<LinhaDoTempo demanda={demanda} />);
    expect(screen.queryByTestId("glosa-7")).toBeNull();
    expect(screen.getByTestId("painel-timeline").textContent).toContain("Status atual");
  });
});
