"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, PlugZap, Plus } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { useIsSuperAdmin } from "@/app/lib/auth/roles";
import {
  DIRECAO_LABEL,
  fetchCamposArloMapping,
  listArloMapping,
  reordenarArloMapping,
  type ArloFieldMapping,
  type DirecaoArlo,
} from "@/app/lib/arloMapping";
import { qk } from "@/app/lib/queryKeys";
import { MapeamentoDialog } from "./_components/MapeamentoDialog";
import { MapeamentoTabela } from "./_components/MapeamentoTabela";
import { PreviewExportacao } from "./_components/PreviewExportacao";

type DialogState =
  | { modo: "criar"; direcao: DirecaoArlo }
  | { modo: "editar"; linha: ArloFieldMapping }
  | null;

const DIRECOES: DirecaoArlo[] = ["exportacao", "importacao"];

/**
 * Configuração do mapeamento Arlo ↔ SGD (#320 · SGD-FE-9). CRUD do BE-9 em
 * `/api/v1/sgd/config/arlo-mapping/`, com reordenação (`reordenar`), ativar e
 * desativar. Rótulos, obrigatoriedade e formatos vêm do catálogo `campos/`;
 * sem ele não há como montar uma coluna nova, então "Nova coluna" espera o
 * catálogo carregar.
 */
