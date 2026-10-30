"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import {
  baixarExportacao,
  emAndamento,
  fetchExportacao,
  repetirExportacao,
  type Exportacao,
  type ResultadoExportacao,
  type StatusExportacao,
} from "@/app/lib/exportacoes";
import { ExportTimeoutError } from "@/app/lib/exportarPlano";
import { qk } from "@/app/lib/queryKeys";

const POLL_INTERVAL_MS = 2_000;

/**
 * Tarefa em andamento + os filtros que a geraram. Os filtros ficam guardados
 * para que "Tentar novamente" repita exatamente o mesmo conjunto, mesmo que o
 * usuário já tenha mexido nos filtros da tela.
 */
export type TarefaExportacao<F> = {
  exportacao: Exportacao;
  filtros: F;
  /**
   * O backend não tem mais o arquivo: o download respondeu 410 (vale 24 h) ou
   * a exportação sumiu (404). Só resta gerar de novo com os mesmos filtros.
   */
  indisponivel?: boolean;
};

export type OpcoesExportacao<F> = {
  /**
   * Chave da tarefa no localStorage — uma por tela/tipo de exportação. O hook
   * acrescenta o id do usuário: o job é de quem o pediu (o backend responde 404
   * a outro usuário), então quem entra depois no mesmo navegador não herda.
   */
  chave: string;
  /** Inicia a exportação: devolve o arquivo já baixado ou o job na fila. */
  iniciar: (filtros: F) => Promise<ResultadoExportacao>;
  /** Mensagem quando o pedido não sai. */
  erroAoIniciar: string;
  /** Aviso ao enfileirar (ex.: quantos registros serão gerados). */
  avisoNaFila?: (exportacao: Exportacao) => string;
};

function lerTarefa<F>(chave: string | null): TarefaExportacao<F> | null {
  if (!chave) return null;
  try {
    const raw = localStorage.getItem(chave);
    return raw ? (JSON.parse(raw) as TarefaExportacao<F>) : null;
  } catch {
    return null;
  }
}

function gravarTarefa<F>(chave: string | null, tarefa: TarefaExportacao<F> | null): void {
  if (!chave) return;
  try {
    if (tarefa) localStorage.setItem(chave, JSON.stringify(tarefa));
    else localStorage.removeItem(chave);
  } catch {
    /* storage indisponível — a tarefa só não sobrevive ao reload */
  }
}

/** 404 no polling: o backend não conhece mais a exportação (foi removida). */
function expirou(e: unknown): boolean {
  return e instanceof ApiError && e.status === 404;
}

/** 410 no download: o arquivo da exportação concluída passou das 24 h. */
function arquivoExpirado(e: unknown): boolean {
  return e instanceof ApiError && e.status === 410;
}

function mensagemDeErro(e: unknown, padrao: string): string {
  if (e instanceof ApiError || e instanceof ExportTimeoutError) return e.message;
  return padrao;
}

/**
 * Orquestra uma exportação do SGP (#240, A4 da #302): inicia, acompanha o job
 * por polling até concluir ou falhar, baixa o arquivo e oferece "Tentar
 * novamente". A tarefa fica no localStorage, então sair da página (ou
 * recarregar) não perde o arquivo — ao voltar, o acompanhamento retoma. O
 * polling é uma query: sair da tela o cancela.
 */
