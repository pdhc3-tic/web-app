import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Pagination } from "./Pagination";

/** #467: o seletor tem nome acessível mesmo sem o rótulo visível, e os controles quebram linha. */

function renderizar() {
  const onLimitChange = vi.fn();
  render(
    <Pagination
      count={42}
      offset={20}
      limit={20}
      onOffsetChange={vi.fn()}
      onLimitChange={onLimitChange}
      pageSizes={[20, 50]}
      itemNoun={{ one: "remanejamento", other: "remanejamentos" }}
    />,
  );
  return onLimitChange;
}

describe("Pagination (#467)", () => {
  it("o seletor de tamanho tem nome acessível", () => {
    const onLimitChange = renderizar();
    fireEvent.change(screen.getByRole("combobox", { name: "Itens por página" }), { target: { value: "50" } });
    expect(onLimitChange).toHaveBeenCalledWith(50);
  });

  it("os controles podem quebrar linha em tela estreita", () => {
    renderizar();
    expect(screen.getByTestId("paginacao-controles").className).toContain("flex-wrap");
    expect(screen.getByText("remanejamentos", { exact: false }).textContent).toContain("21–40 de 42 remanejamentos");
  });
});

describe("Pagination carregando (#448)", () => {
  it("na primeira carga, \"Carregando…\" no lugar do \"0–0 de 0\"", () => {
    render(
      <Pagination
        count={0}
        offset={0}
        limit={25}
        onOffsetChange={vi.fn()}
        onLimitChange={vi.fn()}
        itemNoun={{ one: "UFPA", other: "UFPAs" }}
        carregando
      />,
    );
    expect(screen.getByRole("status").textContent).toBe("Carregando UFPAs…");
    expect(screen.queryByText(/0–0/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Próxima página" })).toBeNull();
  });
});
