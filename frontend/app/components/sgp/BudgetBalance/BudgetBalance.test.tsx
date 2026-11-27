import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BudgetBalance } from "./BudgetBalance";

/**
 * O ramo em que o card decide pela SESSÃO (#232): o ADT/ACR sem território na
 * sessão vê o estado vazio e o card nem consulta o saldo.
 *
 * Vivia num E2E que reescrevia a resposta de `/api/auth/session`. Desde a #448
 * a sessão vem do servidor e essa chamada não acontece mais, então o ramo é
 * coberto aqui. O caminho real (vínculo desfeito no banco, 403 do painel) segue
 * em `e2e/orcamento-saldo.spec.ts`.
 */

const sessao = vi.hoisted(() => ({ territorios: [] as { id: number; nome: string; estados: string[] }[] }));
vi.mock("next-auth/react", () => ({
  useSession: () => ({
    status: "authenticated",
    data: { user: { perfis: [{ id: 1, nome: "ADT", slug: "adt-acr" }], territorios: sessao.territorios } },
  }),
}));

const buscar = vi.fn();
vi.mock("@/app/lib/orcamento", async (original) => ({
  ...(await original<typeof import("@/app/lib/orcamento")>()),
  fetchSaldoPorRubrica: (...args: unknown[]) => buscar(...args),
}));

beforeEach(() => {
  buscar.mockReset().mockResolvedValue([]);
  sessao.territorios = [];
});

describe("BudgetBalance — ADT/ACR sem território na sessão", () => {
  it("mostra o estado vazio sem consultar o saldo", async () => {
    render(<BudgetBalance />);
    expect(await screen.findByText(/Nenhum território atribuído/)).toBeTruthy();
    expect(buscar).not.toHaveBeenCalled();
    expect(screen.queryByTestId("budget-balance-erro")).toBeNull();
  });

  it("com território na sessão, consulta o saldo", async () => {
    sessao.territorios = [{ id: 3, nome: "Território PE", estados: ["PE"] }];
    render(<BudgetBalance />);
    await vi.waitFor(() => expect(buscar).toHaveBeenCalledTimes(1));
  });
});
