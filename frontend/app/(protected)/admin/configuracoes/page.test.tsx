import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FaixaDestino, ValorDiaria } from "@/app/lib/diarias";
import ConfiguracoesPage from "./page";

/** #440 — o card da Tabela de diárias avisa as faixas sem valor vigente. */

const mocks = vi.hoisted(() => ({ listarFaixas: vi.fn(), listarValores: vi.fn() }));

vi.mock("@/app/lib/auth/roles", async (original) => ({
  ...(await original<typeof import("@/app/lib/auth/roles")>()),
  useIsSuperAdmin: () => ({ loading: false, isSuperAdmin: true }),
}));
vi.mock("@/app/components/layout/PageHeader", () => ({
  PageHeader: ({ children }: { children: React.ReactNode }) => <header>{children}</header>,
}));
vi.mock("@/app/lib/diarias", async (original) => ({
  ...(await original<typeof import("@/app/lib/diarias")>()),
  listarFaixas: mocks.listarFaixas,
  listarValores: mocks.listarValores,
}));

const faixa = (id: number): FaixaDestino => ({ id, nome: `Faixa ${id}`, ordem: id, padrao: null, ativo: true, enquadramentos: [] });
const emAberto = (id: number, faixaId: number): ValorDiaria => ({
  id, faixa_destino: faixaId, faixa_destino_nome: `Faixa ${faixaId}`, categoria_beneficiario: "padrao",
  vigencia_inicio: "2025-01-01", vigencia_fim: null, valor: "300.00", origem: "fgd", criado_por_nome: null,
  criado_em: "2025-01-01T00:00:00Z",
});

function montar() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ConfiguracoesPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocks.listarFaixas.mockReset().mockResolvedValue([faixa(1), faixa(2), faixa(3)]);
  mocks.listarValores.mockReset();
});

describe("Configurações — aviso da Tabela de diárias (#440)", () => {
  it("conta as faixas sem valor vigente no card", async () => {
    mocks.listarValores.mockResolvedValue([emAberto(1, 1)]);
    montar();
    expect(await screen.findByTestId("configuracao-aviso-diarias")).toHaveTextContent("2 faixas sem valor vigente");
  });

  it("sem lacuna, o card não avisa nada", async () => {
    mocks.listarValores.mockResolvedValue([emAberto(1, 1), emAberto(2, 2), emAberto(3, 3)]);
    montar();
    await screen.findByTestId("configuracao-card-diarias");
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByTestId("configuracao-aviso-diarias")).toBeNull();
  });

  it("falha ao carregar a tabela não mostra aviso", async () => {
    mocks.listarValores.mockRejectedValue(new Error("rede"));
    montar();
    await screen.findByTestId("configuracao-card-diarias");
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByTestId("configuracao-aviso-diarias")).toBeNull();
  });
});
