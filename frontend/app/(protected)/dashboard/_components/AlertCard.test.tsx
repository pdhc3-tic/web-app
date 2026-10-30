import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AlertCard } from "./AlertCard";

/**
 * Card de alerta do dashboard (#236). O estado zero não tem como ser produzido
 * no E2E sem inventar resposta da API (o seed sempre tem pendências), então é
 * coberto aqui, pelas props.
 */

const props = { title: "Atrasadas", description: "Atividades com prazo vencido", href: "/sgp/atividades?atrasada=true" };

describe("AlertCard", () => {
  it("contagem zero mostra 'Nenhuma pendência' e mantém o link para a listagem", () => {
    render(<AlertCard {...props} state={{ phase: "ok", count: 0 }} />);
    expect(screen.getByText("Nenhuma pendência")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Ver listagem/ }).getAttribute("href")).toBe(props.href);
  });

  it("contagem positiva mostra o número e o link", () => {
    render(<AlertCard {...props} state={{ phase: "ok", count: 7 }} />);
    expect(screen.getByText("7")).toBeTruthy();
    expect(screen.queryByText("Nenhuma pendência")).toBeNull();
    expect(screen.getByRole("link", { name: /Ver listagem/ }).getAttribute("href")).toBe(props.href);
  });

  it("falha mostra o aviso, sem número nem link", () => {
    render(<AlertCard {...props} state={{ phase: "error" }} />);
    expect(screen.getByText("Não foi possível carregar")).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
