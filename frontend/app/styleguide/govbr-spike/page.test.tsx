import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import GovbrSpikePage from "./page";
import { GOVBR_DS_CSS } from "./documento";

describe("GovbrSpikePage (#397)", () => {
  it("isola os componentes e as folhas de estilo em um iframe", () => {
    const linksAntes = document.head.querySelectorAll("link").length;
    render(<GovbrSpikePage />);
    const frame = screen.getByTitle("Demonstração isolada de GOV.BR DS e Tailwind prefixado");
    const documento = new DOMParser().parseFromString(frame.getAttribute("srcdoc")!, "text/html");
    const folhas = [...documento.querySelectorAll('link[rel="stylesheet"]')].map((l) => l.getAttribute("href"));
    // Ordem do guia do GOV.BR DS: fonte, ícones, core; o Tailwind prefixado por último.
    expect(folhas).toEqual([
      expect.stringContaining("/fonts/rawline/"),
      expect.stringContaining("font-awesome/5."),
      GOVBR_DS_CSS,
      "/govbr-spike.css",
    ]);
    expect(documento.querySelector("button.br-button.primary")).not.toBeNull();
    expect(documento.querySelector('[data-testid="govbr-spike-grid-tw"]')?.classList.contains("tw:grid")).toBe(true);
    expect(document.head.querySelectorAll("link").length).toBe(linksAntes);
  });

  it("o GOV.BR DS fica numa versão estável e fixa", () => {
    // A 4.3.0 não existe (a série 4 só tem 4.0.0-next); o core respondia 404.
    expect(GOVBR_DS_CSS).toMatch(/@govbr-ds\/core@\d+\.\d+\.\d+\/dist\/core\.min\.css$/);
  });
});
