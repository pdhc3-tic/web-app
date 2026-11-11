import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import GovbrSpikePage from "./page";

 describe("GovbrSpikePage (#397)", () => {
  it("isola os componentes e as folhas de estilo em um iframe", () => {
    const linksAntes = document.head.querySelectorAll("link").length;
    render(<GovbrSpikePage />);
    const frame = screen.getByTitle("Demonstração isolada de GOV.BR DS e Tailwind prefixado");
    const documento = new DOMParser().parseFromString(frame.getAttribute("srcdoc")!, "text/html");
    expect(documento.querySelector('link[href*="@govbr-ds/core"]')).not.toBeNull();
    expect(documento.querySelector('link[href="/govbr-spike.css"]')).not.toBeNull();
    expect(documento.querySelector("button.br-button.primary")).not.toBeNull();
    expect(documento.querySelector('[data-testid="govbr-spike-grid-tw"]')?.classList.contains("tw:grid")).toBe(true);
    expect(document.head.querySelectorAll("link").length).toBe(linksAntes);
  });

  it("o CSS compilado contém prefixo v4 e variantes, sem o reset preflight", () => {
    const css = readFileSync(path.resolve(__dirname, "../../../public/govbr-spike.css"), "utf8");
    expect(css).toContain(".tw\\:grid");
    expect(css).toContain(".tw\\:sm\\:grid-cols-2");
    expect(css).toContain("--tw-spacing");
    expect(css).not.toContain("box-sizing: border-box");
    expect(css).not.toContain("::file-selector-button");
  });
});
