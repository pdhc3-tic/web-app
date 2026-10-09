"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileUp, XCircle } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Button } from "@/app/components/ui/Button/Button";
import { ProgressBar } from "@/app/components/ui/ProgressBar/ProgressBar";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import {
  ARLO_TAMANHO_MAXIMO,
  getOperacaoArlo,
  importarRetornoArlo,
  operacaoEmAndamento,
  tipoDoArquivoArlo,
} from "@/app/lib/arlo";
import { qk } from "@/app/lib/queryKeys";
import { ErrosDaImportacao, StatusOperacao } from "./ErrosDaImportacao";

/** Intervalo de consulta enquanto a task processa a planilha. */
const INTERVALO_ACOMPANHAMENTO_MS = 2_000;

type Etapa =
  | { tipo: "ocioso" }
  | { tipo: "enviando"; percentual: number }
  | { tipo: "acompanhando"; operacaoId: number };

function validar(file: File): string | null {
  if (!tipoDoArquivoArlo(file)) return "Envie a planilha de retorno em CSV ou XLSX.";
  if (file.size === 0) return "O arquivo está vazio.";
  if (file.size > ARLO_TAMANHO_MAXIMO) return "O arquivo passa de 10 MB, o limite da importação.";
  return null;
}

/**
 * Upload da planilha de retorno do Arlo. O envio vai direto ao storage (com
 * progresso real); depois o backend processa numa task e a tela acompanha a
 * operação até concluir, mostrando o resumo e as linhas recusadas.
 */
