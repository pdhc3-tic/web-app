import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import DotacaoNacionalPage from "./page";

const mocks = vi.hoisted(() => ({
  perfil: "ugp",
  showToast: vi.fn(),
  listRubricas: vi.fn(),
  fetchPainelOrcamento: vi.fn(),
  lancarDotacaoNacional: vi.fn(),
  atualizarPool: vi.fn(),
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({
    status: "authenticated",
    data: { user: { id: 1, perfis: [{ slug: mocks.perfil, nome: mocks.perfil }] } },
  }),
}));

vi.mock("@/app/components/layout/PageHeader", () => ({
  PageHeader: ({ children }: { children: React.ReactNode }) => <header>{children}</header>,
}));

vi.mock("@/app/components/ui/Toast/Toast", () => ({
  useToast: () => ({ showToast: mocks.showToast }),
}));

vi.mock("@/app/lib/tiposSolicitacao", async () => {
  const atual = await vi.importActual<typeof import("@/app/lib/tiposSolicitacao")>("@/app/lib/tiposSolicitacao");
  return { ...atual, listRubricas: mocks.listRubricas };
});

vi.mock("@/app/lib/orcamento", async () => {
  const atual = await vi.importActual<typeof import("@/app/lib/orcamento")>("@/app/lib/orcamento");
  return {
    ...atual,
    fetchPainelOrcamento: mocks.fetchPainelOrcamento,
    lancarDotacaoNacional: mocks.lancarDotacaoNacional,
    atualizarPool: mocks.atualizarPool,
  };
});

const DIARIAS = { id: 1, slug: "diarias", nome: "Diárias", ativo: true };
const GRAFICO = { id: 5, slug: "material-grafico", nome: "Material Gráfico", ativo: true };
const ANTIGA_SEM_POOL = { id: 9, slug: "antiga", nome: "Rubrica antiga", ativo: false };

function poolNacional(
  id: number,
  rubrica: { id: number; slug: string; nome: string },
  valores: { aprovado: string; distribuido?: string; comprometido?: string },
) {
  return {
    id,
    rubrica: { id: rubrica.id, slug: rubrica.slug, nome: rubrica.nome },
    nivel: "nacional",
    estado: null,
    territorio: null,
    reserva_ugp: false,
    valor_aprovado: valores.aprovado,
    valor_distribuido: valores.distribuido ?? "0.00",
    valor_comprometido: valores.comprometido ?? "0.00",
    valor_executado: "0.00",
    saldo_disponivel: "0.00",
    saldo_pool: "0.00",
    semaforo: "verde",
    alerta_80: false,
    limiares_semaforo: {},
  };
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DotacaoNacionalPage />
    </QueryClientProvider>,
  );
}

function digitar(slug: string, centavos: string) {
  fireEvent.change(screen.getByTestId(`dotacao-valor-${slug}`), { target: { value: centavos } });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.perfil = "ugp";
  mocks.listRubricas.mockResolvedValue([DIARIAS, GRAFICO, ANTIGA_SEM_POOL]);
  mocks.fetchPainelOrcamento.mockResolvedValue([]);
});

