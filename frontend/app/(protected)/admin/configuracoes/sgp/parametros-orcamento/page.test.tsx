import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import type { ConfigDoSistema } from "@/app/lib/parametrosOrcamento";
import ParametrosOrcamentoPage from "./page";

/** #403: parâmetros globais do orçamento, contra o formato real do backend. */

const mocks = vi.hoisted(() => ({
  superAdmin: { loading: false, isSuperAdmin: true },
  showToast: vi.fn(),
  fetchConfigs: vi.fn(),
  salvarConfig: vi.fn(),
}));

vi.mock("@/app/lib/auth/roles", () => ({
  useIsSuperAdmin: () => mocks.superAdmin,
}));

vi.mock("@/app/components/layout/PageHeader", () => ({
  PageHeader: ({ children }: { children: React.ReactNode }) => <header>{children}</header>,
}));

vi.mock("@/app/components/ui/Toast/Toast", () => ({
  useToast: () => ({ showToast: mocks.showToast }),
}));

vi.mock("@/app/lib/parametrosOrcamento", async () => {
  const atual = await vi.importActual<typeof import("@/app/lib/parametrosOrcamento")>(
    "@/app/lib/parametrosOrcamento",
  );
  return { ...atual, fetchConfigs: mocks.fetchConfigs, salvarConfig: mocks.salvarConfig };
});

function config(chave: string, valor: ConfigDoSistema["valor"], tipo: string): ConfigDoSistema {
  return { chave, valor, tipo, descricao: "", atualizado_por: null, atualizado_em: null };
}

/** Como o `SystemConfigSerializer` devolve: inteiro e booleano já convertidos. */
const CONFIGS = [
  config("budget_limit_period", "trimestral", "string"),
  config("budget_limit_carry_over", false, "boolean"),
  config("budget_overallocation_allowed", true, "boolean"),
  config("budget_subexec_alert_months", 6, "integer"),
  config("budget_subexec_min_pct", 60, "integer"),
  config("budget_transfer_alert_pct", 25, "integer"),
];

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ParametrosOrcamentoPage />
    </QueryClientProvider>,
  );
}

const controle = (chave: string) => document.getElementById(`parametro-${chave}`) as HTMLInputElement;

describe("ParametrosOrcamentoPage (#403)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.superAdmin = { loading: false, isSuperAdmin: true };
    mocks.fetchConfigs.mockResolvedValue(CONFIGS);
    mocks.salvarConfig.mockResolvedValue(config("budget_subexec_min_pct", 70, "integer"));
  });

  it("mostra os seis parâmetros com os valores tipados do backend", async () => {
    renderPage();
    await screen.findByTestId("parametros-orcamento");

    expect(controle("budget_limit_period").value).toBe("trimestral");
    expect(controle("budget_limit_carry_over").value).toBe("false");
    expect(controle("budget_overallocation_allowed").value).toBe("true");
    expect(controle("budget_subexec_alert_months").value).toBe("6");
    expect(controle("budget_subexec_min_pct").value).toBe("60");
    expect(controle("budget_transfer_alert_pct").value).toBe("25");
    expect(screen.getByTestId("parametro-salvar-budget_subexec_min_pct")).toBeDisabled();
  });

  it("valida tipo e faixa antes de deixar salvar", async () => {
    renderPage();
    await screen.findByTestId("parametros-orcamento");
    const salvar = screen.getByTestId("parametro-salvar-budget_subexec_min_pct");

    fireEvent.change(controle("budget_subexec_min_pct"), { target: { value: "abc" } });
    expect(screen.getByTestId("parametro-erro-budget_subexec_min_pct")).toHaveTextContent(
      "Informe um número inteiro.",
    );
    expect(salvar).toBeDisabled();

    fireEvent.change(controle("budget_subexec_min_pct"), { target: { value: "150" } });
    expect(screen.getByTestId("parametro-erro-budget_subexec_min_pct")).toHaveTextContent(
      "Informe um valor entre 1 e 100.",
    );
    expect(salvar).toBeDisabled();
  });

  it("salva o valor como texto e avisa", async () => {
    renderPage();
    await screen.findByTestId("parametros-orcamento");

    fireEvent.change(controle("budget_subexec_min_pct"), { target: { value: " 70 " } });
    fireEvent.click(screen.getByTestId("parametro-salvar-budget_subexec_min_pct"));

    await waitFor(() => expect(mocks.salvarConfig).toHaveBeenCalledWith("budget_subexec_min_pct", "70"));
    await waitFor(() =>
      expect(mocks.showToast).toHaveBeenCalledWith('"Execução mínima esperada" atualizado.', "success"),
    );
  });

  it("mostra a recusa do servidor no campo", async () => {
    mocks.salvarConfig.mockRejectedValue(
      new ApiError(400, {
        code: "validation_error",
        message: "Valor inválido.",
        field_errors: [{ field: "valor", message: "Valor inválido para tipo INTEGER." }],
      }),
    );
    renderPage();
    await screen.findByTestId("parametros-orcamento");

    fireEvent.change(controle("budget_subexec_min_pct"), { target: { value: "70" } });
    fireEvent.click(screen.getByTestId("parametro-salvar-budget_subexec_min_pct"));

    expect(await screen.findByTestId("parametro-erro-budget_subexec_min_pct")).toHaveTextContent(
      "Valor inválido para tipo INTEGER.",
    );
  });

  it("parâmetro ausente no backend fica desabilitado, com aviso", async () => {
    mocks.fetchConfigs.mockResolvedValue(CONFIGS.filter((c) => c.chave !== "budget_transfer_alert_pct"));
    renderPage();
    await screen.findByTestId("parametros-orcamento");

    expect(controle("budget_transfer_alert_pct")).toBeDisabled();
    expect(screen.getByTestId("parametro-budget_transfer_alert_pct")).toHaveTextContent(
      "Parâmetro ainda não cadastrado no backend.",
    );
  });

  it("quem não é Super Admin não vê os parâmetros", () => {
    mocks.superAdmin = { loading: false, isSuperAdmin: false };
    renderPage();

    expect(screen.queryByTestId("parametros-orcamento")).toBeNull();
    expect(mocks.fetchConfigs).not.toHaveBeenCalled();
  });
});
