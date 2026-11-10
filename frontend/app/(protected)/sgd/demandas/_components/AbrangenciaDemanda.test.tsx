import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { rotuloAbrangencia } from "@/app/lib/demandas";
import { AvisoForaDoTerritorio, SeloForaDoTerritorio } from "./AbrangenciaDemanda";

const territorial = {
  estado_sigla: "PB",
  territorio_nome: "Território Borborema",
  atividade_fora_do_territorio: true,
};

describe("rotuloAbrangencia (#361)", () => {
  it("território com a UF", () => {
    expect(rotuloAbrangencia(territorial)).toBe("Território Borborema (PB)");
  });

  it("só o estado, sem território", () => {
    expect(rotuloAbrangencia({ estado_sigla: "PB", territorio_nome: null })).toBe("PB");
  });

  it("sem estado nem território, é nacional", () => {
    expect(rotuloAbrangencia({ estado_sigla: null, territorio_nome: null })).toBe("Nacional");
  });
});

describe("AvisoForaDoTerritorio (#361)", () => {
  it("diz quem analisa e de onde sai o saldo", () => {
    render(<AvisoForaDoTerritorio demanda={territorial} />);
    expect(screen.getByTestId("aviso-fora-do-territorio").textContent).toBe(
      "A atividade é em outro estado. A demanda será analisada pelo Articulador de PB e usará o saldo do seu território (Território Borborema).",
    );
  });

  it("demanda estadual usa o saldo do estado", () => {
    render(<AvisoForaDoTerritorio demanda={{ ...territorial, territorio_nome: null }} />);
    expect(screen.getByTestId("aviso-fora-do-territorio").textContent).toContain(
      "usará o saldo de PB.",
    );
  });

  it("não avisa quando a atividade é do mesmo estado", () => {
    render(<AvisoForaDoTerritorio demanda={{ ...territorial, atividade_fora_do_territorio: false }} />);
    expect(screen.queryByTestId("aviso-fora-do-territorio")).toBeNull();
  });

  it("não avisa demanda nacional", () => {
    render(
      <AvisoForaDoTerritorio
        demanda={{ estado_sigla: null, territorio_nome: null, atividade_fora_do_territorio: true }}
      />,
    );
    expect(screen.queryByTestId("aviso-fora-do-territorio")).toBeNull();
  });
});

describe("SeloForaDoTerritorio (#361)", () => {
  it("aparece só com a marca do backend", () => {
    const { rerender } = render(<SeloForaDoTerritorio demanda={territorial} />);
    expect(screen.getByTestId("selo-fora-do-territorio").textContent).toBe(
      "Atividade fora do território",
    );
    rerender(<SeloForaDoTerritorio demanda={{ ...territorial, atividade_fora_do_territorio: false }} />);
    expect(screen.queryByTestId("selo-fora-do-territorio")).toBeNull();
  });
});
