import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Demanda, RiscoGlosa } from "@/app/lib/demandas";
import { LinhaDoTempo } from "./DemandaPainel";

const demanda = {
  status: "concluida",
  status_display: "Concluída",
  criado_em: "2026-11-01T10:00:00-03:00",
  etapas: [],
  solicitacoes: [{ id: 42, tipo_display: "Passagem" }],
} as unknown as Demanda;

const pagoAcima: RiscoGlosa = {
  id: 7,
  tipo: "pago_acima_autorizado",
  severidade: "media",
  valor_exposto: "200.00",
  activity_id: 3,
  demanda_id: 1,
  demand_request_id: 42,
  valor_autorizado: "1200.00",
  valor_pago: "1400.00",
  criado_em: "2026-11-01T10:30:00-03:00",
  resolvido_em: null,
};

describe("LinhaDoTempo — riscos de glosa (#360)", () => {
  it("pago acima do autorizado: o valor exposto, a solicitação, os valores e a severidade", () => {
    render(<LinhaDoTempo demanda={demanda} glosas={[pagoAcima]} />);
    const glosa = screen.getByTestId("glosa-7");
    expect(glosa.textContent).toContain("200,00 acima do autorizado");
    expect(glosa.textContent).toContain("severidade média");
    expect(glosa.textContent).toContain("Passagem");
    expect(glosa.textContent).toContain("pago R$ 1.400,00, autorizado R$ 1.200,00");
    expect(glosa.textContent).not.toContain("resolvido");
  });

  it("demanda sem evidência mostra só o valor exposto, e o resolvido aparece com a data", () => {
    render(
      <LinhaDoTempo
        demanda={demanda}
        glosas={[
          {
            ...pagoAcima,
            id: 8,
            tipo: "demanda_sem_evidencia",
            severidade: "alta",
            valor_exposto: "900.00",
            demand_request_id: null,
            valor_autorizado: null,
            valor_pago: null,
            resolvido_em: "2026-11-02T09:00:00-03:00",
          },
        ]}
      />,
    );
    const glosa = screen.getByTestId("glosa-8");
    expect(glosa.textContent).toContain("demanda executada sem evidência");
    expect(glosa.textContent).toContain("severidade alta");
    expect(glosa.textContent).toContain("valor exposto R$ 900,00");
    expect(glosa.textContent).toContain("resolvido em");
    expect(glosa.textContent).not.toContain("pago");
  });

  it("sem riscos (ou para quem não consulta a rota), a linha do tempo segue sem glosa", () => {
    render(<LinhaDoTempo demanda={demanda} />);
    expect(screen.queryByTestId("glosa-7")).toBeNull();
    expect(screen.queryByTestId("glosas-erro")).toBeNull();
    expect(screen.getByTestId("painel-timeline").textContent).toContain("Status atual");
  });

  it("falha na consulta vira um aviso discreto, sem esconder o resto", () => {
    render(<LinhaDoTempo demanda={demanda} glosasFalharam />);
    expect(screen.getByTestId("glosas-erro").textContent).toContain("Não foi possível carregar os riscos de glosa");
    expect(screen.getByTestId("painel-timeline").textContent).toContain("Status atual");
  });
});
