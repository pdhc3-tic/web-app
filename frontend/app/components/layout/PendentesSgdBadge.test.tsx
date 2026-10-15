import { act, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { qk } from "@/app/lib/queryKeys";
import { PendentesSgdBadge, rotuloPendentes } from "./PendentesSgdBadge";

/**
 * Badge "N pendentes" do SGD na sidebar (#296): a contagem da fila
 * "Aguardando minha ação", com a regra de cada perfil aplicada no backend.
 */

const sessao = vi.hoisted(() => ({ perfis: [{ slug: "ugp" }] as { slug: string }[] }));
const contagem = vi.hoisted(() => ({ fetch: vi.fn() }));

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { user: { perfis: sessao.perfis } }, status: "authenticated" }),
}));

vi.mock("@/app/lib/demandas", async (original) => ({
  ...(await original<typeof import("@/app/lib/demandas")>()),
  fetchContagemFila: contagem.fetch,
}));

function renderBadge() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PendentesSgdBadge className="badge" />
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => {
  sessao.perfis = [{ slug: "ugp" }];
  contagem.fetch.mockReset();
});

describe("rotuloPendentes", () => {
  it("usa singular para 1 e plural para os demais", () => {
    expect(rotuloPendentes(1)).toBe("1 pendente");
    expect(rotuloPendentes(2)).toBe("2 pendentes");
    expect(rotuloPendentes(10)).toBe("10 pendentes");
  });
});

describe("PendentesSgdBadge", () => {
  it("não aparece quando a fila está vazia", async () => {
    contagem.fetch.mockResolvedValue({ total: 0, status: ["pre_autorizada"] });
    renderBadge();

    await waitFor(() => expect(contagem.fetch).toHaveBeenCalled());
    expect(screen.queryByTestId("sidebar-badge-sgd")).not.toBeInTheDocument();
  });

  it("mostra 1 pendente no singular", async () => {
    contagem.fetch.mockResolvedValue({ total: 1, status: ["pre_autorizada"] });
    renderBadge();

    const badge = await screen.findByTestId("sidebar-badge-sgd");
    expect(badge).toHaveTextContent("1");
    expect(badge).toHaveAccessibleName("1 pendente");
  });

  it("mostra N pendentes no plural", async () => {
    contagem.fetch.mockResolvedValue({ total: 3, status: ["pre_autorizada"] });
    renderBadge();

    const badge = await screen.findByTestId("sidebar-badge-sgd");
    expect(badge).toHaveTextContent("3");
    expect(badge).toHaveAccessibleName("3 pendentes");
  });

  it("atualiza quando a fila é invalidada depois de uma decisão", async () => {
    contagem.fetch
      .mockResolvedValueOnce({ total: 2, status: ["submetida"] })
      .mockResolvedValueOnce({ total: 1, status: ["submetida"] })
      .mockResolvedValueOnce({ total: 0, status: ["submetida"] });
    const client = renderBadge();

    expect(await screen.findByTestId("sidebar-badge-sgd")).toHaveTextContent("2");

    // É o que o painel faz ao registrar uma decisão.
    await act(() => client.invalidateQueries({ queryKey: qk.demandas.all }));
    await waitFor(() => expect(screen.getByTestId("sidebar-badge-sgd")).toHaveTextContent("1"));

    await act(() => client.invalidateQueries({ queryKey: qk.demandas.all }));
    await waitFor(() => expect(screen.queryByTestId("sidebar-badge-sgd")).not.toBeInTheDocument());
  });

  it("não consulta a fila para quem não decide sobre demandas", async () => {
    sessao.perfis = [{ slug: "adt-acr" }];
    renderBadge();

    await new Promise((r) => setTimeout(r, 50));
    expect(contagem.fetch).not.toHaveBeenCalled();
    expect(screen.queryByTestId("sidebar-badge-sgd")).not.toBeInTheDocument();
  });
});
