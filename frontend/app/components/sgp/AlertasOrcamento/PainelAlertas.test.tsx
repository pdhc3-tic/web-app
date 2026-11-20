import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import type { AlertaOrcamento } from "@/app/lib/alertasOrcamento";
import { PainelAlertas } from "./PainelAlertas";

/** #403: painel de alertas orçamentários do Painel de Orçamento e da home do SGD. */

const mocks = vi.hoisted(() => ({ fetchAlertas: vi.fn() }));

vi.mock("@/app/lib/alertasOrcamento", async () => {
  const atual = await vi.importActual<typeof import("@/app/lib/alertasOrcamento")>(
    "@/app/lib/alertasOrcamento",
  );
  return { ...atual, fetchAlertas: mocks.fetchAlertas };
});

function alerta(id: number, parcial: Partial<AlertaOrcamento>): AlertaOrcamento {
  return {
    id,
    tipo: "semaforo",
    escopo: "pool",
    referencia_id: 100 + id,
    alvo: {
      nome: "Cariri Paraibano",
      nivel: "territorial",
      estado: { sigla: "PB", nome: "Paraíba" },
      territorio: { id: 2, nome: "Cariri Paraibano" },
      usuario: null,
    },
    rubrica: 1,
    rubrica_nome: "Diárias",
    faixa: "vermelho",
    percentual_atingido: "96.50",
    criado_em: "2026-11-10T09:00:00-03:00",
    alertado_em: "2026-11-10T09:00:00-03:00",
    resolvido_em: null,
    ...parcial,
  };
}

const VERMELHO = alerta(1, {});
const REMANEJAMENTO = alerta(2, {
  tipo: "remanejamento_excessivo",
  faixa: "",
  rubrica_nome: "Locação de veículo",
  percentual_atingido: "31.00",
});

function renderPainel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <PainelAlertas />
    </QueryClientProvider>,
  );
}

const ultimaChamada = () => mocks.fetchAlertas.mock.calls.at(-1)?.[0];

