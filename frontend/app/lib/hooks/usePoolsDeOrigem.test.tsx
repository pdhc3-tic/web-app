import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PoolOrcamentoApi } from "@/app/lib/orcamento";
import { usePoolsDeOrigem } from "./usePoolsDeOrigem";

/**
 * #399 — as origens do excedente (#363) e do recurso extra (#321) vêm dos
 * pools estaduais e nacional da matriz Rubrica × Nível, sem passar pela Meta.
 */

const api = vi.hoisted(() => ({ fetchPoolsDaRubrica: vi.fn() }));
vi.mock("@/app/lib/orcamento", () => ({ fetchPoolsDaRubrica: api.fetchPoolsDaRubrica }));

function pool(id: number, nivel: "nacional" | "estadual", estado: string | null): PoolOrcamentoApi {
  return {
    id,
    nivel,
    rubrica: { id: 3, slug: "locacao-veiculo", nome: "Locação de Veículo" },
    estado: estado ? { id: id, sigla: estado.slice(0, 2).toUpperCase(), nome: estado } : null,
    territorio: null,
    saldo_pool: "1000.00",
  } as PoolOrcamentoApi;
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("usePoolsDeOrigem (#399)", () => {
  beforeEach(() => {
    api.fetchPoolsDaRubrica.mockReset();
    api.fetchPoolsDaRubrica.mockImplementation(async ({ nivel }: { nivel: string }) =>
      nivel === "nacional" ? [pool(9, "nacional", null)] : [pool(7, "estadual", "Rio Grande do Norte"), pool(5, "estadual", "Paraíba")],
    );
  });

  it("busca o nacional e os estaduais da rubrica, com o nacional primeiro e os estados por nome", async () => {
    const { result } = renderHook(() => usePoolsDeOrigem(["locacao-veiculo"]), { wrapper });

    await waitFor(() => expect(result.current.carregando).toBe(false));
    expect(api.fetchPoolsDaRubrica).toHaveBeenCalledWith({ rubrica: "locacao-veiculo", nivel: "nacional" }, expect.anything());
    expect(api.fetchPoolsDaRubrica).toHaveBeenCalledWith({ rubrica: "locacao-veiculo", nivel: "estadual" }, expect.anything());
    expect(result.current.pools.map((p) => p.id)).toEqual([9, 5, 7]);
    expect(result.current.falhou).toBe(false);
  });

  it("desabilitado, não chama a API nem fica carregando", () => {
    const { result } = renderHook(() => usePoolsDeOrigem(["locacao-veiculo"], false), { wrapper });

    expect(api.fetchPoolsDaRubrica).not.toHaveBeenCalled();
    expect(result.current.carregando).toBe(false);
    expect(result.current.pools).toEqual([]);
  });

  it("falha numa das consultas é sinalizada", async () => {
    api.fetchPoolsDaRubrica.mockRejectedValueOnce(new Error("500"));
    const { result } = renderHook(() => usePoolsDeOrigem(["locacao-veiculo"]), { wrapper });

    await waitFor(() => expect(result.current.falhou).toBe(true));
  });
});