describe("Dotação nacional (#438)", () => {
  it("lista as rubricas ativas e pede só o nível nacional ao painel", async () => {
    renderPage();
    expect(await screen.findByTestId("dotacao-rubrica-diarias")).toBeInTheDocument();
    expect(screen.getByTestId("dotacao-rubrica-material-grafico")).toBeInTheDocument();
    // Inativa sem pool não recebe dotação nova.
    expect(screen.queryByTestId("dotacao-rubrica-antiga")).not.toBeInTheDocument();
    expect(mocks.fetchPainelOrcamento).toHaveBeenCalledWith({ nivel: "nacional" }, expect.anything());
    expect(screen.getByTestId("dotacao-sem-lancamento")).toBeInTheDocument();
  });

  it("lança a dotação de uma rubrica sem pool com POST nacional", async () => {
    mocks.lancarDotacaoNacional.mockResolvedValue(poolNacional(70, DIARIAS, { aprovado: "1000.00" }));
    renderPage();
    await screen.findByTestId("dotacao-rubrica-diarias");

    expect(screen.getByTestId("dotacao-submit-diarias")).toHaveTextContent("Lançar");
    digitar("diarias", "100000");
    fireEvent.click(screen.getByTestId("dotacao-submit-diarias"));

    const confirmacao = await screen.findByTestId("dotacao-confirmacao");
    expect(within(confirmacao).getByText("Diárias")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("dotacao-confirmar"));

    await waitFor(() => expect(mocks.lancarDotacaoNacional).toHaveBeenCalledWith(1, "1000.00"));
    expect(mocks.atualizarPool).not.toHaveBeenCalled();
    await waitFor(() => expect(mocks.showToast).toHaveBeenCalledWith(expect.stringContaining("Diárias"), "success"));
  });

  it("ajusta com PATCH a rubrica que já tem pool e mostra os totais", async () => {
    mocks.fetchPainelOrcamento.mockResolvedValue([
      poolNacional(50, GRAFICO, { aprovado: "5000.00", distribuido: "2000.00" }),
    ]);
    mocks.atualizarPool.mockResolvedValue(poolNacional(50, GRAFICO, { aprovado: "6000.00" }));
    renderPage();
    await screen.findByTestId("dotacao-rubrica-material-grafico");

    expect(screen.getByTestId("dotacao-total")).toHaveTextContent("5.000,00");
    expect(screen.queryByTestId("dotacao-sem-lancamento")).not.toBeInTheDocument();
    expect(screen.getByTestId("dotacao-submit-material-grafico")).toHaveTextContent("Ajustar");

    digitar("material-grafico", "600000");
    fireEvent.click(screen.getByTestId("dotacao-submit-material-grafico"));
    fireEvent.click(await screen.findByTestId("dotacao-confirmar"));

    await waitFor(() => expect(mocks.atualizarPool).toHaveBeenCalledWith(50, "6000.00"));
    expect(mocks.lancarDotacaoNacional).not.toHaveBeenCalled();
  });

  it("não deixa baixar abaixo do distribuído aos estados mais o consumido", async () => {
    mocks.fetchPainelOrcamento.mockResolvedValue([
      poolNacional(50, GRAFICO, { aprovado: "5000.00", distribuido: "2000.00", comprometido: "500.00" }),
    ]);
    renderPage();
    await screen.findByTestId("dotacao-rubrica-material-grafico");

    digitar("material-grafico", "200000");
    expect(screen.getByTestId("dotacao-submit-material-grafico")).toBeDisabled();
    expect(screen.getByTestId("dotacao-motivo-material-grafico")).toHaveTextContent("2.500,00");

    digitar("material-grafico", "250000");
    expect(screen.getByTestId("dotacao-submit-material-grafico")).toBeEnabled();
  });

  it("não envia o mesmo valor nem zero numa rubrica sem pool", async () => {
    mocks.fetchPainelOrcamento.mockResolvedValue([poolNacional(50, GRAFICO, { aprovado: "5000.00" })]);
    renderPage();
    await screen.findByTestId("dotacao-rubrica-material-grafico");

    digitar("material-grafico", "500000");
    expect(screen.getByTestId("dotacao-submit-material-grafico")).toBeDisabled();
    digitar("diarias", "000");
    expect(screen.getByTestId("dotacao-submit-diarias")).toBeDisabled();
  });

  it("ancora o erro do servidor no campo da rubrica", async () => {
    mocks.lancarDotacaoNacional.mockRejectedValue(
      new ApiError(400, {
        code: "validation_error",
        message: "Valor acima do aprovado.",
        field_errors: [{ field: "valor_alocado", message: "Valor acima do aprovado no TED." }],
      }),
    );
    renderPage();
    await screen.findByTestId("dotacao-rubrica-diarias");

    digitar("diarias", "100000");
    fireEvent.click(screen.getByTestId("dotacao-submit-diarias"));
    fireEvent.click(await screen.findByTestId("dotacao-confirmar"));

    const linha = screen.getByTestId("dotacao-rubrica-diarias");
    expect(await within(linha).findByText("Valor acima do aprovado no TED.")).toBeInTheDocument();
    expect(mocks.showToast).not.toHaveBeenCalled();
  });

  it("recarrega a lista quando outra pessoa já criou o pool da rubrica", async () => {
    mocks.lancarDotacaoNacional.mockRejectedValue(
      new ApiError(400, {
        code: "validation_error",
        message: "Já existe.",
        field_errors: [{ field: "nivel", message: "Já existe um pool para esta rubrica neste nível. Altere o valor dele." }],
      }),
    );
    renderPage();
    await screen.findByTestId("dotacao-rubrica-diarias");
    expect(mocks.fetchPainelOrcamento).toHaveBeenCalledTimes(1);

    digitar("diarias", "100000");
    fireEvent.click(screen.getByTestId("dotacao-submit-diarias"));
    fireEvent.click(await screen.findByTestId("dotacao-confirmar"));

    await waitFor(() => expect(mocks.fetchPainelOrcamento).toHaveBeenCalledTimes(2));
  });

  it("mostra acesso restrito para quem não é UGP nem Super Admin", async () => {
    mocks.perfil = "articulador-estadual";
    renderPage();
    expect(await screen.findByText("Dotação restrita")).toBeInTheDocument();
    expect(mocks.fetchPainelOrcamento).not.toHaveBeenCalled();
    expect(mocks.listRubricas).not.toHaveBeenCalled();
  });
});
