import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { rotuloAbrangencia } from "@/app/lib/demandas";
import {
  AvisoForaDoTerritorio,
  PreviaAbrangencia,
  rotuloArticuladores,
  SeloForaDoTerritorio,
} from "./AbrangenciaDemanda";

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
  it("diz a UF da atividade, quem analisa e de onde sai o saldo", () => {
    render(<AvisoForaDoTerritorio demanda={territorial} ufAtividade="RN" />);
    expect(screen.getByTestId("aviso-fora-do-territorio").textContent).toBe(
      "A atividade é em RN. A demanda será analisada pelo Articulador de PB e usará o saldo do seu território (Território Borborema).",
    );
  });

  it("sem a UF da atividade, diz “outro estado”", () => {
    render(<AvisoForaDoTerritorio demanda={territorial} ufAtividade={null} />);
    expect(screen.getByTestId("aviso-fora-do-territorio").textContent).toContain(
      "A atividade é em outro estado.",
    );
  });

  it("demanda estadual usa o saldo do estado", () => {
    render(<AvisoForaDoTerritorio demanda={{ ...territorial, territorio_nome: null }} ufAtividade="RN" />);
    expect(screen.getByTestId("aviso-fora-do-territorio").textContent).toContain(
      "usará o saldo de PB.",
    );
  });

  it("não avisa quando a atividade é do mesmo estado", () => {
    render(
      <AvisoForaDoTerritorio
        demanda={{ ...territorial, atividade_fora_do_territorio: false }}
        ufAtividade="PB"
      />,
    );
    expect(screen.queryByTestId("aviso-fora-do-territorio")).toBeNull();
  });

  it("não avisa demanda nacional", () => {
    render(
      <AvisoForaDoTerritorio
        demanda={{ estado_sigla: null, territorio_nome: null, atividade_fora_do_territorio: true }}
        ufAtividade="RN"
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

describe("rotuloArticuladores (#361)", () => {
  it("lista os nomes, na ordem do backend", () => {
    expect(
      rotuloArticuladores("PB", [
        { id: 1, nome: "Ana Lima" },
        { id: 2, nome: "Bruno Rocha" },
      ]),
    ).toBe("Ana Lima, Bruno Rocha");
  });

  it("estado sem Articulador ativo diz isso em vez de ficar vazio", () => {
    expect(rotuloArticuladores("PB", [])).toBe("Nenhum Articulador Estadual ativo em PB");
  });

  it("demanda nacional não passa por Articulador", () => {
    expect(rotuloArticuladores(null, [])).toBeNull();
  });
});

describe("PreviaAbrangencia (#361)", () => {
  const previa = {
    estado_sigla: "PB",
    territorio: { id: 7, nome: "Território Borborema" },
    articuladores: [{ id: 1, nome: "Ana Lima" }],
    atividade_fora_do_territorio: true,
  };

  it("mostra território, Articulador e o aviso com a UF da atividade", () => {
    render(<PreviaAbrangencia previa={previa} ufAtividade="RN" />);
    expect(screen.getByTestId("previa-territorio").textContent).toBe("Território Borborema (PB)");
    expect(screen.getByTestId("previa-articuladores").textContent).toBe("Ana Lima");
    expect(screen.getByTestId("aviso-fora-do-territorio").textContent).toContain(
      "A atividade é em RN.",
    );
  });

  it("demanda nacional: sem a linha do Articulador e sem aviso", () => {
    render(
      <PreviaAbrangencia
        previa={{ estado_sigla: null, territorio: null, articuladores: [], atividade_fora_do_territorio: false }}
        ufAtividade="RN"
      />,
    );
    expect(screen.getByTestId("previa-territorio").textContent).toBe("Nacional");
    expect(screen.queryByText("Analisada por")).toBeNull();
    expect(screen.queryByTestId("aviso-fora-do-territorio")).toBeNull();
  });
});
