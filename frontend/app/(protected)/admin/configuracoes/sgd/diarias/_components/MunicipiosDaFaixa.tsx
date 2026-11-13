"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { SearchSelect } from "@/app/components/ui/SearchSelect/SearchSelect";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import {
  PADRAO_LABEL,
  buscarMunicipiosComIbge,
  salvarEnquadramentos,
  type Enquadramento,
  type FaixaDestino,
} from "@/app/lib/diarias";
import { qk } from "@/app/lib/queryKeys";

const mesmaLista = (a: Enquadramento[], b: Enquadramento[]) =>
  a.length === b.length && a.every((m, i) => m.codigo_ibge === b[i].codigo_ibge);

const porNome = (a: Enquadramento, b: Enquadramento) =>
  (a.nome_referencia || a.codigo_ibge).localeCompare(b.nome_referencia || b.codigo_ibge, "pt-BR");

/**
 * Municípios enquadrados numa faixa de destino (#366), editáveis. A lista é
 * salva inteira: o backend substitui os enquadramentos da faixa e recusa o
 * município que já está em outra.
 */
export function MunicipiosDaFaixa({ faixa }: { faixa: FaixaDestino }) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const salvos = [...faixa.enquadramentos].sort(porNome);
  const [lista, setLista] = useState<Enquadramento[]>(salvos);
  const [erro, setErro] = useState<string | null>(null);
  const mudou = !mesmaLista(lista, salvos);

  const salvar = useMutation({
    mutationFn: () => salvarEnquadramentos(faixa.id, lista),
    onSuccess: async () => {
      setErro(null);
      await queryClient.invalidateQueries({ queryKey: qk.diarias.faixas });
      showToast(`Municípios de "${faixa.nome}" atualizados.`, "success");
    },
    onError: (e) => {
      setErro(
        e instanceof ApiError
          ? (e.fieldErrors?.find((f) => f.field.startsWith("enquadramentos"))?.message ?? e.message)
          : "Não foi possível salvar os municípios da faixa.",
      );
    },
  });

  function adicionar(municipio: Enquadramento | undefined) {
    if (!municipio) return;
    setErro(null);
    if (lista.some((m) => m.codigo_ibge === municipio.codigo_ibge)) {
      setErro(`${municipio.nome_referencia} já está nesta faixa.`);
      return;
    }
    setLista((atual) => [...atual, municipio].sort(porNome));
  }

  function remover(codigo: string) {
    setErro(null);
    setLista((atual) => atual.filter((m) => m.codigo_ibge !== codigo));
  }

  return (
    <li className="flex flex-col gap-3 px-5 py-4" data-testid={`faixa-municipios-${faixa.id}`}>
      <div>
        <p className="text-sm font-medium text-text">{faixa.nome}</p>
        <p className="mt-0.5 text-xs text-text-muted">
          {faixa.padrao
            ? `${PADRAO_LABEL[faixa.padrao]}, além dos municípios listados aqui.`
            : "Só os municípios listados aqui."}
        </p>
      </div>

      {lista.length === 0 ? (
        <p className="text-sm text-text-muted">Nenhum município enquadrado explicitamente.</p>
      ) : (
        <ul className="flex flex-wrap gap-2" aria-label={`Municípios de ${faixa.nome}`}>
          {lista.map((m) => (
            <li
              key={m.codigo_ibge}
              className="flex items-center gap-1 rounded-full border border-border bg-surface-muted/60 py-0.5 pl-3 pr-1 text-sm text-text"
              data-testid={`faixa-${faixa.id}-municipio-${m.codigo_ibge}`}
            >
              {m.nome_referencia || m.codigo_ibge}
              <button
                type="button"
                onClick={() => remover(m.codigo_ibge)}
                disabled={salvar.isPending}
                aria-label={`Remover ${m.nome_referencia || m.codigo_ibge} de ${faixa.nome}`}
                className="flex h-6 w-6 items-center justify-center rounded-full text-text-muted hover:bg-surface hover:text-text focus-visible:outline-2 focus-visible:outline-primary"
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 basis-64">
          <SearchSelect<Enquadramento>
            label={`Adicionar município a ${faixa.nome}`}
            value={null}
            onChange={(opcao) => adicionar(opcao?.item)}
            search={buscarMunicipiosComIbge}
            queryKey={qk.diarias.municipios}
            placeholder="Buscar município pelo nome"
            emptyText="Nenhum município encontrado."
            disabled={salvar.isPending}
            data-testid={`faixa-${faixa.id}-adicionar`}
          />
        </div>
        {mudou && (
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setLista(salvos);
                setErro(null);
              }}
              disabled={salvar.isPending}
            >
              Desfazer
            </Button>
            <Button
              size="sm"
              onClick={() => salvar.mutate()}
              loading={salvar.isPending}
              data-testid={`faixa-${faixa.id}-salvar`}
            >
              Salvar municípios
            </Button>
          </div>
        )}
      </div>

      {erro && (
        <p role="alert" className="text-sm text-error-text" data-testid={`faixa-${faixa.id}-erro`}>
          {erro}
        </p>
      )}
    </li>
  );
}
