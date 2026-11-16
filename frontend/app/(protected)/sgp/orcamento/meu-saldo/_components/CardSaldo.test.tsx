import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SaldoDaRubrica } from "@/app/lib/meuSaldo";
import { CardSaldo } from "./CardSaldo";

const base: SaldoDaRubrica = {
  rubrica: "diarias",
  rubrica_nome: "Diárias",
  rubrica_ativa: true,
  limite: "5000.00",
  comprometido: "1200.00",
  executado: "300.00",
  disponivel: "3500.00",
  semaforo: "verde",
  periodo_inicio: "2026-10-01",
  periodo_fim: "2026-12-31",
  dias_restantes: 51,
  acumula_saldo: false,
  saldo_territorio: "7000.00",
};

/** Texto do elemento com o espaço não separável do `Intl` trocado por espaço comum. */
const texto = (testId: string) => screen.getByTestId(testId).textContent?.replace(/ /g, " ");

function renderCard(saldo: Partial<SaldoDaRubrica> = {}) {
  const onExtrato = vi.fn();
  const onRecursoExtra = vi.fn();
  render(<CardSaldo saldo={{ ...base, ...saldo }} onExtrato={onExtrato} onRecursoExtra={onRecursoExtra} />);
  return { onExtrato, onRecursoExtra };
}

describe("CardSaldo (#401)", () => {
  it("mostra limite, comprometido, executado, disponível, período e o pool", () => {
    renderCard();
    const card = texto("meu-saldo-card-diarias");
    expect(card).toContain("Diárias");
    expect(texto("meu-saldo-disponivel")).toContain("R$ 3.500,00");
    expect(texto("meu-saldo-comprometido")).toContain("R$ 1.200,00");
    expect(card).toContain("R$ 5.000,00");
    expect(card).toContain("R$ 300,00");
    expect(card).toContain("Período até 31/12/2026 (51 dias)");
    expect(card).toContain("Pool do território: R$ 7.000,00");
    expect(card).toContain("Com folga");
  });

  it("verde não oferece recurso extra", () => {
    renderCard();
    expect(screen.queryByTestId("meu-saldo-recurso-extra")).toBeNull();
  });

  it.each(["amarelo", "vermelho"] as const)("%s oferece o atalho do recurso extra", (semaforo) => {
    const { onRecursoExtra } = renderCard({ semaforo });
    fireEvent.click(screen.getByTestId("meu-saldo-recurso-extra"));
    expect(onRecursoExtra).toHaveBeenCalledOnce();
  });

  it("rubrica inativa avisa e não oferece recurso extra", () => {
    renderCard({ rubrica_ativa: false, semaforo: "vermelho" });
    expect(texto("meu-saldo-card-diarias")).toContain("Rubrica inativa");
    expect(screen.queryByTestId("meu-saldo-recurso-extra")).toBeNull();
  });

  it("disponível negativo fica em vermelho, sem pool não há nota, e o extrato abre pelo botão", () => {
    const { onExtrato } = renderCard({ disponivel: "-200.00", semaforo: "vermelho", saldo_territorio: null });
    expect(screen.getByTestId("meu-saldo-disponivel").querySelector("dd")?.className).toContain("text-error-text");
    expect(texto("meu-saldo-card-diarias")).not.toContain("Pool do território");
    fireEvent.click(screen.getByTestId("meu-saldo-ver-extrato"));
    expect(onExtrato).toHaveBeenCalledOnce();
  });
});