describe("PainelAlertas (#403)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.fetchAlertas.mockResolvedValue({ count: 2, results: [VERMELHO, REMANEJAMENTO] });
  });

  it("lista os alertas abertos com alvo, tipo, percentual e faixa", async () => {
    renderPainel();

    const vermelho = await screen.findByTestId("alerta-orcamento-1");
    // O alvo pelo nome que o backend devolve (#423, item 5).
    expect(vermelho).toHaveTextContent("Cariri Paraibano · Diárias");
    expect(vermelho).toHaveTextContent("Pool territorial · Semáforo · desde 10/11/2026");
    expect(vermelho).toHaveTextContent("96,5%");
    expect(vermelho).toHaveTextContent("Vermelho");

    const remanejamento = screen.getByTestId("alerta-orcamento-2");
    expect(remanejamento).toHaveTextContent("Remanejamento excessivo");
    expect(remanejamento).toHaveTextContent("Sem faixa");
    expect(screen.getByTestId("alertas-orcamento-total")).toHaveTextContent("2");
  });

  it("filtra por tipo e por faixa no servidor", async () => {
    renderPainel();
    await screen.findByTestId("alerta-orcamento-1");

    fireEvent.change(screen.getByTestId("alertas-orcamento-filtro-tipo"), {
      target: { value: "subexecucao" },
    });
    await waitFor(() => expect(ultimaChamada()).toMatchObject({ tipo: "subexecucao", faixa: "" }));

    fireEvent.change(screen.getByTestId("alertas-orcamento-filtro-faixa"), {
      target: { value: "vermelho" },
    });
    await waitFor(() => expect(ultimaChamada()).toMatchObject({ tipo: "subexecucao", faixa: "vermelho" }));
  });

  it("sem alertas, diz se é pelo filtro ou porque não há nenhum aberto", async () => {
    mocks.fetchAlertas.mockResolvedValue({ count: 0, results: [] });
    renderPainel();

    expect(await screen.findByTestId("alertas-orcamento-vazio")).toHaveTextContent("Nenhum alerta aberto");

    fireEvent.change(screen.getByTestId("alertas-orcamento-filtro-tipo"), {
      target: { value: "semaforo" },
    });
    await waitFor(() => {
      expect(screen.getByTestId("alertas-orcamento-vazio")).toHaveTextContent("Nenhum alerta com estes filtros");
    });
  });

  /**
   * O servidor de verdade: `OrcamentoPagination` corta o `limit` em 100 e anda
   * por `offset`. Revisão do PR #433: só aumentar o `limit` deixava o 101º
   * alerta inacessível.
   */
  function servidorCom(quantos: number) {
    const todos = Array.from({ length: quantos }, (_, i) => alerta(1000 + i, {}));
    mocks.fetchAlertas.mockImplementation(async ({ offset = 0, limit = 10 }: { offset?: number; limit?: number }) => ({
      count: todos.length,
      results: todos.slice(offset, offset + Math.min(limit, 100)),
    }));
    return todos;
  }

  it("Ver mais avança pelo offset até o último de mais de 100 alertas, e então some", async () => {
    const todos = servidorCom(101);
    renderPainel();
    await screen.findByTestId(`alerta-orcamento-${todos[9].id}`);

    // 10 por página: dez cliques levam do 10º ao 101º.
    for (let pagina = 1; pagina <= 10; pagina++) {
      fireEvent.click(await screen.findByText(new RegExp(`^Ver mais \\(${pagina * 10} de 101\\)$`)));
      await screen.findByTestId(`alerta-orcamento-${todos[Math.min(pagina * 10 + 9, 100)].id}`);
    }

    expect(screen.getByTestId(`alerta-orcamento-${todos[100].id}`)).toBeInTheDocument();
    expect(screen.getAllByTestId(/^alerta-orcamento-\d+$/)).toHaveLength(101);
    await waitFor(() => expect(screen.queryByTestId("alertas-orcamento-mais")).toBeNull());
    // Cada página pediu o trecho seguinte, sem passar do teto da API.
    const pedidos = mocks.fetchAlertas.mock.calls.map(([p]) => p as { offset?: number; limit: number });
    expect(pedidos.map((p) => p.offset ?? 0)).toEqual([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]);
    expect(pedidos.every((p) => p.limit <= 100)).toBe(true);
  });

  it("um alerta repetido entre páginas aparece uma vez só", async () => {
    const todos = Array.from({ length: 15 }, (_, i) => alerta(2000 + i, {}));
    mocks.fetchAlertas
      .mockResolvedValueOnce({ count: 15, results: todos.slice(0, 10) })
      // Um alerta novo no topo desloca a lista: o 10º volta na página seguinte.
      .mockResolvedValueOnce({ count: 16, results: todos.slice(9, 15) });
    renderPainel();

    fireEvent.click(await screen.findByTestId("alertas-orcamento-mais"));
    await screen.findByTestId(`alerta-orcamento-${todos[14].id}`);
    expect(screen.getAllByTestId(`alerta-orcamento-${todos[9].id}`)).toHaveLength(1);
  });

  it("trocar o filtro recomeça a paginação do início", async () => {
    servidorCom(30);
    renderPainel();
    fireEvent.click(await screen.findByTestId("alertas-orcamento-mais"));
    await waitFor(() => expect(ultimaChamada()).toMatchObject({ offset: 10 }));

    fireEvent.change(screen.getByTestId("alertas-orcamento-filtro-tipo"), { target: { value: "semaforo" } });
    await waitFor(() => expect(ultimaChamada()).toMatchObject({ tipo: "semaforo", offset: 0 }));
    await waitFor(() => expect(screen.getAllByTestId(/^alerta-orcamento-\d+$/)).toHaveLength(10));
  });

  it("some para quem não tem acesso ao orçamento (403)", async () => {
    mocks.fetchAlertas.mockRejectedValue(
      new ApiError(403, { code: "permission_denied", message: "Sem permissão." }),
    );
    renderPainel();

    await waitFor(() => expect(mocks.fetchAlertas).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByTestId("painel-alertas-orcamento")).toBeNull());
  });

  it("outros erros aparecem com a opção de tentar de novo", async () => {
    mocks.fetchAlertas.mockRejectedValue(
      new ApiError(500, { code: "error", message: "Falha no servidor." }),
    );
    renderPainel();

    // O painel tenta mais duas vezes, com espera, antes de mostrar o erro.
    expect(
      await screen.findByTestId("alertas-orcamento-erro", undefined, { timeout: 6_000 }),
    ).toHaveTextContent("Falha no servidor.");
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });
});
