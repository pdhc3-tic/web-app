"use client";

import { useEffect, useState, type DragEvent } from "react";
import { ArrowDown, ArrowUp, GripVertical, Pencil } from "lucide-react";
import { Badge } from "@/app/components/ui/Badge/Badge";
import {
  FORMATO_LABEL,
  type ArloFieldMapping,
  type CampoArlo,
} from "@/app/lib/arloMapping";

type Props = {
  linhas: ArloFieldMapping[];
  camposDaDirecao: CampoArlo[];
  reordenando: boolean;
  permiteReordenar: boolean;
  onEditar: (linha: ArloFieldMapping) => void;
  onMoverCima: (id: number) => void;
  onMoverBaixo: (id: number) => void;
  onReordenarArraste: (idOrigem: number, idDestino: number) => void;
};

/**
 * Tabela do mapeamento de uma direção. Reordenação com HTML5 drag-and-drop
 * nativo e, para teclado/leitor de tela, botões ↑/↓ (equivalentes no efeito).
 *
 * O rótulo do campo e a flag "obrigatório" vêm do catálogo do backend
 * (`GET .../arlo-mapping/campos/`, em `camposDaDirecao`).
 */
export function MapeamentoTabela({
  linhas,
  camposDaDirecao,
  reordenando,
  permiteReordenar,
  onEditar,
  onMoverCima,
  onMoverBaixo,
  onReordenarArraste,
}: Props) {
  const [arrastando, setArrastando] = useState<number | null>(null);
  const [sobre, setSobre] = useState<number | null>(null);
  // Só a linha com a alça pressionada fica `draggable`: o `dragstart` nasce no
  // próprio <tr> (nunca no botão), então é o estado da alça que decide se a
  // linha arrasta — clicar no texto não arrasta nada.
  const [alcaPressionada, setAlcaPressionada] = useState<number | null>(null);

  // Soltar o botão fora da alça (sem arrastar) também desarma a linha; se o
  // arrasto começar, o navegador não manda o pointerup e quem desarma é o dragend.
  useEffect(() => {
    if (alcaPressionada === null) return;
    const desarmar = () => setAlcaPressionada(null);
    window.addEventListener("pointerup", desarmar);
    return () => window.removeEventListener("pointerup", desarmar);
  }, [alcaPressionada]);

  function metaDoCampo(campo: string): CampoArlo | undefined {
    return camposDaDirecao.find((c) => c.campo === campo);
  }

  function onDragStart(id: number) {
    return (e: DragEvent<HTMLTableRowElement>) => {
      setArrastando(id);
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(id));
    };
  }

  function onDragOver(id: number) {
    return (e: DragEvent<HTMLTableRowElement>) => {
      if (arrastando === null || arrastando === id) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      setSobre(id);
    };
  }

  function onDrop(id: number) {
    return (e: DragEvent<HTMLTableRowElement>) => {
      e.preventDefault();
      const origemStr = e.dataTransfer.getData("text/plain");
      const origem = Number(origemStr);
      setArrastando(null);
      setSobre(null);
      if (!Number.isFinite(origem) || origem === id) return;
      onReordenarArraste(origem, id);
    };
  }

  function onDragEnd() {
    setArrastando(null);
    setSobre(null);
    setAlcaPressionada(null);
  }

  return (
    <div
      aria-busy={reordenando}
      className="overflow-hidden rounded-lg border border-border bg-surface"
    >
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-surface-muted/50 text-left text-xs font-medium uppercase tracking-wide text-text-muted">
          <tr>
            {permiteReordenar && <th scope="col" className="w-10 px-2 py-2" aria-label="Reordenar" />}
            <th scope="col" className="w-14 px-2 py-2">Ordem</th>
            <th scope="col" className="px-3 py-2">Campo do SGD</th>
            <th scope="col" className="px-3 py-2">Coluna no Arlo</th>
            <th scope="col" className="px-3 py-2">Formato</th>
            <th scope="col" className="px-3 py-2">Situação</th>
            <th scope="col" className="w-20 px-3 py-2 text-right">Ações</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {linhas.map((linha, index) => {
            const meta = metaDoCampo(linha.campo_sgd);
            const destaque =
              sobre === linha.id && arrastando !== null && arrastando !== linha.id;
            return (
              <tr
                key={linha.id}
                draggable={permiteReordenar && alcaPressionada === linha.id}
                onDragStart={onDragStart(linha.id)}
                onDragOver={onDragOver(linha.id)}
                onDrop={onDrop(linha.id)}
                onDragEnd={onDragEnd}
                className={`transition-colors ${
                  destaque ? "bg-primary/5" : ""
                } ${arrastando === linha.id ? "opacity-60" : ""}`}
                data-testid={`arlo-linha-${linha.campo_sgd}`}
              >
                {permiteReordenar && (
                  <td className="px-2">
                    <button
                      type="button"
                      data-arlo-handle
                      aria-label={`Arrastar para reordenar ${meta?.label ?? linha.campo_sgd}`}
                      className="flex h-8 w-6 cursor-grab items-center justify-center rounded text-text-muted hover:text-text active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                      onPointerDown={() => setAlcaPressionada(linha.id)}
                    >
                      <GripVertical className="h-4 w-4" aria-hidden />
                    </button>
                  </td>
                )}
                <td className="px-2 text-xs text-text-muted">{index + 1}</td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-text">
                      {meta?.label ?? linha.campo_sgd}
                    </span>
                    {meta?.obrigatorio && (
                      <Badge status="info" label="Obrigatório" />
                    )}
                  </div>
                  <p className="text-xs text-text-muted">{linha.campo_sgd}</p>
                </td>
                <td className="px-3 py-2.5">
                  <span className="font-mono text-sm">{linha.coluna_arlo}</span>
                </td>
                <td className="px-3 py-2.5">{FORMATO_LABEL[linha.formato]}</td>
                <td className="px-3 py-2.5">
                  {linha.ativo ? (
                    <Badge status="ativo" label="Ativo" />
                  ) : (
                    <Badge status="inativo" label="Inativo" />
                  )}
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center justify-end gap-1">
                    {permiteReordenar && (
                      <>
                        <button
                          type="button"
                          onClick={() => onMoverCima(linha.id)}
                          disabled={index === 0 || reordenando}
                          className="rounded p-1.5 text-text-muted hover:bg-surface-muted hover:text-text disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                          aria-label={`Mover ${meta?.label ?? linha.campo_sgd} para cima`}
                        >
                          <ArrowUp className="h-4 w-4" aria-hidden />
                        </button>
                        <button
                          type="button"
                          onClick={() => onMoverBaixo(linha.id)}
                          disabled={index === linhas.length - 1 || reordenando}
                          className="rounded p-1.5 text-text-muted hover:bg-surface-muted hover:text-text disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                          aria-label={`Mover ${meta?.label ?? linha.campo_sgd} para baixo`}
                        >
                          <ArrowDown className="h-4 w-4" aria-hidden />
                        </button>
                      </>
                    )}
                    <button
                      type="button"
                      onClick={() => onEditar(linha)}
                      aria-label={`Editar ${meta?.label ?? linha.campo_sgd}`}
                      className="rounded p-1.5 text-text-muted hover:bg-surface-muted hover:text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                    >
                      <Pencil className="h-4 w-4" aria-hidden />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
