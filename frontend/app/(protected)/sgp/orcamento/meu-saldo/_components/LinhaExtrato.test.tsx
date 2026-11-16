import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { LinhaDoExtrato } from "@/app/lib/meuSaldo";
import { LinhaExtrato } from "./ExtratoSlideOver";

const reserva: LinhaDoExtrato = {
  id: 9,
  tipo: "reserva",
  valor: "700.00",
  efeito: "-700.00",
  saldo_anterior: "1000.00",
  saldo_posterior: "300.00",
  demanda_id: "321",
  justificativa: "",
  criado_em: "2026-11-10T14:00:00-03:00",
  periodo_inicio: "2026-10-01",
  periodo_fim: "2026-12-31",
};

/** Texto do elemento com o espaço não separável do `Intl` trocado por espaço comum. */
const texto = (testId: string) => screen.getByTestId(testId).textContent?.replace(/ /g, " ");

function renderLinha(linha: Partial<LinhaDoExtrato> = {}) {
  render(
    <table>
      <tbody>
        <LinhaExtrato linha={{ ...reserva, ...linha }} />
      </tbody>
    </table>,
  );
}

describe("LinhaExtrato (#401)", () => {
  it("reserva: tipo, link da demanda, valor com o sinal do efeito e saldo depois", () => {
    renderLinha();
    expect(texto("extrato-tipo")).toBe("Reserva");
    const link = screen.getByTestId("extrato-demanda");
    expect(link.getAttribute("href")).toBe("/sgd/demandas?demanda=321");
    expect(link.textContent).toBe("#321");
    expect(texto("extrato-valor")).toBe("−R$ 700,00");
    expect(texto("extrato-saldo-depois")).toBe("R$ 300,00");
  });

  it("liberação devolve: sinal positivo, sem demanda vira travessão", () => {
    renderLinha({ tipo: "liberacao", efeito: "700.00", demanda_id: null, justificativa: "Demanda cancelada." });
    expect(texto("extrato-tipo")).toBe("Liberação");
    expect(texto("extrato-valor")).toBe("+R$ 700,00");
    expect(screen.queryByTestId("extrato-demanda")).toBeNull();
    expect(screen.getByText("Demanda cancelada.")).toBeTruthy();
  });

  it("o sinal vem do efeito, não do tipo: execução não mexe no disponível", () => {
    renderLinha({ tipo: "execucao", efeito: "0.00" });
    expect(texto("extrato-valor")).toBe("R$ 0,00");
  });
});