export default function IntegracaoArloMappingPage() {
  const { loading, isSuperAdmin } = useIsSuperAdmin();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const [aba, setAba] = useState<DirecaoArlo>("exportacao");
  const [dialog, setDialog] = useState<DialogState>(null);
  const [reordenando, setReordenando] = useState(false);

  const campos = useQuery({
    queryKey: qk.arloMapping.campos,
    queryFn: ({ signal }) => fetchCamposArloMapping(signal),
    enabled: isSuperAdmin,
    staleTime: 5 * 60_000,
  });

  const lista = useQuery({
    queryKey: qk.arloMapping.lista(aba),
    queryFn: ({ signal }) => listArloMapping(aba, signal),
    enabled: isSuperAdmin,
    staleTime: 30_000,
  });

  const camposDaDirecao = useMemo(
    () => campos.data?.[aba] ?? [],
    [campos.data, aba],
  );

  // Campos já mapeados: filtra o combobox de "novo" para só mostrar os livres.
  const mapeadosNaDirecao = useMemo(
    () => new Set((lista.data ?? []).map((l) => l.campo_sgd)),
    [lista.data],
  );

  const header = (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Integração Arlo — Mapeamento de campos
      </h1>
    </PageHeader>
  );

  if (loading) {
    return (
      <>
        {header}
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner className="h-6 w-6 animate-spin text-text-muted" />
        </div>
      </>
    );
  }

  if (!isSuperAdmin) {
    return (
      <>
        {header}
        <RestrictedAccess />
      </>
    );
  }

  const linhas = lista.data ?? [];
  const vazia = !lista.isPending && !lista.isError && linhas.length === 0;

  async function moverLinha(direcao: "cima" | "baixo", id: number) {
    const atual = linhas.findIndex((l) => l.id === id);
    const alvo = direcao === "cima" ? atual - 1 : atual + 1;
    if (atual < 0 || alvo < 0 || alvo >= linhas.length) return;
    const novaOrdem = [...linhas];
    [novaOrdem[atual], novaOrdem[alvo]] = [novaOrdem[alvo], novaOrdem[atual]];
    await aplicarReordenacao(novaOrdem.map((l) => l.id));
  }

  async function trocarPorArrasto(idOrigem: number, idDestino: number) {
    if (idOrigem === idDestino) return;
    const origem = linhas.findIndex((l) => l.id === idOrigem);
    const destino = linhas.findIndex((l) => l.id === idDestino);
    if (origem < 0 || destino < 0) return;
    const nova = [...linhas];
    const [movida] = nova.splice(origem, 1);
    nova.splice(destino, 0, movida);
    await aplicarReordenacao(nova.map((l) => l.id));
  }

  async function aplicarReordenacao(ids: number[]) {
    setReordenando(true);
    try {
      const atualizadas = await reordenarArloMapping(aba, ids);
      queryClient.setQueryData(qk.arloMapping.lista(aba), atualizadas);
      // Invalida o preview: o backend monta o CSV na ordem gravada, então uma
      // reordenação muda a sequência das colunas do exemplo.
      queryClient.invalidateQueries({ queryKey: qk.arloMapping.preview(aba) });
      showToast("Ordem salva.", "success");
    } catch (e) {
      showToast(
        e instanceof Error && e.message
          ? e.message
          : "Não foi possível salvar a ordem.",
        "error",
      );
      // O backend é a fonte: refaz a lista do servidor para desfazer a
      // reordenação otimista que não cabe aqui.
      void lista.refetch();
    } finally {
      setReordenando(false);
    }
  }

  return (
    <div data-testid="arlo-mapping-page">
      {header}

      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "Configurações", href: "/admin/configuracoes" },
            { label: "SGD" },
            { label: "Integração Arlo" },
          ]}
        />

        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-text">
            Mapeamento de campos
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Define quais campos do SGD saem no CSV enviado ao Arlo e como o
            retorno é lido. A ordem na exportação é a ordem das colunas no
            arquivo. Alterações afetam a próxima operação.
          </p>
        </div>

        <div
          role="tablist"
          aria-label="Direção do mapeamento"
          className="flex border-b border-border"
        >
          {DIRECOES.map((d) => (
            <button
              key={d}
              type="button"
              role="tab"
              aria-selected={aba === d}
              onClick={() => setAba(d)}
              className={`border-b-2 px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                aba === d
                  ? "border-primary font-semibold text-primary"
                  : "border-transparent text-text-muted hover:text-text"
              }`}
              data-testid={`arlo-tab-${d}`}
            >
              {DIRECAO_LABEL[d]}
            </button>
          ))}
        </div>

        <div className="flex items-center justify-between">
          <p className="text-sm text-text-muted">
            {aba === "exportacao"
              ? "Colunas do arquivo enviado ao Arlo, na ordem configurada."
              : "Colunas lidas no retorno recebido do Arlo (a ordem é irrelevante na importação)."}
          </p>
          <Button
            onClick={() => setDialog({ modo: "criar", direcao: aba })}
            disabled={!campos.isSuccess}
            data-testid="arlo-novo"
          >
            <Plus className="h-4 w-4" aria-hidden /> Nova coluna
          </Button>
        </div>

        {campos.isError && (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-error-text bg-error-bg px-4 py-3 text-sm text-error-text"
            data-testid="arlo-campos-erro"
          >
            <span className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
              {campos.error instanceof Error && campos.error.message
                ? campos.error.message
                : "Não foi possível carregar o catálogo de campos do Arlo."}
            </span>
            <Button size="sm" variant="secondary" onClick={() => void campos.refetch()}>
              Tentar novamente
            </Button>
          </div>
        )}

        {lista.isPending ? (
          <div className="flex min-h-[30vh] items-center justify-center">
            <Spinner className="h-6 w-6 animate-spin text-text-muted" />
          </div>
        ) : lista.isError ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <p className="max-w-sm text-sm text-text-muted">
              {lista.error instanceof Error && lista.error.message
                ? lista.error.message
                : "Não foi possível carregar o mapeamento."}
            </p>
            <Button variant="secondary" onClick={() => void lista.refetch()}>
              Tentar novamente
            </Button>
          </div>
        ) : vazia ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<PlugZap className="h-7 w-7" />}
              title={`Nenhuma coluna configurada para a ${aba === "exportacao" ? "exportação" : "importação"}`}
              description="Adicione colunas para montar o mapeamento. A operação só roda se os campos obrigatórios estiverem ativos."
              action={
                <Button
                  onClick={() => setDialog({ modo: "criar", direcao: aba })}
                  disabled={!campos.isSuccess}
                >
                  <Plus className="h-4 w-4" aria-hidden /> Nova coluna
                </Button>
              }
            />
          </div>
        ) : (
          <MapeamentoTabela
            linhas={linhas}
            camposDaDirecao={camposDaDirecao}
            reordenando={reordenando}
            onEditar={(linha) => setDialog({ modo: "editar", linha })}
            onMoverCima={(id) => void moverLinha("cima", id)}
            onMoverBaixo={(id) => void moverLinha("baixo", id)}
            onReordenarArraste={(idOrigem, idDestino) =>
              void trocarPorArrasto(idOrigem, idDestino)
            }
            // Só a exportação precisa de ordem: lá o CSV sai pela sequência das
            // linhas; na importação as colunas são localizadas pelo nome.
            permiteReordenar={aba === "exportacao"}
          />
        )}

        {aba === "exportacao" && <PreviewExportacao direcao="exportacao" />}
      </div>

      <MapeamentoDialog
        open={dialog !== null}
        onClose={() => setDialog(null)}
        modo={dialog?.modo ?? "criar"}
        direcao={
          dialog?.modo === "editar" ? dialog.linha.direcao : (dialog?.direcao ?? aba)
        }
        linha={dialog?.modo === "editar" ? dialog.linha : undefined}
        camposDaDirecao={
          dialog
            ? campos.data?.[
                dialog.modo === "editar" ? dialog.linha.direcao : dialog.direcao
              ] ?? []
            : []
        }
        camposMapeados={mapeadosNaDirecao}
        onSalvo={() => {
          setDialog(null);
          queryClient.invalidateQueries({ queryKey: qk.arloMapping.all });
        }}
      />
    </div>
  );
}
