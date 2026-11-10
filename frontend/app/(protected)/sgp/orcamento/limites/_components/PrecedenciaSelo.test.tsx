import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PrecedenciaSelo } from "./PrecedenciaSelo";

describe("PrecedenciaSelo (#400)", () => {
  it("linha individual nascida do padrão: herdado do perfil", () => {
    render(<PrecedenciaSelo limite={{ escopo: "individual", herdado: true }} />);
    const selo = screen.getByTestId("limite-precedencia");
    expect(selo.textContent).toBe("Herdado do perfil");
    expect(selo.dataset.precedencia).toBe("herdado");
  });

  it("linha individual criada pela UGP: sobrescrito", () => {
    render(<PrecedenciaSelo limite={{ escopo: "individual", herdado: false }} />);
    const selo = screen.getByTestId("limite-precedencia");
    expect(selo.textContent).toBe("Sobrescrito");
    expect(selo.dataset.precedencia).toBe("sobrescrito");
  });

  it("o próprio padrão do perfil", () => {
    render(<PrecedenciaSelo limite={{ escopo: "perfil", herdado: false }} />);
    expect(screen.getByTestId("limite-precedencia").textContent).toBe("Padrão do perfil");
  });
});
