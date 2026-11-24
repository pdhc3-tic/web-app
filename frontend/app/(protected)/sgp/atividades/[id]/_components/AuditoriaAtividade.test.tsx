import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuditoriaAtividade } from "./AuditoriaAtividade";

/** #449 — "Criado por" lê o `UsuarioRef` ({id, nome}) do detalhe da atividade. */

const sessao = vi.hoisted(() => ({ userId: 99 as number | string }));
vi.mock("next-auth/react", () => ({
  useSession: () => ({ status: "authenticated", data: { user: { id: sessao.userId } } }),
}));

const DATAS = { criado_em: "2026-11-10T12:00:00Z", atualizado_em: "2026-11-20T15:30:00Z" };

function criadoPor(): string {
  const termo = screen.getByText("Criado por");
  return termo.nextElementSibling?.textContent ?? "";
}

beforeEach(() => {
  sessao.userId = 99;
});

describe("AuditoriaAtividade (#449)", () => {
  it("mostra o nome de quem criou, e não o objeto", () => {
    render(<AuditoriaAtividade atividade={{ ...DATAS, criado_por: { id: 7, nome: "Beatriz Nogueira" } }} />);

    expect(criadoPor()).toBe("Beatriz Nogueira");
    expect(screen.getByTestId("atividade-auditoria").textContent).not.toContain("[object Object]");
    expect(screen.getByTestId("atividade-auditoria").textContent).not.toContain("Usuário #");
  });

  it("marca o próprio usuário logado", () => {
    sessao.userId = "7";
    render(<AuditoriaAtividade atividade={{ ...DATAS, criado_por: { id: 7, nome: "Beatriz Nogueira" } }} />);

    expect(criadoPor()).toBe("Beatriz Nogueira (você)");
  });

  it("sem autor, mostra o traço", () => {
    render(<AuditoriaAtividade atividade={{ ...DATAS, criado_por: null }} />);

    expect(criadoPor()).toBe("—");
  });
});
