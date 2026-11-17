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
vi.mock("@/app/lib/solicitacoes", async (original) => ({
  ...(await original<typeof import("@/app/lib/solicitacoes")>()),
  enviarDocumentoDemanda: (...args: unknown[]) => enviar(...args),
  removerDocumentoDemanda: (...args: unknown[]) => remover(...args),
  atualizarSolicitacao: (...args: unknown[]) => atualizar(...args),
}));
vi.mock("@/app/providers/SgpChoicesProvider", () => ({ useSgpChoices: () => ({}) }));
vi.mock("./SaldoSolicitacao", () => ({ SaldoSolicitacao: () => null }));

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
