import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SaldoConsulta, TravaSaldo } from "@/app/lib/solicitacoes";
import { SaldoSolicitacao } from "./SaldoSolicitacao";

/**
 * #467: o aviso do limite individual manda "usar a opção Solicitar recurso
 * extra"; o botão fica junto dele, só quando o backend sugere essa saída.
 */

const consultar = vi.fn();
vi.mock("@/app/lib/solicitacoes", async (original) => ({
  ...(await original<typeof import("@/app/lib/solicitacoes")>()),
  consultarSaldo: (...args: unknown[]) => consultar(...args),
}));
// Sem espera: o valor vai direto para a consulta.
vi.mock("@/app/lib/hooks/useDebounced", () => ({ useDebounced: <T,>(v: T) => v }));

const livre: TravaSaldo = {
  disponivel: true,
  saldo: "5000.00",
  motivo_bloqueio: null,
  acao_sugerida: null,
  semaforo_atual: "verde",
  semaforo_apos: "verde",
};

function saldo(individual: Partial<TravaSaldo>, territorial: Partial<TravaSaldo> = {}): SaldoConsulta {
  return {
    rubrica_slug: "diarias",
    rubrica_nome: "Diárias",
    individual: { ...livre, ...individual },
    territorial: { ...livre, ...territorial },
    disponivel: false,
    trava_bloqueada: "individual",
  };
}

const BLOQUEIO_INDIVIDUAL: Partial<TravaSaldo> = {
  disponivel: false,
  saldo: "40.00",
  motivo_bloqueio: "Limite individual insuficiente: R$ 40,00 disponível, R$ 100,00 solicitado. Use a opção 'Solicitar recurso extra'.",
  acao_sugerida: "solicitar_recurso_extra",
};

function renderizar(onRecursoExtra?: (b: { disponivel: string; solicitado: string }) => void, desabilitado = false) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SaldoSolicitacao
        tipo="diaria"
        valor="100.00"
        devolvida={false}
        onRecursoExtra={onRecursoExtra}
        recursoExtraDesabilitado={desabilitado}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => consultar.mockReset());

describe("SaldoSolicitacao — atalho do recurso extra (#467)", () => {
  it("bloqueio no limite individual: o botão abre o pedido com o disponível e o solicitado", async () => {
    consultar.mockResolvedValue(saldo(BLOQUEIO_INDIVIDUAL));
    const onRecursoExtra = vi.fn();
    renderizar(onRecursoExtra);
    fireEvent.click(await screen.findByTestId("saldo-recurso-extra"));
    expect(onRecursoExtra).toHaveBeenCalledWith({ disponivel: "40.00", solicitado: "100.00" });
    expect(screen.getByText("A solicitação é salva antes de abrir o pedido.")).toBeTruthy();
  });

  it("com o formulário ocupado (Salvar comum, anexo subindo), o atalho fica desabilitado", async () => {
    consultar.mockResolvedValue(saldo(BLOQUEIO_INDIVIDUAL));
    renderizar(vi.fn(), true);
    expect(((await screen.findByTestId("saldo-recurso-extra")) as HTMLButtonElement).disabled).toBe(true);
  });

  it("sem o callback, só o aviso", async () => {
    consultar.mockResolvedValue(saldo(BLOQUEIO_INDIVIDUAL));
    renderizar();
    expect(await screen.findByText(/Use a opção 'Solicitar recurso extra'/)).toBeTruthy();
    expect(screen.queryByTestId("saldo-recurso-extra")).toBeNull();
  });

  it("bloqueio só na verba do território: sem atalho, quem remaneja é o Articulador", async () => {
    consultar.mockResolvedValue(
      saldo({}, { disponivel: false, saldo: "0.00", motivo_bloqueio: "Verba do território insuficiente.", acao_sugerida: "acionar_articulador" }),
    );
    renderizar(vi.fn());
    expect(await screen.findByText("Verba do território insuficiente.")).toBeTruthy();
    expect(screen.queryByTestId("saldo-recurso-extra")).toBeNull();
  });

  it("dentro do limite: sem atalho", async () => {
    consultar.mockResolvedValue(saldo({}));
    renderizar(vi.fn());
    expect(await screen.findByTestId("saldo-individual")).toBeTruthy();
    expect(screen.queryByTestId("saldo-recurso-extra")).toBeNull();
  });
});
