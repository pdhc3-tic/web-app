"use client";

import { useQuery } from "@tanstack/react-query";
import { Filter, X } from "lucide-react";
import { SearchSelect, type SearchSelectOption } from "@/app/components/ui/SearchSelect/SearchSelect";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { getAtividade, listAcoes } from "@/app/lib/atividades";
import {
  buscarAtividadesParaFiltro,
  fetchSubmetaOptions,
  fetchOpcoesUsuarios,
  type AtividadeOpcao,
  type ChaveFiltro,
  type ExecucaoFiltros,
  type PapelUsuario,
} from "@/app/lib/execucaoSgd";
import { listMetas } from "@/app/lib/metas";
import { qk } from "@/app/lib/queryKeys";
import { fetchTerritoryOptions } from "@/app/lib/upfs";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";

const INPUT_CLASS =
  "h-9 w-full rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus:border-primary";

function comTodos(rotulo: string, opcoes: SelectOption[]): SelectOption[] {
  return [{ value: "", label: rotulo }, ...opcoes];
}

/**
 * Solicitante ou responsável de etapa, pela rota de opções pedida ao backend
 * na pendência 26 (`fetchOpcoesUsuarios`).
 */
function FiltroUsuario({
  papel,
  rotulo,
  rotuloTodos,
  valor,
  onChange,
}: {
  papel: PapelUsuario;
  rotulo: string;
  rotuloTodos: string;
  valor: string;
  onChange: (valor: string | undefined) => void;
}) {
  const opcoes = useQuery({
    queryKey: qk.execucao.opcoesUsuarios(papel),
    queryFn: ({ signal }) => fetchOpcoesUsuarios(papel, signal),
    staleTime: Infinity,
  });

  return (
    <Select
      label={rotulo}
      value={valor}
      onChange={(v) => onChange(v || undefined)}
      options={comTodos(rotuloTodos, opcoes.data ?? [])}
      error={opcoes.isError ? "Não foi possível carregar a lista." : undefined}
      name={papel}
    />
  );
}

/** Busca de atividade pelo título; o id da URL vira rótulo pelo detalhe. */
function FiltroAtividade({
  valor,
  onChange,
}: {
  valor: string | undefined;
  onChange: (valor: string | undefined) => void;
}) {
  const escolhida = useQuery({
    queryKey: qk.atividade(valor ?? ""),
    queryFn: ({ signal }) => getAtividade(valor!, signal),
    enabled: !!valor,
    staleTime: Infinity,
  });

  const paraOpcao = (a: AtividadeOpcao): SearchSelectOption<AtividadeOpcao> => ({
    value: String(a.id),
    label: a.titulo,
    item: a,
  });

  const opcaoAtual: SearchSelectOption<AtividadeOpcao> | null = valor
    ? paraOpcao({ id: Number(valor), titulo: escolhida.data?.titulo ?? `Atividade #${valor}` })
    : null;

  return (
    <SearchSelect<AtividadeOpcao>
      label="Atividade"
      value={opcaoAtual}
      onChange={(opcao) => onChange(opcao?.value)}
      search={async (texto, signal) =>
        (await buscarAtividadesParaFiltro(texto, signal)).map(paraOpcao)
      }
      queryKey={qk.execucao.buscaAtividade}
      placeholder="Buscar pelo título…"
      emptyText="Nenhuma atividade encontrada."
      data-testid="filtro-atividade"
    />
  );
}

