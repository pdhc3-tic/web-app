import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { riscosAbertos, totalExposto, type RiscoGlosa } from "@/app/lib/demandas";
import { RiscosDeGlosa } from "./RiscosDeGlosa";

/** #404 — bloco "Riscos de glosa" da ficha: só aparece quando há risco em aberto. */

const sessao = vi.hoisted(() => ({ perfis: ["ugp"] as string[] }));
const api = vi.hoisted(() => ({ listar: vi.fn() }));

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { user: { id: "1", perfis: sessao.perfis } }, status: "authenticated" }),
}));

vi.mock("@/app/lib/auth/roles", () => ({
  canVerRiscosDeGlosa: (user: { perfis: string[] } | undefined) => !user?.perfis.includes("adt-acr"),
}));

vi.mock("@/app/lib/demandas", async (original) => ({
  ...(await original<typeof import("@/app/lib/demandas")>()),
  listRiscosDeGlosaDaAtividade: api.listar,
}));

const risco = (extra: Partial<RiscoGlosa>): RiscoGlosa => ({
  id: 1,
  tipo: "pago_acima_autorizado",
  severidade: "alta",
  valor_exposto: "200.00",
  activity_id: 9,
  demanda_id: 42,
  demand_request_id: 7,
  valor_autorizado: "1200.00",
  valor_pago: "1400.00",
  criado_em: "2026-11-01T10:00:00-03:00",
  resolvido_em: null,
  ...extra,
});

function montar() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RiscosDeGlosa atividadeId={9} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  sessao.perfis = ["ugp"];
  api.listar.mockReset();
});

describe("RiscosDeGlosa (#404)", () => {
  it("lista tipo, severidade e valor exposto de cada risco em aberto", async () => {
    api.listar.mockResolvedValue([
      risco({ id: 1 }),
      risco({ id: 2, tipo: "demanda_sem_evidencia", severidade: "media", valor_exposto: "350.50", demanda_id: 43 }),
    ]);
    montar();

    const primeiro = await screen.findByTestId("risco-de-glosa-1");
    expect(primeiro.textContent).toContain("Pago acima do autorizado");
    expect(primeiro.textContent).toContain("200,00");
    expect(screen.getByTestId("risco-de-glosa-severidade-1").textContent).toBe("Severidade alta");

    const segundo = screen.getByTestId("risco-de-glosa-2");
    expect(segundo.textContent).toContain("Demanda executada sem evidência");
    expect(segundo.textContent).toContain("350,50");
    expect(screen.getByTestId("riscos-de-glosa-total").textContent).toContain("550,50");
  });

  it("a severidade tem cor própria: alta em erro, média em atenção, baixa em neutro", async () => {
    api.listar.mockResolvedValue([
      risco({ id: 1, severidade: "alta" }),
      risco({ id: 2, severidade: "media" }),
      risco({ id: 3, severidade: "baixa" }),
    ]);
    montar();

    expect((await screen.findByTestId("risco-de-glosa-severidade-1")).className).toContain("text-error-text");
    expect(screen.getByTestId("risco-de-glosa-severidade-2").className).toContain("text-warning-text");
    expect(screen.getByTestId("risco-de-glosa-severidade-3").className).toContain("text-neutral-text");
  });

  it("sem risco, o bloco não aparece", async () => {
    api.listar.mockResolvedValue([]);
    const { container } = montar();
    await waitFor(() => expect(api.listar).toHaveBeenCalled());
    expect(screen.queryByTestId("riscos-de-glosa")).toBeNull();
    expect(container.textContent).toBe("");
  });

  it("erro na consulta avisa, em vez de parecer que não há risco", async () => {
    api.listar.mockRejectedValue(new Error("falhou"));
    montar();
    expect(await screen.findByTestId("riscos-de-glosa-erro")).toHaveTextContent(
      "Não foi possível verificar os riscos de glosa desta atividade.",
    );
    expect(screen.queryByTestId("riscos-de-glosa")).toBeNull();

    api.listar.mockResolvedValue([risco({ id: 3 })]);
    screen.getByRole("button", { name: "Tentar de novo" }).click();
    expect(await screen.findByTestId("riscos-de-glosa")).toBeInTheDocument();
  });

  it("risco já resolvido não conta", async () => {
    api.listar.mockResolvedValue([risco({ id: 1, resolvido_em: "2026-11-05T10:00:00-03:00" })]);
    montar();
    await waitFor(() => expect(api.listar).toHaveBeenCalled());
    expect(screen.queryByTestId("riscos-de-glosa")).toBeNull();
  });

  it("quem não pode ver riscos (ADT) nem consulta a rota", () => {
    sessao.perfis = ["adt-acr"];
    montar();
    expect(api.listar).not.toHaveBeenCalled();
    expect(screen.queryByTestId("riscos-de-glosa")).toBeNull();
  });
});

describe("riscos de glosa — leitura", () => {
  it("riscosAbertos descarta os resolvidos e aceita lista ausente", () => {
    expect(riscosAbertos(undefined)).toEqual([]);
    expect(riscosAbertos([risco({ id: 1 }), risco({ id: 2, resolvido_em: "2026-11-05T10:00:00-03:00" })]).map((r) => r.id)).toEqual([1]);
  });

  it("totalExposto soma sem erro de ponto flutuante", () => {
    expect(totalExposto([risco({ valor_exposto: "0.10" }), risco({ valor_exposto: "0.20" })])).toBe("0.30");
    expect(totalExposto([])).toBe("0.00");
  });
});
