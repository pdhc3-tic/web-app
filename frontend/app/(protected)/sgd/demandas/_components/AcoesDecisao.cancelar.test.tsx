import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Demanda, StatusDemanda } from "@/app/lib/demandas";
import { AcoesDecisao } from "./AcoesDecisao";

/** #456 — o solicitante cancela a própria demanda antes da autorização. */

const SOLICITANTE = 7;

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { user: { id: "7", perfis: [] } }, status: "authenticated" }),
}));

vi.mock("@/app/lib/auth/roles", async (original) => ({
  ...(await original<typeof import("@/app/lib/auth/roles")>()),
  perfisDecisoresSgd: () => [],
  canCancelarDemandaAutorizada: () => false,
}));

// Trocada a cada teste: um `vi.fn` do `vi.hoisted` que rejeita reprova o teste
// mesmo com o erro tratado (Vitest 4).
const api = vi.hoisted(() => ({
  cancelar: (() => Promise.resolve()) as (id: number, justificativa: string) => Promise<unknown>,
}));
vi.mock("@/app/lib/demandas", async (original) => ({
  ...(await original<typeof import("@/app/lib/demandas")>()),
  cancelarDemanda: (id: number, justificativa: string) => api.cancelar(id, justificativa),
}));

function demanda(status: StatusDemanda, solicitante = SOLICITANTE): Demanda {
  return { id: 1, titulo: "Oficina de manejo", activity: 2, status, solicitante, solicitacoes: [] } as unknown as Demanda;
}

function montar(d: Demanda) {
  const onDecidido = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AcoesDecisao demanda={d} onDecidido={onDecidido} onIniciar={vi.fn()} />
    </QueryClientProvider>,
  );
  return onDecidido;
}

let cancelar = vi.fn();
beforeEach(() => {
  cancelar = vi.fn();
  api.cancelar = (id, justificativa) => cancelar(id, justificativa);
});

describe("AcoesDecisao — cancelar pelo solicitante (#456)", () => {
  it.each(["rascunho", "submetida", "devolvida", "pre_autorizada"] as const)(
    "o solicitante vê Cancelar em %s",
    (status) => {
      montar(demanda(status));
      expect(screen.getByTestId("acao-cancelar-solicitante")).toBeInTheDocument();
    },
  );

  it.each(["autorizada", "em_atendimento", "concluida", "recusada", "cancelada"] as const)(
    "o solicitante não cancela em %s",
    (status) => {
      montar(demanda(status));
      expect(screen.queryByTestId("acao-cancelar-solicitante")).toBeNull();
    },
  );

  it("quem não é o solicitante não vê o botão", () => {
    montar(demanda("rascunho", 99));
    expect(screen.queryByTestId("acao-cancelar-solicitante")).toBeNull();
  });

  it("cancela sem justificativa: ela é opcional", async () => {
    const cancelada = { ...demanda("rascunho"), status: "cancelada" };
    cancelar.mockResolvedValue(cancelada);
    const onDecidido = montar(demanda("rascunho"));

    fireEvent.click(screen.getByTestId("acao-cancelar-solicitante"));
    const drawer = await screen.findByTestId("cancelar-solicitante-drawer");
    // Rascunho não reservou saldo: a confirmação não fala em liberar.
    expect(drawer).not.toHaveTextContent("saldo reservado");
    fireEvent.click(screen.getByTestId("cancelar-solicitante-drawer-confirmar"));

    await waitFor(() => expect(cancelar).toHaveBeenCalledWith(1, ""));
    expect(onDecidido).toHaveBeenCalledWith({ tipo: "info", texto: "Demanda cancelada." });
  });

  it("depois da submissão, avisa que o saldo reservado volta", async () => {
    montar(demanda("submetida"));
    fireEvent.click(screen.getByTestId("acao-cancelar-solicitante"));
    expect(await screen.findByTestId("cancelar-solicitante-drawer")).toHaveTextContent(
      "O saldo reservado na submissão volta a ficar disponível.",
    );
  });

  it("a recusa do backend aparece no drawer, que continua aberto", async () => {
    cancelar.mockRejectedValue(new Error("x"));
    montar(demanda("submetida"));
    fireEvent.click(screen.getByTestId("acao-cancelar-solicitante"));
    fireEvent.click(await screen.findByTestId("cancelar-solicitante-drawer-confirmar"));
    expect(await screen.findByText("Não foi possível registrar a decisão. Tente novamente.")).toBeInTheDocument();
    expect(screen.getByTestId("cancelar-solicitante-drawer")).toBeInTheDocument();
  });
});
