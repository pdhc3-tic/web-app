import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SearchSelect } from "./SearchSelect";

/**
 * Debounce da busca textual (#323): digitar várias teclas seguidas não dispara
 * uma busca por tecla, só uma depois que o texto para de mudar por 300 ms.
 * A busca é a prop `search` do componente; aqui ela só registra as chamadas.
 */

function renderBusca(search: (texto: string) => Promise<never[]>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SearchSelect<never>
        label="Atividade"
        value={null}
        onChange={() => {}}
        search={search}
        queryKey={(texto) => ["teste", "busca", texto]}
        data-testid="busca"
      />
    </QueryClientProvider>,
  );
  return screen.getByTestId("busca");
}

/** Avança o relógio falso e deixa o React Query e o React processarem. */
async function avancar(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("SearchSelect — debounce da busca", () => {
  it("quatro teclas seguidas viram uma busca só, depois do debounce", async () => {
    const search = vi.fn<(texto: string) => Promise<never[]>>(async () => []);
    const campo = renderBusca(search);

    // Abrir o campo busca a lista inicial (texto vazio).
    fireEvent.focus(campo);
    await avancar(0);
    expect(search.mock.calls.map(([texto]) => texto)).toEqual([""]);

    for (const texto of ["a", "at", "ati", "ativ"]) {
      fireEvent.change(campo, { target: { value: texto } });
      await avancar(100);
    }
    // Ainda dentro dos 300 ms desde a última tecla: nenhuma busca nova.
    expect(search.mock.calls.map(([texto]) => texto)).toEqual([""]);

    await avancar(300);
    expect(search.mock.calls.map(([texto]) => texto)).toEqual(["", "ativ"]);
  });

  it("parar de digitar no meio e continuar depois gera uma busca por pausa", async () => {
    const search = vi.fn<(texto: string) => Promise<never[]>>(async () => []);
    const campo = renderBusca(search);
    fireEvent.focus(campo);
    await avancar(0);

    fireEvent.change(campo, { target: { value: "fei" } });
    await avancar(300);
    fireEvent.change(campo, { target: { value: "feir" } });
    await avancar(100);
    fireEvent.change(campo, { target: { value: "feira" } });
    await avancar(300);

    expect(search.mock.calls.map(([texto]) => texto)).toEqual(["", "fei", "feira"]);
  });
});