export function useExportacao<F>({ chave: base, iniciar, erroAoIniciar, avisoNaFila }: OpcoesExportacao<F>) {
  const { data: session } = useSession();
  const usuarioId = session?.user?.id;
  const chave = usuarioId ? `${base}:${usuarioId}` : null;
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [tarefa, setTarefa] = useState<TarefaExportacao<F> | null>(null);
  const [iniciando, setIniciando] = useState(false);
  const [baixando, setBaixando] = useState(false);

  // localStorage só existe no cliente: ler no mount evita divergência de hidratação.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTarefa(lerTarefa<F>(chave));
  }, [chave]);

  const atualizarTarefa = useCallback(
    (nova: TarefaExportacao<F> | null) => {
      gravarTarefa(chave, nova);
      setTarefa(nova);
    },
    [chave],
  );

  const id = tarefa?.exportacao.id ?? null;

  const polling = useQuery({
    queryKey: qk.exportacao(String(id ?? "")),
    queryFn: ({ signal }) => fetchExportacao(id!, signal),
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
  const efetiva: TarefaExportacao<F> | null = useMemo(() => {
    if (!tarefa) return null;
    if (expirou(erroPolling)) {
      return {
        ...tarefa,
        indisponivel: true,
        exportacao: {
          ...tarefa.exportacao,
          status: "erro",
          erro: "Esta exportação não está mais disponível. Gere o arquivo novamente.",
        },
      };
    }
    const lida = polling.data;
    return lida && lida.id === tarefa.exportacao.id ? { ...tarefa, exportacao: lida } : tarefa;
  }, [tarefa, polling.data, erroPolling]);

  // Persiste o estado efetivo (reabrir a página mostra o desfecho sem refazer
  // o polling) e avisa por toast quando a tarefa sai do andamento.
  const statusAnterior = useRef<StatusExportacao | null>(null);
  useEffect(() => {
    if (!efetiva) {
      statusAnterior.current = null;
      return;
    }
    gravarTarefa(chave, efetiva);
    const { status, erro } = efetiva.exportacao;
    const antes = statusAnterior.current;
    statusAnterior.current = status;
    if (antes !== "pendente" && antes !== "processando") return;
    if (status === "concluida") {
      showToast("Exportação concluída. O arquivo está pronto para download.", "success");
    } else if (status === "erro") {
      showToast(erro || "A exportação falhou.", "error");
    }
  }, [chave, efetiva, showToast]);

  const exportar = useCallback(
    async (filtros: F) => {
      if (iniciando) return;
      setIniciando(true);
      try {
        const resultado = await iniciar(filtros);
        if (resultado.tipo === "arquivo") {
          showToast(`Download de ${resultado.nome} iniciado.`, "success");
          return;
        }
        atualizarTarefa({ exportacao: resultado.exportacao, filtros });
        showToast(avisoNaFila?.(resultado.exportacao) ?? "A exportação será gerada em segundo plano.");
      } catch (e) {
        showToast(mensagemDeErro(e, erroAoIniciar), "error");
      } finally {
        setIniciando(false);
      }
    },
    [iniciando, iniciar, atualizarTarefa, avisoNaFila, erroAoIniciar, showToast],
  );

  const baixar = useCallback(async () => {
    if (!efetiva || efetiva.exportacao.status !== "concluida" || baixando) return;
    setBaixando(true);
    try {
      const nome = await baixarExportacao(efetiva.exportacao);
      showToast(`Download de ${nome} iniciado.`, "success");
    } catch (e) {
      if (arquivoExpirado(e)) atualizarTarefa({ ...efetiva, indisponivel: true });
      showToast(mensagemDeErro(e, "Não foi possível baixar o arquivo."), "error");
    } finally {
      setBaixando(false);
    }
  }, [efetiva, baixando, atualizarTarefa, showToast]);

  /**
   * "Tentar novamente": a exportação em `erro` é reenfileirada pelo backend
   * (`repetir`), mantendo o mesmo id. Se ela não existe mais (ou o arquivo
   * expirou), gera uma nova com os filtros guardados.
   */
  const repetir = useCallback(async () => {
    if (!efetiva) return;
    const { filtros } = efetiva;
    if (efetiva.indisponivel) {
      atualizarTarefa(null);
      void exportar(filtros);
      return;
    }
    try {
      const reenfileirada = await repetirExportacao(efetiva.exportacao.id);
      // A leitura antiga (em `erro`) no cache prevaleceria sobre o novo estado.
      queryClient.removeQueries({ queryKey: qk.exportacao(String(reenfileirada.id)) });
      atualizarTarefa({ exportacao: reenfileirada, filtros });
    } catch (e) {
      showToast(mensagemDeErro(e, "Não foi possível repetir a exportação."), "error");
    }
  }, [efetiva, atualizarTarefa, exportar, queryClient, showToast]);

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
