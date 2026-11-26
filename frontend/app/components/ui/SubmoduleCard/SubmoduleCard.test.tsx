import { render, screen } from "@testing-library/react";
import { Users } from "lucide-react";
import { describe, expect, it } from "vitest";
import { SubmoduleCard } from "./SubmoduleCard";

/** #467: descrição inteira e nenhum "—" solto no contador. */

const DESCRICAO = "Cadastro de famílias e Unidades Familiares de Produção Agropecuária (UFPA).";

function renderizar(count?: number | null) {
  render(
    <SubmoduleCard title="Famílias / UFPAs" description={DESCRICAO} Icon={Users} href="/sgp/ufpas/" count={count} testId="card" />,
  );
  return screen.getByTestId("card");
}

describe("SubmoduleCard (#467)", () => {
  it("mostra a descrição inteira, sem corte por reticências", () => {
    renderizar();
    const descricao = screen.getByText(DESCRICAO);
    expect(descricao.className).not.toMatch(/line-clamp|truncate/);
  });

  it("com a contagem, o número", () => {
    expect(renderizar(1234).textContent).toContain("1.234");
  });

  it("carregando (null): um marcador sem texto, nunca o \"—\"", () => {
    const card = renderizar(null);
    expect(screen.getByTestId("submodule-card-contador-carregando").getAttribute("aria-hidden")).toBe("true");
    expect(card.textContent).not.toContain("—");
  });

  it("sem contagem (omitida ou falhou): nada no lugar do número", () => {
    const card = renderizar(undefined);
    expect(screen.queryByTestId("submodule-card-contador-carregando")).toBeNull();
    expect(card.textContent).not.toContain("—");
  });
});