export function ExecucaoFilters({
  filtros,
  onChange,
  rubricaOptions,
}: {
  filtros: ExecucaoFiltros;
  onChange: (novo: ExecucaoFiltros) => void;
  /** Rubricas ativas, tiradas do próprio painel (o backend lista todas). */
  rubricaOptions: SelectOption[];
}) {
  const choices = useSgpChoices();

  const territorios = useQuery({
    queryKey: qk.territorios,
    queryFn: ({ signal }) => fetchTerritoryOptions(signal),
    staleTime: Infinity,
  });
  const metas = useQuery({
    queryKey: qk.execucao.metas,
    queryFn: ({ signal }) => listMetas(signal),
    staleTime: Infinity,
  });
  const submetas = useQuery({
    queryKey: qk.execucao.submetas,
    queryFn: ({ signal }) => fetchSubmetaOptions(signal),
    staleTime: Infinity,
  });
  const acoes = useQuery({
    queryKey: qk.acoesPT,
    queryFn: ({ signal }) => listAcoes(signal),
    staleTime: Infinity,
  });
  const falhas = [
    territorios.isError && "territórios",
    metas.isError && "metas",
    submetas.isError && "submetas",
    acoes.isError && "ações",
  ].filter(Boolean);

  const temFiltroAtivo = Object.values(filtros).some(Boolean);
  const atualizar = (chave: ChaveFiltro, valor: string | undefined) =>
    onChange({ ...filtros, [chave]: valor || undefined });

  return (
    <div
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 shadow-xs"
      data-testid="execucao-filtros"
    >
      <div className="flex items-center justify-between gap-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
        <span className="flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5" aria-hidden />
          Filtros de Execução e Custo
        </span>
        {temFiltroAtivo && (
          <button
            type="button"
            onClick={() => onChange({})}
            className="inline-flex items-center gap-1 text-xs font-medium normal-case tracking-normal text-primary hover:underline"
            data-testid="limpar-filtros-btn"
          >
            <X className="h-3 w-3" aria-hidden />
            Limpar filtros
          </button>
        )}
      </div>

      {falhas.length > 0 && (
        <p role="alert" className="text-xs text-error-text" data-testid="filtros-erro">
          Não foi possível carregar as opções de {falhas.join(", ")}. Recarregue a página para
          tentar de novo.
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
        <Select
          label="Status"
          value={filtros.status ?? ""}
          onChange={(v) => atualizar("status", v)}
          options={comTodos("Todos os status", choices.demanda_status)}
          name="status"
        />
        <Select
          label="Tipo"
          value={filtros.tipo ?? ""}
          onChange={(v) => atualizar("tipo", v)}
          options={comTodos("Todos os tipos", choices.solicitacao_tipo)}
          name="tipo"
        />
        <Select
          label="Rubrica"
          value={filtros.rubrica ?? ""}
          onChange={(v) => atualizar("rubrica", v)}
          options={comTodos("Todas as rubricas", rubricaOptions)}
          name="rubrica"
        />
        <Select
          label="Território"
          value={filtros.territorio ?? ""}
          onChange={(v) => atualizar("territorio", v)}
          options={comTodos("Todos os territórios", territorios.data ?? [])}
          name="territorio"
        />
        <div className="flex flex-col gap-1">
          <span className="text-label font-medium text-text">Período</span>
          <div className="grid grid-cols-2 gap-1.5">
            <input
              type="date"
              aria-label="Data inicial"
              value={filtros.periodo_inicio ?? ""}
              onChange={(e) => atualizar("periodo_inicio", e.target.value)}
              className={INPUT_CLASS}
            />
            <input
              type="date"
              aria-label="Data final"
              value={filtros.periodo_fim ?? ""}
              onChange={(e) => atualizar("periodo_fim", e.target.value)}
              className={INPUT_CLASS}
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
        <Select
          label="Meta"
          value={filtros.meta ?? ""}
          onChange={(v) => atualizar("meta", v)}
          options={comTodos(
            "Todas as metas",
            (metas.data ?? []).map((m) => ({ value: String(m.id), label: `Meta ${m.numero} — ${m.titulo}` })),
          )}
          name="meta"
        />
        <Select
          label="Submeta"
          value={filtros.submeta ?? ""}
          onChange={(v) => atualizar("submeta", v)}
          options={comTodos("Todas as submetas", submetas.data ?? [])}
          name="submeta"
        />
        <Select
          label="Ação"
          value={filtros.acao ?? ""}
          onChange={(v) => atualizar("acao", v)}
          options={comTodos(
            "Todas as ações",
            (acoes.data ?? []).map((a) => ({ value: String(a.id), label: `${a.numero} — ${a.descricao}` })),
          )}
          name="acao"
        />
        <FiltroAtividade valor={filtros.atividade} onChange={(v) => atualizar("atividade", v)} />
        <FiltroUsuario
          papel="solicitante"
          rotulo="Solicitante"
          rotuloTodos="Todos os solicitantes"
          valor={filtros.solicitante ?? ""}
          onChange={(v) => atualizar("solicitante", v)}
        />
        <FiltroUsuario
          papel="responsavel"
          rotulo="Responsável pela etapa atual"
          rotuloTodos="Todos os responsáveis"
          valor={filtros.responsavel_etapa_atual ?? ""}
          onChange={(v) => atualizar("responsavel_etapa_atual", v)}
        />
      </div>
    </div>
  );
}
