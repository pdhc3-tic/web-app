"use client";

import { useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Gauge, Plus, Search } from "lucide-react";
import { AlertCircleIcon } from "@/app/components/icons";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Input } from "@/app/components/ui/Input/Input";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { Select } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { useCanManageWorkPlan } from "@/app/lib/auth/roles";
import { useDebounced } from "@/app/lib/hooks/useDebounced";
import {
  atualizarIndicador,
  CATEGORIA_LABEL,
  CODIGO_EM_USO,
  excluirIndicador,
  FILTROS_PADRAO,
  FORMA_APURACAO_LABEL,
  listarIndicadores,
  opcoes,
  type FiltrosIndicadores,
  type Indicador,
} from "@/app/lib/indicadores";
import { qk } from "@/app/lib/queryKeys";
import { IndicadoresTable } from "./_components/IndicadoresTable";
import { IndicadorSlideOver } from "./_components/IndicadorSlideOver";

const POR_PAGINA = 25;

type Painel = { aberto: boolean; indicador: Indicador | null };

/** A exclusão: o indicador e, depois do 409, o motivo de não poder excluir. */
type Exclusao = { indicador: Indicador; emUso: string | null };

/**
 * Catálogo de Indicadores (SGP §5.4, #453).
 *
 * Todo perfil que lê o Plano de Trabalho vê o catálogo; UGP e Super Admin
 * cadastram, editam, inativam e excluem. Excluir é recusado pelo backend
 * quando há Ação vinculada (409 `indicador_em_uso`): a confirmação passa a
 * oferecer inativar, que preserva o histórico.
 */
