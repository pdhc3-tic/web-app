import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import type { Demanda, SolicitacaoDemanda } from "@/app/lib/demandas";
import { SolicitacaoForm } from "./SolicitacaoForm";

/**
 * #440 — sem valor de diária vigente para o destino, o backend recusa o
 * cálculo (simulação e gravação). O formulário não deixa salvar, a não ser na
 * edição que mantém destino e datas: aí o backend usa o valor congelado.
 */

const api = vi.hoisted(() => ({ simular: vi.fn(), atualizar: vi.fn() }));
vi.mock("@/app/lib/solicitacoes", async (original) => ({
  ...(await original<typeof import("@/app/lib/solicitacoes")>()),
  simularDiarias: api.simular,
  atualizarSolicitacao: api.atualizar,
}));
// Os campos de escolha da diária (vínculo, transporte) leem as opções daqui.
vi.mock("@/app/providers/SgpChoicesProvider", () => ({
  useSgpChoices: () => new Proxy({}, { get: () => [] }),
}));
vi.mock("./SaldoSolicitacao", () => ({ SaldoSolicitacao: () => null }));
vi.mock("@/app/lib/hooks/useTiposSolicitacao", () => ({
  useTiposSolicitacao: () => ({
    data: [{ slug: "diaria", nome: "Diárias", ativo: true, schema_campos: null }],
    isPending: false,
    isError: false,
  }),
}));

const SEM_VALOR = "Sem valor de diária vigente para a faixa 'Demais localidades' em 10/12/2026. Contate a FGD ou o Super Admin.";

const demanda = { id: 7, status: "rascunho" } as Demanda;

function diaria(campos: Record<string, unknown> = {}): SolicitacaoDemanda {
  return {
    id: 3,
    demanda: 7,
    tipo: "diaria",
    tipo_display: "Diárias",
    campos_json: {
      beneficiario_nome: "Paulo Rocha",
      beneficiario_cpf: "52998224725",
      beneficiario_cargo: "Facilitador",
      beneficiario_vinculo: "colaborador_externo",
      meio_transporte: "rodoviario",
      municipio_destino_id: 12,
      data_inicio: "2026-12-10",
      data_fim: "2026-12-12",
      hospedagem_custeada: false,
      justificativa: "Encontro.",
      ...campos,
    },
    valor_estimado: "750.00",
    anexos: {},
  } as unknown as SolicitacaoDemanda;
}

function renderizar(solicitacao: SolicitacaoDemanda) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <SolicitacaoForm demanda={demanda} solicitacao={solicitacao} onClose={vi.fn()} onSalvo={vi.fn()} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  api.simular.mockReset().mockRejectedValue(
    new ApiError(400, {
      code: "BUSINESS_RULE",
      message: SEM_VALOR,
      field_errors: [{ field: "valor_por_diaria", message: SEM_VALOR }],
    }),
  );
  api.atualizar.mockReset();
});

describe("SolicitacaoForm — diária sem valor vigente (#440)", () => {
  it("bloqueia o Salvar com o motivo quando o backend recusa o cálculo", async () => {
    renderizar(diaria());

    expect(await screen.findByTestId("simulacao-diarias-bloqueio")).toHaveTextContent("não pode ser salva");
    expect(screen.getByTestId("solicitacao-salvar")).toBeDisabled();
    expect(screen.getByTestId("solicitacao-bloqueio")).toBeInTheDocument();
  });

  it("na edição que mantém destino e datas, o valor congelado vale e salvar é permitido", async () => {
    renderizar(diaria({ tabela_diaria_id: 3, valor_total: "750.00" }));

    expect(await screen.findByTestId("simulacao-diarias-bloqueio")).toHaveTextContent("continua valendo");
    expect(screen.getByTestId("solicitacao-salvar")).toBeEnabled();
    expect(screen.queryByTestId("solicitacao-bloqueio")).toBeNull();
  });

  it("mudar a data na edição congelada passa a bloquear", async () => {
    renderizar(diaria({ tabela_diaria_id: 3, valor_total: "750.00" }));
    await screen.findByTestId("simulacao-diarias-bloqueio");

    fireEvent.change(screen.getByLabelText(/Data de volta/), { target: { value: "2026-12-13" } });

    await waitFor(() => expect(screen.getByTestId("solicitacao-salvar")).toBeDisabled());
    expect(screen.getByTestId("simulacao-diarias-bloqueio")).toHaveTextContent("não pode ser salva");
  });

  it("com o cálculo aceito, salva normalmente", async () => {
    api.simular.mockResolvedValue({
      faixa_destino: { id: 3, nome: "Demais localidades" },
      valor_por_diaria: "300.00",
      numero_diarias: "2.5",
      adicional_embarque: "0.00",
      valor_total: "750.00",
    });
    renderizar(diaria());

    expect(await screen.findByTestId("simulacao-diarias-total")).toHaveTextContent("750,00");
    expect(screen.getByTestId("solicitacao-salvar")).toBeEnabled();
  });
});
