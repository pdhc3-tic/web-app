import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import NovoRemanejamentoPage from "./page";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  showToast: vi.fn(),
  fetchPainelOrcamento: vi.fn(),
  simularRemanejamento: vi.fn(),
  confirmarRemanejamento: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({
    status: "authenticated",
    data: {
      user: {
        id: 1,
        perfis: [{ slug: "ugp", nome: "UGP" }],
      },
    },
  }),
}));

vi.mock("@/app/components/layout/PageHeader", () => ({
  PageHeader: ({ children }: { children: React.ReactNode }) => <header>{children}</header>,
}));

vi.mock("@/app/components/ui/Toast/Toast", () => ({
  useToast: () => ({ showToast: mocks.showToast }),
}));

vi.mock("@/app/lib/orcamento", async () => {
  const atual = await vi.importActual<typeof import("@/app/lib/orcamento")>("@/app/lib/orcamento");
  return {
    ...atual,
    fetchPainelOrcamento: mocks.fetchPainelOrcamento,
  };
});

vi.mock("@/app/lib/remanejamentoSgp", async () => {
  const atual = await vi.importActual<typeof import("@/app/lib/remanejamentoSgp")>(
    "@/app/lib/remanejamentoSgp",
  );
  return {
    ...atual,
    simularRemanejamento: mocks.simularRemanejamento,
    confirmarRemanejamento: mocks.confirmarRemanejamento,
  };
});

const POOLS = [
  {
    id: 10,
    rubrica: { id: 1, nome: "Diárias", slug: "diarias" },
    nivel: "estadual",
    estado: { id: 1, sigla: "PB", nome: "Paraíba" },
    territorio: null,
    saldo_disponivel: "5000.00",
    valor_alocado: "5000.00",
    valor_comprometido: "0.00",
    valor_executado: "0.00",
    percentual_comprometido: "0.00",
    semaforo: "verde",
  },
  {
    id: 20,
    rubrica: { id: 1, nome: "Diárias", slug: "diarias" },
    nivel: "estadual",
    estado: { id: 2, sigla: "RN", nome: "Rio Grande do Norte" },
    territorio: null,
    saldo_disponivel: "500.00",
    valor_alocado: "5000.00",
    valor_comprometido: "4500.00",
    valor_executado: "0.00",
    percentual_comprometido: "90.00",
    semaforo: "vermelho",
  },
];

const SIMULACAO = {
  origem: {
    saldo_antes: "5000.00",
    saldo_depois: "4000.00",
    percentual_antes: "0.00",
    percentual_depois: "20.00",
    percentual_execucao_antes: "0.00",
    percentual_execucao_depois: "0.00",
    faixa_antes: "verde" as const,
    faixa_depois: "verde" as const,
  },
  destino: {
    saldo_antes: "500.00",
    saldo_depois: "1500.00",
    percentual_antes: "90.00",
    percentual_depois: "75.00",
    percentual_execucao_antes: "0.00",
    percentual_execucao_depois: "0.00",
    faixa_antes: "vermelho" as const,
    faixa_depois: "amarelo" as const,
  },
};

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <NovoRemanejamentoPage />
    </QueryClientProvider>,
  );
}

function escolherSelect(label: RegExp, opcao: RegExp) {
  fireEvent.click(screen.getByLabelText(label));
  fireEvent.mouseDown(screen.getByRole("option", { name: opcao }));
}

describe("NovoRemanejamentoPage (#402)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.fetchPainelOrcamento.mockResolvedValue(POOLS);
    mocks.simularRemanejamento.mockResolvedValue(SIMULACAO);
    mocks.confirmarRemanejamento.mockResolvedValue([{ id: 1 }]);
  });

  it("simula antes de exibir o botão de confirmar, mostra mudança de faixa e confirma com o mesmo payload", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/Pool de origem/i)).toBeInTheDocument();
    });

    // Espera os pools carregarem no Select.
    await waitFor(() => {
      expect(mocks.fetchPainelOrcamento).toHaveBeenCalled();
    });

    // Antes de simular, o botão de confirmar não existe na tela.
    expect(screen.queryByTestId("remanejamento-confirmar")).toBeNull();

    escolherSelect(/Pool de origem/i, /Paraíba/);
    escolherSelect(/Pool de destino/i, /Rio Grande do Norte/);
    fireEvent.change(screen.getByLabelText(/Valor \(R\$\)/i), { target: { value: "1000.00" } });
    fireEvent.change(screen.getByLabelText(/Justificativa/i), {
      target: { value: "Reforço para o RN" },
    });

    fireEvent.click(screen.getByTestId("remanejamento-simular"));

    await waitFor(() => {
      expect(screen.getByTestId("remanejamento-simulacao")).toBeInTheDocument();
    });

    expect(screen.getByTestId("impacto-destino-mudou-faixa")).toBeInTheDocument();
    expect(mocks.simularRemanejamento).toHaveBeenCalledWith({
      origem_allocation: 10,
      destino_allocation: 20,
      valor: "1000.00",
      justificativa: "Reforço para o RN",
    });

    fireEvent.click(screen.getByTestId("remanejamento-confirmar"));

    await waitFor(() => {
      expect(mocks.confirmarRemanejamento).toHaveBeenCalledWith({
        origem_allocation: 10,
        destino_allocation: 20,
        valor: "1000.00",
        justificativa: "Reforço para o RN",
      });
    });
  });

  it("exibe INSUFFICIENT_BALANCE e invalida a simulação se o saldo mudou antes de confirmar", async () => {
    mocks.confirmarRemanejamento.mockRejectedValueOnce(
      new ApiError(400, {
        code: "INSUFFICIENT_BALANCE",
        message: "Saldo insuficiente.",
      }),
    );

    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/Pool de origem/i)).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(mocks.fetchPainelOrcamento).toHaveBeenCalled();
    });

    escolherSelect(/Pool de origem/i, /Paraíba/);
    escolherSelect(/Pool de destino/i, /Rio Grande do Norte/);
    fireEvent.change(screen.getByLabelText(/Valor \(R\$\)/i), { target: { value: "1000.00" } });
    fireEvent.change(screen.getByLabelText(/Justificativa/i), {
      target: { value: "Reforço para o RN" },
    });

    fireEvent.click(screen.getByTestId("remanejamento-simular"));
    await waitFor(() => {
      expect(screen.getByTestId("remanejamento-confirmar")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("remanejamento-confirmar"));

    await waitFor(() => {
      expect(screen.getByTestId("remanejamento-erro")).toHaveTextContent("INSUFFICIENT_BALANCE");
    });
    expect(screen.queryByTestId("remanejamento-simulacao")).toBeNull();
  });
});