export default function IndicadoresPage() {
  const { loading: carregandoSessao, canManage } = useCanManageWorkPlan();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [filtros, setFiltros] = useState<FiltrosIndicadores>(FILTROS_PADRAO);
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(POR_PAGINA);
  const busca = useDebounced(filtros.q);
  const filtrosEfetivos = { ...filtros, q: busca };

  const lista = useQuery({
    queryKey: qk.indicadores.lista({ ...filtrosEfetivos, offset, limit }),
    queryFn: ({ signal }) => listarIndicadores(filtrosEfetivos, { offset, limit }, signal),
    enabled: !carregandoSessao,
    placeholderData: keepPreviousData,
  });

  /**
   * Mudar filtro volta para a primeira página NO MESMO passo. Voltar depois,
   * num efeito, deixava sair uma consulta com o filtro novo e a página antiga,
   * e o `PageNumberPagination` responde 404 a uma página que não existe mais.
   */
  function mudarFiltro(mudanca: Partial<FiltrosIndicadores>) {
    setFiltros((f) => ({ ...f, ...mudanca }));
    setOffset(0);
  }

  const [painel, setPainel] = useState<Painel>({ aberto: false, indicador: null });
  const [exclusao, setExclusao] = useState<Exclusao | null>(null);
  const [processando, setProcessando] = useState(false);

  function recarregar() {
    // O seletor de indicador da Ação (`AcaoSlideOver`) relê o catálogo a cada abertura.
    void queryClient.invalidateQueries({ queryKey: qk.indicadores.todos });
  }

  /** Id do indicador sendo inativado ou reativado: um segundo clique não manda outro PATCH. */
  const [alternando, setAlternando] = useState<number | null>(null);

  async function alternarAtivo(indicador: Indicador) {
    if (alternando !== null) return;
    setAlternando(indicador.id);
    try {
      await atualizarIndicador(indicador.id, { ativo: !indicador.ativo });
      showToast(`Indicador ${indicador.codigo} ${indicador.ativo ? "inativado" : "reativado"}.`, "success");
      recarregar();
    } catch (e: unknown) {
      showToast(e instanceof ApiError ? e.message : "Não foi possível alterar o indicador.", "error");
    } finally {
      setAlternando(null);
    }
  }

  async function confirmarExclusao() {
    if (!exclusao || processando) return;
    setProcessando(true);
    try {
      if (exclusao.emUso) {
        // Depois da recusa, o botão principal inativa.
        await atualizarIndicador(exclusao.indicador.id, { ativo: false });
        showToast(`Indicador ${exclusao.indicador.codigo} inativado.`, "success");
      } else {
        await excluirIndicador(exclusao.indicador.id);
        showToast(`Indicador ${exclusao.indicador.codigo} excluído.`, "success");
      }
      setExclusao(null);
      recarregar();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.code === CODIGO_EM_USO) {
        setExclusao({ indicador: exclusao.indicador, emUso: e.message });
        return;
      }
      setExclusao(null);
      showToast(e instanceof ApiError ? e.message : "Não foi possível excluir o indicador.", "error");
    } finally {
      setProcessando(false);
    }
  }

  const proibido = lista.error instanceof ApiError && lista.error.status === 403;

  const header = (
    <PageHeader>
      <div className="flex w-full items-center justify-between gap-3">
        <h1 className="truncate text-base font-semibold text-text">Catálogo de Indicadores</h1>
        {canManage && !proibido && (
          <Button
            size="sm"
            onClick={() => setPainel({ aberto: true, indicador: null })}
            leftIcon={<Plus className="h-4 w-4" />}
            data-testid="indicador-novo-btn"
          >
            Novo indicador
          </Button>
        )}
      </div>
    </PageHeader>
  );

  if (carregandoSessao) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    );
  }

  if (proibido) {
    return (
      <>
        {header}
        <RestrictedAccess />
      </>
    );
  }

  const dados = lista.data;
  const filtrado =
    filtros.q.trim() !== "" || filtros.situacao !== "ativos" || filtros.categoria !== "" || filtros.forma_apuracao !== "";

  return (
    <div data-testid="indicadores-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Plano de Trabalho", href: "/sgp/metas" },
            { label: "Indicadores" },
          ]}
        />

        <p className="max-w-prose text-sm text-text-muted">
          Cada Ação do Plano de Trabalho é medida por um indicador do catálogo. Ações de Metas diferentes podem usar o
          mesmo indicador, e a quantidade realizada é apurada pela forma de apuração dele.
        </p>

        <div
          className="grid grid-cols-1 gap-3 rounded-lg border border-border bg-surface p-4 sm:grid-cols-2 lg:grid-cols-4"
          data-testid="indicadores-filtros"
        >
          <Input
            label="Buscar"
            placeholder="Código ou nome"
            value={filtros.q}
            onChange={(e) => mudarFiltro({ q: e.target.value })}
            startIcon={<Search className="h-4 w-4" />}
            data-testid="indicadores-busca"
          />
          <Select
            id="indicadores-situacao"
            label="Situação"
            options={[
              { value: "ativos", label: "Ativos" },
              { value: "inativos", label: "Inativos" },
              { value: "todos", label: "Todos" },
            ]}
            value={filtros.situacao}
            onChange={(v) => mudarFiltro({ situacao: v as FiltrosIndicadores["situacao"] })}
          />
          <Select
            id="indicadores-categoria"
            label="Categoria"
            options={[{ value: "", label: "Todas" }, ...opcoes(CATEGORIA_LABEL)]}
            value={filtros.categoria}
            onChange={(v) => mudarFiltro({ categoria: v })}
            placeholder="Todas"
          />
          <Select
            id="indicadores-forma"
            label="Forma de apuração"
            options={[{ value: "", label: "Todas" }, ...opcoes(FORMA_APURACAO_LABEL)]}
            value={filtros.forma_apuracao}
            onChange={(v) => mudarFiltro({ forma_apuracao: v })}
            placeholder="Todas"
          />
        </div>

        {lista.isError ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <p className="max-w-sm text-sm text-text-muted">
              {lista.error instanceof ApiError ? lista.error.message : "Não foi possível carregar o catálogo."}
            </p>
            <Button variant="secondary" onClick={() => void lista.refetch()}>
              Tentar novamente
            </Button>
          </div>
        ) : dados && dados.count === 0 ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<Gauge className="h-7 w-7" />}
              title={filtrado ? "Nenhum indicador neste filtro" : "Nenhum indicador cadastrado"}
              description={
                filtrado
                  ? "Ajuste a busca ou os filtros para ver outros indicadores."
                  : canManage
                    ? "Cadastre o primeiro indicador do catálogo."
                    : "A UGP ainda não cadastrou indicadores."
              }
              action={
                filtrado ? (
                  <Button variant="secondary" onClick={() => mudarFiltro(FILTROS_PADRAO)}>
                    Limpar filtros
                  </Button>
                ) : undefined
              }
            />
          </div>
        ) : (
          <>
            <IndicadoresTable
              indicadores={dados?.results ?? []}
              carregando={!dados}
              canManage={canManage}
              onEditar={(indicador) => setPainel({ aberto: true, indicador })}
              onAlternarAtivo={alternarAtivo}
              onExcluir={(indicador) => setExclusao({ indicador, emUso: null })}
            />
            {dados && (
              <Pagination
                count={dados.count}
                offset={offset}
                limit={limit}
                onOffsetChange={setOffset}
                onLimitChange={(l) => {
                  setLimit(l);
                  setOffset(0);
                }}
                itemNoun={{ one: "indicador", other: "indicadores" }}
              />
            )}
          </>
        )}
      </div>

      <IndicadorSlideOver
        open={painel.aberto}
        indicador={painel.indicador}
        onClose={() => setPainel((p) => ({ ...p, aberto: false }))}
        onSaved={(salvo, novo) => {
          setPainel((p) => ({ ...p, aberto: false }));
          showToast(`Indicador ${salvo.codigo} ${novo ? "cadastrado" : "atualizado"}.`, "success");
          recarregar();
        }}
      />

      <SlideOver
        open={exclusao !== null}
        onClose={() => {
          if (!processando) setExclusao(null);
        }}
        title={exclusao?.emUso ? "Indicador em uso" : "Excluir indicador?"}
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={() => setExclusao(null)} disabled={processando}>
              Cancelar
            </Button>
            <Button
              variant={exclusao?.emUso ? "primary" : "danger"}
              onClick={confirmarExclusao}
              loading={processando}
              data-testid="indicador-excluir-confirmar"
            >
              {exclusao?.emUso ? "Inativar" : "Excluir"}
            </Button>
          </div>
        }
      >
        {exclusao && (
          <div className="flex flex-col gap-4 px-4 py-6" data-testid="indicador-exclusao">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-error-bg text-error-text">
                <AlertCircleIcon className="h-5 w-5" />
              </span>
              <p className="text-sm leading-relaxed text-text">
                {exclusao.emUso ? (
                  <>
                    {exclusao.emUso} Inativado, ele sai das opções de novas Ações e as que já o usam continuam como
                    estão.
                  </>
                ) : (
                  <>
                    O indicador {exclusao.indicador.codigo} – {exclusao.indicador.nome} será excluído permanentemente.
                    Indicador usado por alguma Ação não pode ser excluído, só inativado.
                  </>
                )}
              </p>
            </div>
          </div>
        )}
      </SlideOver>
    </div>
  );
}