export function ImportarRetorno() {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [erroArquivo, setErroArquivo] = useState<string | null>(null);
  const [etapa, setEtapa] = useState<Etapa>({ tipo: "ocioso" });

  const operacaoId = etapa.tipo === "acompanhando" ? etapa.operacaoId : null;
  const acompanhamento = useQuery({
    queryKey: qk.arlo.operacao(operacaoId ?? 0),
    queryFn: ({ signal }) => getOperacaoArlo(operacaoId as number, signal),
    enabled: operacaoId !== null,
    refetchInterval: (q) =>
      q.state.data && !operacaoEmAndamento(q.state.data) ? false : INTERVALO_ACOMPANHAMENTO_MS,
  });
  const operacao = acompanhamento.data;
  const terminou = operacao ? !operacaoEmAndamento(operacao) : false;

  // Ao terminar, o status das demandas pagas mudou e o histórico ganhou a linha.
  // Avisa uma vez por operação, mesmo que ela seja buscada de novo depois.
  const avisada = useRef<number | null>(null);
  useEffect(() => {
    if (!terminou || !operacao || avisada.current === operacao.id) return;
    avisada.current = operacao.id;
    void queryClient.invalidateQueries({ queryKey: qk.demandas.all });
    void queryClient.invalidateQueries({ queryKey: qk.arlo.operacoes });
    if (operacao.status === "concluido") {
      showToast(
        operacao.erros_json.length
          ? `Importação concluída: ${operacao.registros_ok} de ${operacao.total_registros} linhas processadas.`
          : "Importação concluída. As demandas pagas foram atualizadas.",
      );
    } else {
      showToast("A importação falhou. Veja o motivo abaixo.", "error");
    }
  }, [terminou, operacao, queryClient, showToast]);

  function escolher(file: File | undefined) {
    if (!file) return;
    setArquivo(file);
    setErroArquivo(validar(file));
  }

  async function enviar() {
    if (!arquivo) return;
    const tipo = tipoDoArquivoArlo(arquivo);
    if (!tipo || validar(arquivo)) return;
    setEtapa({ tipo: "enviando", percentual: 0 });
    try {
      const op = await importarRetornoArlo(arquivo, tipo, (percentual) =>
        setEtapa({ tipo: "enviando", percentual }),
      );
      queryClient.setQueryData(qk.arlo.operacao(op.id), op);
      void queryClient.invalidateQueries({ queryKey: qk.arlo.operacoes });
      setEtapa({ tipo: "acompanhando", operacaoId: op.id });
    } catch (err) {
      setEtapa({ tipo: "ocioso" });
      showToast(
        err instanceof ApiError ? err.message : "Não foi possível enviar a planilha. Tente de novo.",
        "error",
      );
    }
  }

  function novaImportacao() {
    setArquivo(null);
    setErroArquivo(null);
    setEtapa({ tipo: "ocioso" });
    if (inputRef.current) inputRef.current.value = "";
  }

  const ocupado = etapa.tipo === "enviando" || (etapa.tipo === "acompanhando" && !terminou);

  return (
    <section aria-labelledby="arlo-importar-titulo" className="space-y-3" data-testid="arlo-importar">
      <div>
        <h2 id="arlo-importar-titulo" className="text-base font-semibold text-text">
          Importar retorno do Arlo
        </h2>
        <p className="mt-0.5 text-sm text-text-muted">
          Planilha de pagamentos devolvida pelo Arlo (CSV ou XLSX, até 10 MB). As demandas pagas
          passam para Em atendimento ou Concluída; linhas com erro são listadas e não impedem as
          demais.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-surface p-4 space-y-4">
        {etapa.tipo !== "acompanhando" && (
          <div className="flex flex-wrap items-center gap-3">
            <input
              ref={inputRef}
              id="arlo-arquivo"
              type="file"
              accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="sr-only"
              onChange={(e) => escolher(e.target.files?.[0])}
              disabled={ocupado}
              data-testid="arlo-arquivo"
            />
            <Button
              variant="secondary"
              leftIcon={<FileUp className="h-4 w-4" aria-hidden />}
              onClick={() => inputRef.current?.click()}
              disabled={ocupado}
            >
              Escolher planilha
            </Button>
            <span className="min-w-0 truncate text-sm text-text-muted" aria-live="polite">
              {arquivo ? arquivo.name : "Nenhum arquivo escolhido."}
            </span>
            <Button
              className="ml-auto"
              onClick={enviar}
              disabled={!arquivo || !!erroArquivo || ocupado}
              loading={etapa.tipo === "enviando"}
            >
              Importar
            </Button>
          </div>
        )}

        {erroArquivo && (
          <p role="alert" className="text-sm text-error-text">
            {erroArquivo}
          </p>
        )}

        {etapa.tipo === "enviando" && (
          <ProgressBar
            value={etapa.percentual}
            label="Envio da planilha"
            valueText={`${etapa.percentual}% enviado`}
          />
        )}

        {etapa.tipo === "acompanhando" && (
          <div className="space-y-4" data-testid="arlo-acompanhamento">
            <div className="flex flex-wrap items-center gap-3">
              {!operacao || !terminou ? (
                <Spinner className="h-4 w-4 text-primary" />
              ) : operacao.status === "concluido" ? (
                <CheckCircle2 className="h-5 w-5 text-success-text" aria-hidden />
              ) : (
                <XCircle className="h-5 w-5 text-error-text" aria-hidden />
              )}
              <span className="text-sm font-medium text-text">
                {arquivo?.name ?? operacao?.nome_original}
              </span>
              {operacao && <StatusOperacao operacao={operacao} />}
              {terminou && (
                <Button variant="ghost" size="sm" className="ml-auto" onClick={novaImportacao}>
                  Importar outra planilha
                </Button>
              )}
            </div>

            {!terminou && (
              <p className="text-sm text-text-muted" aria-live="polite">
                Processando a planilha. Você pode sair desta tela: o resultado fica no histórico.
              </p>
            )}

            {acompanhamento.isError && (
              <p role="alert" className="text-sm text-error-text">
                Não foi possível acompanhar a importação.{" "}
                <button type="button" className="font-medium underline" onClick={() => void acompanhamento.refetch()}>
                  Tentar novamente
                </button>
              </p>
            )}

            {operacao?.status === "falhou" && (
              <p role="alert" className="text-sm text-error-text">
                {operacao.erros_json[0]?.erro ?? "O arquivo não pôde ser processado."}
              </p>
            )}

            {operacao?.status === "concluido" && <ErrosDaImportacao operacao={operacao} />}
          </div>
        )}
      </div>
    </section>
  );
}
