"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { ExportTimeoutError } from "@/app/lib/exportarPlano";
import { qk } from "@/app/lib/queryKeys";
import {
  baixarExportacaoUpfs,
  fetchExportacaoUpfs,
  iniciarExportacaoUpfs,
  type ExportacaoUpfs,
  type ExportUpfsParams,
  type StatusExportacaoUpfs,
} from "@/app/lib/upfs";

const STORAGE_KEY = "sgp.upfs.exportacao";
const POLL_INTERVAL_MS = 2_000;

/**
 * Tarefa em andamento + os filtros que a geraram. Os filtros ficam guardados
 * para que "Tentar novamente" repita exatamente o mesmo conjunto, mesmo que o
 * usuário já tenha mexido nos filtros da tela.
 */
export type TarefaExportacaoUpfs = {
  exportacao: ExportacaoUpfs;
  filtros: ExportUpfsParams;
};

function lerTarefa(): TarefaExportacaoUpfs | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as TarefaExportacaoUpfs) : null;
  } catch {
    return null;
  }
}

function gravarTarefa(tarefa: TarefaExportacaoUpfs | null): void {
  try {
    if (tarefa) localStorage.setItem(STORAGE_KEY, JSON.stringify(tarefa));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage indisponível — a tarefa só não sobrevive ao reload */
  }
}

function emAndamento(e: ExportacaoUpfs): boolean {
  return e.status === "pendente" || e.status === "processando";
}

/** 404 no polling: o backend não conhece mais a tarefa (expirou ou foi removida). */
function expirou(e: unknown): boolean {
  return e instanceof ApiError && e.status === 404;
}

function mensagemDeErro(e: unknown, padrao: string): string {
  if (e instanceof ApiError || e instanceof ExportTimeoutError) return e.message;
  return padrao;
}

/**
 * Orquestra a exportação da listagem de UPFs (#240).
 *
 * - ≤ 1.000 registros: o backend devolve o CSV e o download sai na hora.
 * - > 1.000: o backend devolve 202 com uma tarefa; o hook acompanha por polling
 *   até concluir ou falhar. A tarefa fica no localStorage, então sair da página
 *   (ou recarregar) não perde o arquivo — ao voltar, o acompanhamento retoma e
 *   o download continua disponível.
 */
export function useExportacaoUpfs() {
  const { showToast } = useToast();
  const [tarefa, setTarefa] = useState<TarefaExportacaoUpfs | null>(null);
  const [iniciando, setIniciando] = useState(false);
  const [baixando, setBaixando] = useState(false);

  // localStorage só existe no cliente: ler no mount evita divergência de hidratação.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTarefa(lerTarefa());
  }, []);

  const atualizarTarefa = useCallback((nova: TarefaExportacaoUpfs | null) => {
    gravarTarefa(nova);
    setTarefa(nova);
  }, []);

  const id = tarefa?.exportacao.id ?? null;

  const polling = useQuery({
    queryKey: qk.exportacaoUpfs(id ?? ""),
    queryFn: ({ signal }) => fetchExportacaoUpfs(id!, signal),
    enabled: id !== null && emAndamento(tarefa!.exportacao),
    staleTime: 0,
    refetchInterval: (query) => {
      if (expirou(query.state.error)) return false;
      const atual = query.state.data;
      return atual && !emAndamento(atual) ? false : POLL_INTERVAL_MS;
    },
  });

  // O estado efetivo é DERIVADO: a última leitura do polling prevalece sobre o
  // que estava gravado; uma tarefa que o backend não conhece mais (404 —
  // expirada/removida) vira falha local, com a opção de gerar de novo.
  const erroPolling = polling.error;
  const efetiva: TarefaExportacaoUpfs | null = useMemo(() => {
    if (!tarefa) return null;
    if (expirou(erroPolling)) {
      return {
        ...tarefa,
        exportacao: {
          ...tarefa.exportacao,
          status: "falhou",
          erro: "Esta exportação não está mais disponível. Gere o arquivo novamente.",
        },
      };
    }
    const lida = polling.data;
    return lida && lida.id === tarefa.exportacao.id
      ? { ...tarefa, exportacao: lida }
      : tarefa;
  }, [tarefa, polling.data, erroPolling]);

  // Persiste o estado efetivo (reabrir a página mostra o desfecho sem refazer
  // o polling) e avisa por toast quando a tarefa sai do andamento.
  const statusAnterior = useRef<StatusExportacaoUpfs | null>(null);
  useEffect(() => {
    if (!efetiva) {
      statusAnterior.current = null;
      return;
    }
    gravarTarefa(efetiva);
    const { status, erro } = efetiva.exportacao;
    const antes = statusAnterior.current;
    statusAnterior.current = status;
    if (antes !== "pendente" && antes !== "processando") return;
    if (status === "concluida") {
      showToast("Exportação concluída. O arquivo está pronto para download.", "success");
    } else if (status === "falhou") {
      showToast(erro ?? "A exportação falhou.", "error");
    }
  }, [efetiva, showToast]);

  const exportar = useCallback(
    async (filtros: ExportUpfsParams) => {
      if (iniciando) return;
      setIniciando(true);
      try {
        const resultado = await iniciarExportacaoUpfs(filtros);
        if (resultado.tipo === "arquivo") {
          showToast(`Download de ${resultado.nome} iniciado.`, "success");
          return;
        }
        atualizarTarefa({ exportacao: resultado.exportacao, filtros });
        const total = resultado.exportacao.total;
        showToast(
          total
            ? `O conjunto filtrado tem ${total.toLocaleString("pt-BR")} registros. A exportação será gerada em segundo plano.`
            : "A exportação será gerada em segundo plano.",
        );
      } catch (e) {
        showToast(mensagemDeErro(e, "Não foi possível exportar as UPFs."), "error");
      } finally {
        setIniciando(false);
      }
    },
    [iniciando, atualizarTarefa, showToast],
  );

  const baixar = useCallback(async () => {
    if (!efetiva || efetiva.exportacao.status !== "concluida" || baixando) return;
    setBaixando(true);
    try {
      const nome = await baixarExportacaoUpfs(efetiva.exportacao);
      showToast(`Download de ${nome} iniciado.`, "success");
    } catch (e) {
      showToast(mensagemDeErro(e, "Não foi possível baixar o arquivo."), "error");
    } finally {
      setBaixando(false);
    }
  }, [efetiva, baixando, showToast]);

  const repetir = useCallback(() => {
    if (!tarefa) return;
    const { filtros } = tarefa;
    atualizarTarefa(null);
    void exportar(filtros);
  }, [tarefa, atualizarTarefa, exportar]);

  const descartar = useCallback(() => atualizarTarefa(null), [atualizarTarefa]);

  return {
    tarefa: efetiva,
    iniciando,
    baixando,
    /** Há uma tarefa pendente/processando — nova exportação fica bloqueada. */
    acompanhando: efetiva ? emAndamento(efetiva.exportacao) : false,
    /** O polling falhou de forma transitória (rede/5xx); a tarefa segue válida. */
    erroAcompanhamento:
      erroPolling && !expirou(erroPolling)
        ? mensagemDeErro(erroPolling, "Não foi possível consultar o andamento da exportação.")
        : null,
    reconsultar: () => void polling.refetch(),
    exportar,
    baixar,
    repetir,
    descartar,
  };
}
