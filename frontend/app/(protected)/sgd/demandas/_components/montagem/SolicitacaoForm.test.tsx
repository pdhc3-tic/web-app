import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Demanda, SolicitacaoDemanda } from "@/app/lib/demandas";
import type { SchemaCampos } from "@/app/lib/tiposSolicitacao";
import { SolicitacaoForm } from "./SolicitacaoForm";

/**
 * #365, revisão do PR #426: os envios de anexo em curso seguram Salvar, e um
 * envio que termina depois de o formulário fechar é apagado, sem ficar solto.
 */

const enviar = vi.fn();
const remover = vi.fn();
const atualizar = vi.fn();
const criar = vi.fn();
vi.mock("@/app/lib/solicitacoes", async (original) => ({
  ...(await original<typeof import("@/app/lib/solicitacoes")>()),
  enviarDocumentoDemanda: (...args: unknown[]) => enviar(...args),
  removerDocumentoDemanda: (...args: unknown[]) => remover(...args),
  atualizarSolicitacao: (...args: unknown[]) => atualizar(...args),
  criarSolicitacao: (...args: unknown[]) => criar(...args),
}));
vi.mock("@/app/providers/SgpChoicesProvider", () => ({ useSgpChoices: () => ({}) }));
// O saldo de verdade tem teste próprio; aqui só o atalho do recurso extra (#467).
vi.mock("./SaldoSolicitacao", () => ({
  SaldoSolicitacao: ({
    onRecursoExtra,
  }: {
    onRecursoExtra?: (b: { disponivel: string; solicitado: string }) => void;
  }) =>
    onRecursoExtra ? (
      <button type="button" onClick={() => onRecursoExtra({ disponivel: "40.00", solicitado: "100.00" })}>
        atalho do recurso extra
      </button>
    ) : null,
}));

const SCHEMA: SchemaCampos = {
  type: "object",
  properties: { reserva: { type: "integer", format: "anexo", title: "Comprovante", "x-ordem": 1 } },
};
vi.mock("@/app/lib/hooks/useTiposSolicitacao", () => ({
  useTiposSolicitacao: () => ({
    data: [{ slug: "hospedagem", nome: "Hospedagem", ativo: true, schema_campos: SCHEMA }],
    isPending: false,
    isError: false,
  }),
}));

const demanda = { id: 7, status: "rascunho" } as Demanda;
const solicitacao = {
  id: 3,
  demanda: 7,
  tipo: "hospedagem",
  tipo_display: "Hospedagem",
  campos_json: {},
  valor_estimado: "100.00",
  anexos: {},
} as unknown as SolicitacaoDemanda;

const pdf = new File(["%PDF-1.4"], "reserva.pdf", { type: "application/pdf" });

function renderizar(onClose = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SolicitacaoForm demanda={demanda} solicitacao={solicitacao} onClose={onClose} onSalvo={vi.fn()} />
    </QueryClientProvider>,
  );
  return onClose;
}

async function enviarPendente() {
  let concluir: (doc: { id: number; nome_original: string }) => void = () => {};
  enviar.mockReturnValueOnce(new Promise((r) => (concluir = r)));
  // O SlideOver monta no quadro seguinte (requestAnimationFrame).
  const input = (await screen.findByTestId("campo-reserva")).querySelector("input[type=file]") as HTMLInputElement;
  fireEvent.change(input, { target: { files: [pdf] } });
  return (id: number) => concluir({ id, nome_original: "reserva.pdf" });
}

beforeEach(() => {
  enviar.mockReset();
  remover.mockReset().mockResolvedValue(undefined);
  atualizar.mockReset();
  criar.mockReset();
});

