import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import { SolicitarRecursoExtra } from "./SolicitarRecursoExtra";

/**
 * Fluxo guiado "Solicitar recurso extra" (#321). A entrada pela submissão
 * bloqueada é da #295; aqui o componente é aberto direto com o bloqueio.
 */

// `solicitar` só registra a chamada; `resposta` é a função comum que responde.
// Um vi.fn com implementação que rejeita faz o Vitest reprovar o teste mesmo
// com o erro tratado pelo componente.
const api = vi.hoisted(() => ({
  solicitar: vi.fn(),
  resposta: (() => Promise.resolve({})) as () => Promise<unknown>,
}));

vi.mock("@/app/lib/remanejamentos", async (original) => ({
  ...(await original<typeof import("@/app/lib/remanejamentos")>()),
  solicitarRecursoExtra: (...args: unknown[]) => {
    api.solicitar(...args);
    return api.resposta();
  },
}));

const bloqueio = {
  solicitacaoId: 11,
  rubrica: { slug: "locacao-veiculo", nome: "Locação de veículo" },
  disponivel: "1000.00",
  solicitado: "1200.00",
  valorFaltante: null as string | null,
};

function renderFluxo(onEnviado = vi.fn(), valorFaltante: string | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SolicitarRecursoExtra
        open
        demanda={{ id: 47, titulo: "Van da comitiva" }}
        bloqueio={{ ...bloqueio, valorFaltante }}
        onClose={vi.fn()}
        onEnviado={onEnviado}
      />
    </QueryClientProvider>,
  );
  return onEnviado;
}

beforeEach(() => api.solicitar.mockReset());

describe("SolicitarRecursoExtra", () => {
  it("mostra o disponível e o solicitado do bloqueio e exige justificativa antes da revisão", async () => {
    renderFluxo();
    expect(await screen.findByTestId("recurso-extra-bloqueio")).toHaveTextContent(
      "Limite individual insuficiente: R$ 1.000,00 disponível, R$ 1.200,00 solicitado.",
    );
    // Sem valor_faltante do backend, o valor fica para o sistema calcular.
    expect(screen.getByText(/calculado pelo sistema ao registrar o pedido/)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("recurso-extra-revisar"));
    expect(screen.getByText("A justificativa é obrigatória.")).toBeInTheDocument();
    expect(screen.queryByTestId("recurso-extra-enviar")).not.toBeInTheDocument();
  });

  it("revisa, envia sem valor (o backend usa o que falta) e mostra o valor registrado", async () => {
    api.resposta = async () => ({ id: 5, valor_solicitado: "1800.00", status: "submetida" });
    const onEnviado = renderFluxo();

    fireEvent.change(await screen.findByLabelText(/Justificativa/), {
      target: { value: "  Comitiva maior que o previsto.  " },
    });
    fireEvent.click(screen.getByTestId("recurso-extra-revisar"));
    expect(screen.getByText("Confira o pedido antes de enviar.")).toBeInTheDocument();
    expect(api.solicitar).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("recurso-extra-enviar"));

    await waitFor(() => expect(screen.getByTestId("recurso-extra-enviado")).toBeInTheDocument());
    expect(api.solicitar).toHaveBeenCalledWith(47, {
      rubrica: "locacao-veiculo",
      justificativa: "Comitiva maior que o previsto.",
    });
    expect(screen.getByText("R$ 1.800,00")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Acompanhar o pedido #5" })).toHaveAttribute(
      "href",
      "/sgd/remanejamentos/5",
    );
    expect(onEnviado).toHaveBeenCalledWith(expect.objectContaining({ id: 5 }));
  });

  it("com o valor que falta informado pelo backend, já o mostra preenchido", async () => {
    renderFluxo(vi.fn(), "200.00");
    expect(await screen.findByText("R$ 200,00")).toBeInTheDocument();
    expect(screen.queryByText(/calculado pelo sistema/)).not.toBeInTheDocument();
  });

  it("mostra o erro do backend e continua na revisão", async () => {
    api.resposta = async () => {
      throw new ApiError(400, {
        code: "validation_error",
        message: "Já existe um pedido de recurso extra em andamento nesta rubrica.",
      });
    };
    renderFluxo();

    fireEvent.change(await screen.findByLabelText(/Justificativa/), { target: { value: "Motivo." } });
    fireEvent.click(screen.getByTestId("recurso-extra-revisar"));
    fireEvent.click(screen.getByTestId("recurso-extra-enviar"));

    expect(await screen.findByTestId("recurso-extra-erro")).toHaveTextContent(
      "Já existe um pedido de recurso extra em andamento nesta rubrica.",
    );
    expect(screen.getByTestId("recurso-extra-enviar")).toBeInTheDocument();
  });
});
