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

type Rubrica = { id: number; nome: string; slug: string };
type Estado = { id: number; sigla: string; nome: string };

function pool(id: number, rubrica: Rubrica, estado: Estado, saldo: string) {
  return {
    id,
    rubrica,
    nivel: "estadual",
    estado,
    territorio: null,
    reserva_ugp: false,
    // Diferente de propósito: a opção mostra o `saldo_pool`, não este.
    saldo_disponivel: "1.00",
    saldo_pool: saldo,
    valor_alocado: "5000.00",
    valor_comprometido: "0.00",
    valor_executado: "0.00",
    semaforo: "verde",
  };
}

const DIARIAS = { id: 1, nome: "Diárias", slug: "diarias" };
const GRAFICO = { id: 2, nome: "Material gráfico", slug: "material-grafico" };
const PB = { id: 1, sigla: "PB", nome: "Paraíba" };
const RN = { id: 2, sigla: "RN", nome: "Rio Grande do Norte" };
const CE = { id: 3, sigla: "CE", nome: "Ceará" };

const POOLS = [
  pool(10, DIARIAS, PB, "5000.00"),
  pool(20, DIARIAS, RN, "500.00"),
  pool(30, GRAFICO, CE, "800.00"),
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

/** A simulação não leva justificativa (#423, item 4); a confirmação leva. */
const SIMULADO = {
  origem_allocation: 10,
  destino_allocation: 20,
  valor: "1000.00",
};
const PAYLOAD = { ...SIMULADO, justificativa: "Reforço para o RN" };

/** O 400 de `_exigir_saldo_na_origem`, como o `apiClient` o entrega. */
function recusaDeSaldo(disponivel: string) {
  const detail = `Saldo insuficiente na origem: R$ ${disponivel} disponível.`;
  const corpo = {
    valor: [detail],
    code: "INSUFFICIENT_BALANCE",
    trava: "origem",
    rubrica: "diarias",
    disponivel,
    solicitado: "1000.00",
    valor_faltante: "800.00",
    acao_sugerida: "informar_outra_origem",
    detail,
  };
  return new ApiError(400, { code: "INSUFFICIENT_BALANCE", message: detail }, corpo);
}

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

/** Espera os pools carregarem e abre o Select de origem. */
async function abrirOrigem() {
  await waitFor(() => expect(mocks.fetchPainelOrcamento).toHaveBeenCalled());
  fireEvent.click(screen.getByLabelText(/Pool de origem/i));
  await screen.findByRole("option", { name: /Paraíba/ });
}

async function preencher(valor = "1000.00") {
  renderPage();
  await abrirOrigem();
  fireEvent.mouseDown(screen.getByRole("option", { name: /Paraíba/ }));
  escolherSelect(/Pool de destino/i, /Rio Grande do Norte/);
  fireEvent.change(screen.getByLabelText(/Valor \(R\$\)/i), { target: { value: valor } });
}

/** A justificativa só aparece com a simulação na tela. */
async function justificar() {
  fireEvent.change(await screen.findByLabelText(/Justificativa/i), {
    target: { value: "Reforço para o RN" },
  });
}

describe("NovoRemanejamentoPage (#402)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.fetchPainelOrcamento.mockResolvedValue(POOLS);
    mocks.simularRemanejamento.mockResolvedValue(SIMULACAO);
    mocks.confirmarRemanejamento.mockResolvedValue([{ id: 1 }]);
  });

  it("simula sozinha com origem, destino e valor; a justificativa só é pedida para confirmar", async () => {
    await preencher();
    expect(screen.queryByTestId("remanejamento-confirmar")).toBeNull();
    expect(screen.queryByTestId("remanejamento-simular")).toBeNull();

    await screen.findByTestId("remanejamento-simulacao");
    expect(screen.getByTestId("impacto-destino-mudou-faixa")).toBeInTheDocument();
    expect(mocks.simularRemanejamento).toHaveBeenCalledTimes(1);
    expect(mocks.simularRemanejamento.mock.calls[0][0]).toEqual(SIMULADO);

    // Sem justificativa não confirma.
    expect(screen.getByTestId("remanejamento-confirmar")).toBeDisabled();
    await justificar();
    // Escrever a justificativa não refaz a simulação.
    expect(mocks.simularRemanejamento).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId("remanejamento-confirmar"));
    await waitFor(() => {
      expect(mocks.confirmarRemanejamento).toHaveBeenCalledWith(PAYLOAD);
    });
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/sgp/orcamento"));
  });

  it("mudar o valor refaz a simulação com o valor novo, só depois de ele parar de mudar", async () => {
    await preencher();
    await screen.findByTestId("remanejamento-simulacao");

    const valor = screen.getByLabelText(/Valor \(R\$\)/i);
    fireEvent.change(valor, { target: { value: "15" } });
    fireEvent.change(valor, { target: { value: "150" } });
    // A simulação anterior sai na hora: ela não vale para o valor novo.
    expect(screen.queryByTestId("remanejamento-simulacao")).toBeNull();
    expect(screen.getByTestId("remanejamento-simulando")).toBeInTheDocument();

    await screen.findByTestId("remanejamento-simulacao");
    expect(mocks.simularRemanejamento).toHaveBeenCalledTimes(2);
    expect(mocks.simularRemanejamento.mock.calls[1][0]).toEqual({ ...SIMULADO, valor: "150" });
  });

  it("cada opção mostra o saldo que o remanejamento aceita tirar (saldo_pool)", async () => {
    renderPage();
    await abrirOrigem();
    expect(
      screen.getByRole("option", { name: /Paraíba · Diárias · saldo R\$\s5\.000,00/ }),
    ).toBeInTheDocument();
  });

  it("o destino só lista os outros pools da rubrica da origem", async () => {
    renderPage();
    await waitFor(() => expect(mocks.fetchPainelOrcamento).toHaveBeenCalled());
    expect(screen.getByLabelText(/Pool de destino/i)).toBeDisabled();

    await abrirOrigem();
    fireEvent.mouseDown(screen.getByRole("option", { name: /Paraíba/ }));

    fireEvent.click(screen.getByLabelText(/Pool de destino/i));
    const opcoes = screen.getAllByRole("option").map((o) => o.textContent ?? "");
    expect(opcoes.some((t) => t.includes("Rio Grande do Norte"))).toBe(true);
    expect(opcoes.some((t) => t.includes("Ceará"))).toBe(false);
    expect(opcoes.some((t) => t.includes("Paraíba"))).toBe(false);
    fireEvent.mouseDown(screen.getByRole("option", { name: /Rio Grande do Norte/ }));

    // Trocar para uma origem de outra rubrica descarta o destino escolhido.
    escolherSelect(/Pool de origem/i, /Ceará/);
    expect(screen.getByText(/Não há outro pool de Material gráfico/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Pool de destino/i)).not.toHaveTextContent("Rio Grande do Norte");
  });

  it("com valor zero não simula", async () => {
    await preencher("0");
    expect(screen.queryByTestId("remanejamento-simulando")).toBeNull();
    await new Promise((r) => setTimeout(r, 700));
    expect(mocks.simularRemanejamento).not.toHaveBeenCalled();
  });

  it("na simulação, saldo insuficiente diz quanto há na origem, sem mostrar o código", async () => {
    mocks.simularRemanejamento.mockRejectedValueOnce(recusaDeSaldo("200.00"));
    await preencher();

    await waitFor(() => {
      expect(screen.getByTestId("remanejamento-erro")).toHaveTextContent(
        /O valor passa do saldo da origem: há R\$\s200,00 disponível/,
      );
    });
    expect(screen.getByTestId("remanejamento-erro")).not.toHaveTextContent("INSUFFICIENT_BALANCE");
    expect(screen.getByTestId("remanejamento-erro")).not.toHaveTextContent("mudou");
  });

  it("na confirmação, saldo que mudou recarrega os pools e refaz a simulação", async () => {
    mocks.confirmarRemanejamento.mockRejectedValueOnce(recusaDeSaldo("200.00"));
    await preencher();
    await screen.findByTestId("remanejamento-simulacao");
    await justificar();
    const leiturasAntes = mocks.fetchPainelOrcamento.mock.calls.length;
    // Com o saldo novo, o mesmo valor já não cabe na origem.
    mocks.simularRemanejamento.mockRejectedValueOnce(recusaDeSaldo("200.00"));

    fireEvent.click(screen.getByTestId("remanejamento-confirmar"));

    await waitFor(() => {
      expect(screen.getByTestId("remanejamento-erro")).toHaveTextContent(
        /O saldo da origem mudou desde a simulação e agora é R\$\s200,00/,
      );
    });
    expect(screen.getByTestId("remanejamento-erro")).not.toHaveTextContent("INSUFFICIENT_BALANCE");
    expect(screen.queryByTestId("remanejamento-simulacao")).toBeNull();
    await waitFor(() => {
      expect(mocks.fetchPainelOrcamento.mock.calls.length).toBeGreaterThan(leiturasAntes);
    });
    // A simulação foi refeita com o saldo novo, e a recusa dela não volta a mostrar o impacto antigo.
    await waitFor(() => expect(mocks.simularRemanejamento).toHaveBeenCalledTimes(2));
    expect(screen.queryByTestId("remanejamento-simulacao")).toBeNull();
    expect(screen.queryByTestId("remanejamento-confirmar")).toBeNull();
  });

  it("sem pools, explica que é preciso distribuir o orçamento antes", async () => {
    mocks.fetchPainelOrcamento.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("remanejamento-sem-pools")).toBeInTheDocument();
    });
  });
});