describe("SolicitacaoForm — anexos em envio (#365)", () => {
  it("Salvar espera o envio terminar", async () => {
    renderizar();
    const concluir = await enviarPendente();
    const salvar = screen.getByTestId("solicitacao-salvar") as HTMLButtonElement;

    await waitFor(() => expect(salvar.disabled).toBe(true));
    expect(screen.getByText("Aguarde o envio do arquivo.")).toBeTruthy();
    fireEvent.click(salvar);
    expect(atualizar).not.toHaveBeenCalled();

    concluir(41);
    await screen.findByText("reserva.pdf");
    await waitFor(() => expect(salvar.disabled).toBe(false));
    expect(screen.queryByText("Aguarde o envio do arquivo.")).toBeNull();
  });

  it("durante o salvamento o campo não aceita arquivo nem retirada (salvar → upload, revisão do #426)", async () => {
    let responder: (s: SolicitacaoDemanda) => void = () => {};
    atualizar.mockReturnValueOnce(new Promise((r) => (responder = r)));
    const onSalvo = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SolicitacaoForm
          demanda={demanda}
          solicitacao={{
            ...solicitacao,
            campos_json: { reserva: 41 },
            anexos: { reserva: { id: 41, nome_original: "reserva.pdf", download: "/x" } },
          } as unknown as SolicitacaoDemanda}
          onClose={vi.fn()}
          onSalvo={onSalvo}
        />
      </QueryClientProvider>,
    );
    const retirar = (await screen.findByRole("button", { name: "Retirar reserva.pdf" })) as HTMLButtonElement;
    expect(retirar.disabled).toBe(false);

    fireEvent.click(screen.getByTestId("solicitacao-salvar"));
    await waitFor(() => expect(atualizar).toHaveBeenCalled());
    expect(atualizar.mock.calls[0][2]).toMatchObject({ campos_json: { reserva: 41 } });
    // O payload já saiu: retirar agora não mudaria o que foi enviado.
    await waitFor(() => expect(retirar.disabled).toBe(true));

    responder({ ...solicitacao, campos_json: { reserva: 41 } } as unknown as SolicitacaoDemanda);
    await waitFor(() => expect(onSalvo).toHaveBeenCalled());
    // O anexo do payload ficou ligado à solicitação: nada foi apagado.
    expect(remover).not.toHaveBeenCalled();
  });

  it("com o campo vazio, salvar desabilita o envio até a resposta", async () => {
    let responder: (s: SolicitacaoDemanda) => void = () => {};
    atualizar.mockReturnValueOnce(new Promise((r) => (responder = r)));
    renderizar();
    const campo = await screen.findByTestId("campo-reserva");
    const input = () => campo.querySelector("input[type=file]") as HTMLInputElement;
    expect(input().disabled).toBe(false);

    fireEvent.click(screen.getByTestId("solicitacao-salvar"));
    await waitFor(() => expect(input().disabled).toBe(true));
    fireEvent.change(input(), { target: { files: [pdf] } });
    expect(enviar).not.toHaveBeenCalled();

    responder(solicitacao);
  });

  it("numa solicitação nova, o tipo não pode ser trocado durante o salvamento", async () => {
    let responder: (s: SolicitacaoDemanda) => void = () => {};
    criar.mockReturnValueOnce(new Promise((r) => (responder = r)));
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SolicitacaoForm demanda={demanda} solicitacao={null} onClose={vi.fn()} onSalvo={vi.fn()} />
      </QueryClientProvider>,
    );
    const tipo = (await screen.findByRole("combobox", { name: /Tipo de solicitação/ })) as HTMLButtonElement;
    fireEvent.click(tipo);
    fireEvent.mouseDown(await screen.findByRole("option", { name: "Hospedagem" }));
    fireEvent.change(await screen.findByLabelText(/Valor estimado/), { target: { value: "10000" } });

    fireEvent.click(screen.getByTestId("solicitacao-salvar"));
    await waitFor(() => expect(criar).toHaveBeenCalled());
    // Trocar o tipo agora descartaria anexos que estão no payload a caminho.
    expect(tipo.disabled).toBe(true);

    responder(solicitacao);
  });

  it("cancelar durante o envio apaga o arquivo quando ele chega", async () => {
    const onClose = renderizar();
    const concluir = await enviarPendente();

    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onClose).toHaveBeenCalled();
    expect(remover).not.toHaveBeenCalled();

    concluir(42);
    await waitFor(() => expect(remover).toHaveBeenCalledWith(7, 42));
  });
});

describe("SolicitacaoForm — atalho Solicitar recurso extra (#467)", () => {
  it("salva a solicitação e devolve o bloqueio para abrir o pedido", async () => {
    atualizar.mockResolvedValueOnce(solicitacao);
    const onSalvo = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SolicitacaoForm demanda={demanda} solicitacao={solicitacao} onClose={vi.fn()} onSalvo={onSalvo} />
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "atalho do recurso extra" }));
    await waitFor(() => expect(onSalvo).toHaveBeenCalled());
    expect(atualizar).toHaveBeenCalledTimes(1);
    expect(onSalvo).toHaveBeenCalledWith(solicitacao, false, { disponivel: "40.00", solicitado: "100.00" });
  });

  it("o Salvar comum não pede o recurso extra", async () => {
    atualizar.mockResolvedValueOnce(solicitacao);
    const onSalvo = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SolicitacaoForm demanda={demanda} solicitacao={solicitacao} onClose={vi.fn()} onSalvo={onSalvo} />
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("solicitacao-salvar"));
    await waitFor(() => expect(onSalvo).toHaveBeenCalled());
    expect(onSalvo).toHaveBeenCalledWith(solicitacao, false, undefined);
  });

  it("se salvar falhar, o pedido não abre", async () => {
    const { ApiError } = await import("@/app/lib/api");
    atualizar.mockRejectedValueOnce(new ApiError(400, { code: "X", message: "Recusado pelo backend." }));
    const onSalvo = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SolicitacaoForm demanda={demanda} solicitacao={solicitacao} onClose={vi.fn()} onSalvo={onSalvo} />
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "atalho do recurso extra" }));
    expect(await screen.findByText("Recusado pelo backend.")).toBeTruthy();
    expect(onSalvo).not.toHaveBeenCalled();
  });
});
