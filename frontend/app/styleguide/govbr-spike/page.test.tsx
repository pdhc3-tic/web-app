import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import GovbrSpikePage from "./page";

describe("GovbrSpikePage (#397)", () => {
  it("injeta o CSS do GOV.BR DS ao montar e remove do head ao desmontar", () => {
    const { unmount } = render(<GovbrSpikePage />);
    const link = document.head.querySelector(
      'link[rel="stylesheet"][href*="@govbr-ds/core"]',
    );
    expect(link).not.toBeNull();

    unmount();
    expect(
      document.head.querySelector('link[rel="stylesheet"][href*="@govbr-ds/core"]'),
    ).toBeNull();
  });

  it("renderiza componentes br-* do GOV.BR DS convivendo com layout tw-* do Tailwind", () => {
    render(<GovbrSpikePage />);

    const botaoPrimario = screen.getByTestId("govbr-botao-primario");
    expect(botaoPrimario.className).toContain("br-button primary");

    const inputNome = screen.getByTestId("govbr-input-nome");
    expect(inputNome.closest("label")?.className).toContain("br-input");

    const mensagem = screen.getByTestId("govbr-mensagem");
    expect(mensagem.className).toContain("br-message warning");

    const blocoTailwind = screen.getByTestId("govbr-spike-bloco-tailwind");
    expect(blocoTailwind.className).toContain("tw-p-6");

    const gridTw = screen.getByTestId("govbr-spike-grid-tw");
    expect(gridTw.className).toContain("tw-grid");
    expect(gridTw.className).toContain("tw-gap-4");

    const conviv = screen.getByTestId("govbr-spike-conviv");
    expect(conviv.className).toContain("tw-p-6");
    expect(conviv.querySelector(".tw-grid.tw-gap-4")).not.toBeNull();
    expect(conviv.querySelector("button.br-button.primary")).not.toBeNull();
  });
});
