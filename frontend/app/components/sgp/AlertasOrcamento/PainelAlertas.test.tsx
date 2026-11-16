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
    expect(vermelho).toHaveTextContent("Pool · Diárias");
    expect(vermelho).toHaveTextContent("Semáforo · desde 10/11/2026");
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

  it("Ver mais pede a página seguinte", async () => {
    mocks.fetchAlertas.mockResolvedValue({ count: 15, results: [VERMELHO, REMANEJAMENTO] });
    renderPainel();

    fireEvent.click(await screen.findByTestId("alertas-orcamento-mais"));
    await waitFor(() => expect(ultimaChamada()).toMatchObject({ limit: 20 }));
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
