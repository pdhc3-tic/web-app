import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Demanda } from "@/app/lib/demandas";
import { AcoesDecisao } from "./AcoesDecisao";

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { user: { roles: ["ugp"] } }, status: "authenticated" }),
}));

vi.mock("@/app/lib/auth/roles", async (original) => ({
  ...(await original<typeof import("@/app/lib/auth/roles")>()),
  perfisDecisoresSgd: () => ["ugp"],
  canCancelarDemandaAutorizada: () => false,
}));

vi.mock("@/app/components/ui/Select/Select", () => ({
  Select: ({
    id,
    options,
    value,
    onChange,
  }: {
    id: string;
    options: { value: string; label: string }[];
    value: string;
    onChange: (v: string) => void;
  }) => (
    <select data-testid={id} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="" />
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  ),
}));

vi.mock("@/app/lib/hooks/usePoolsDeOrigem", () => ({
  usePoolsDeOrigem: () => ({
    carregando: false,
    falhou: false,
    pools: [
      { id: 5, nivel: "estadual", estado: { nome: "Rio Grande do Norte" }, rubrica: { slug: "diarias", nome: "Diárias" }, saldo_pool: "9000.00" },
    ],
  }),
}));

const trava = { semaforo_antes: "verde", semaforo_apos: "verde", saldo_apos: "100.00" };

vi.mock("@/app/lib/demandas", async (original) => ({
  ...(await original<typeof import("@/app/lib/demandas")>()),
  previewDecisao: vi.fn(async () => ({
    disponivel: true,
    trava_bloqueada: null,
    individual: trava,
    territorial: trava,
    origem: null,
  })),
}));

const demanda = {
  id: 1,
  activity: 2,
  status: "pre_autorizada",
  solicitacoes: [
    {
      id: 11,
      tipo_display: "Diária",
      rubrica_slug: "diarias",
      rubrica_nome: "Diárias",
      valor_estimado: "1000.00",
      valor_autorizado: null,
    },
  ],
} as unknown as Demanda;

function abrirAjuste() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AcoesDecisao demanda={demanda} onDecidido={vi.fn()} onIniciar={vi.fn()} />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByTestId("acao-ajustar"));
}

describe("AcoesDecisao — autorização com excedente (#363)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sem marcar o excedente, confirma com o impacto validado", async () => {
    abrirAjuste();
    await waitFor(() => expect(screen.getByTestId("decisao-confirmar")).toBeEnabled());
  });

  it("marcado, o botão só libera com a origem e a justificativa", async () => {
    abrirAjuste();
    await waitFor(() => expect(screen.getByTestId("decisao-confirmar")).toBeEnabled());

    fireEvent.click(screen.getByTestId("excedente-ativo"));
    expect(screen.getByTestId("excedente-aviso").textContent).toContain("não aumenta o limite individual");
    expect(screen.getByTestId("decisao-confirmar")).toBeDisabled();

    fireEvent.change(screen.getByTestId("excedente-origem"), { target: { value: "5" } });
    expect(screen.getByTestId("decisao-confirmar")).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Justificativa do excedente/), { target: { value: "Mutirão." } });
    await waitFor(() => expect(screen.getByTestId("decisao-confirmar")).toBeEnabled());

    fireEvent.change(screen.getByLabelText(/Justificativa do excedente/), { target: { value: "  " } });
    expect(screen.getByTestId("decisao-confirmar")).toBeDisabled();
  });
});
