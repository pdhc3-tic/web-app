"use client";

import { useState } from "react";
import { Button } from "@/app/components/ui/Button/Button";
import { formatDate } from "@/app/lib/datetime";
import {
  ORIGEM_LABEL,
  hojeIso,
  montarGrade,
  situacaoDoValor,
  valorEditavel,
  type FaixaDestino,
  type OrigemValorDiaria,
  type SituacaoDoValor,
  type ValorDiaria,
} from "@/app/lib/diarias";
import { formatCurrencyBRL } from "@/app/lib/format";

const SITUACAO_LABEL: Record<SituacaoDoValor, string> = {
  vigente: "Vigente",
  futuro: "Ainda não vigora",
  encerrado: "Encerrado",
};

function Origem({ origem }: { origem: OrigemValorDiaria }) {
  const cor = origem === "federal" ? "bg-info-bg text-info-text" : "bg-warning-bg text-warning-text";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${cor}`}>{ORIGEM_LABEL[origem]}</span>
  );
}

type Props = {
  faixas: FaixaDestino[];
  valores: ValorDiaria[];
  /** Abre o diálogo de valor: com `atual`, é uma nova vigência; sem ele, o primeiro valor da faixa. */
  onEditar: (faixa: FaixaDestino, atual: ValorDiaria | null) => void;
  /** Só para o valor que ainda não vigorou. */
  onExcluir: (valor: ValorDiaria) => void;
  /** Hoje em `AAAA-MM-DD`; parâmetro para o teste fixar a data. */
  hoje?: string;
};

/**
 * Tabela de valores em grade: faixa de destino × vigência (#366). Cada coluna
 * é uma data em que algum valor passou a valer; a célula mostra o valor da
 * faixa naquela data e a origem dele. O histórico completo de cada faixa abre
 * abaixo da linha.
 */
export function GradeValores({ faixas, valores, onEditar, onExcluir, hoje = hojeIso() }: Props) {
  const [aberta, setAberta] = useState<number | null>(null);
  const grade = montarGrade(faixas, valores);
  const colunas = grade.vigencias.length + 2;

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full min-w-[640px] text-sm" data-testid="grade-diarias">
        <caption className="sr-only">Valores da diária por faixa de destino e vigência</caption>
        <thead>
          <tr className="border-b border-border bg-surface-muted/50 text-left text-xs text-text-muted">
            <th scope="col" className="px-4 py-2.5 font-medium">
              Faixa de destino
            </th>
            {grade.vigencias.map((data) => (
              <th key={data} scope="col" className="px-4 py-2.5 font-medium tabular-nums">
                A partir de {formatDate(data)}
              </th>
            ))}
            <th scope="col" className="px-4 py-2.5 text-right font-medium">
              Ações
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {grade.linhas.map(({ faixa, celulas, historico }) => {
            const atual = valorEditavel(historico, hoje);
            const expandida = aberta === faixa.id;
            return (
              <FaixaLinhas
                key={faixa.id}
                faixa={faixa}
                celulas={celulas}
                historico={historico}
                atual={atual}
                hoje={hoje}
                colunas={colunas}
                expandida={expandida}
                onAlternar={() => setAberta(expandida ? null : faixa.id)}
                onEditar={onEditar}
                onExcluir={onExcluir}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

type LinhaProps = {
  faixa: FaixaDestino;
  celulas: ReturnType<typeof montarGrade>["linhas"][number]["celulas"];
  historico: ValorDiaria[];
  atual: ValorDiaria | null;
  hoje: string;
  colunas: number;
  expandida: boolean;
  onAlternar: () => void;
  onEditar: Props["onEditar"];
  onExcluir: Props["onExcluir"];
};

function FaixaLinhas({
  faixa,
  celulas,
  historico,
  atual,
  hoje,
  colunas,
  expandida,
  onAlternar,
  onEditar,
  onExcluir,
}: LinhaProps) {
  return (
    <>
      <tr data-testid={`grade-faixa-${faixa.id}`}>
        <th scope="row" className="px-4 py-3 text-left font-medium text-text">
          {faixa.nome}
          {!faixa.ativo && <span className="ml-2 text-xs font-normal text-text-muted">(inativa)</span>}
        </th>
        {celulas.map((celula, i) => (
          <td key={i} className="px-4 py-3 align-top" data-testid={`grade-celula-${faixa.id}-${i}`}>
            {celula ? (
              <div className={`flex flex-col items-start gap-1 ${celula.iniciaAqui ? "" : "opacity-60"}`}>
                <span className="tabular-nums text-text">{formatCurrencyBRL(celula.valor.valor)}</span>
                <Origem origem={celula.valor.origem} />
                {!celula.iniciaAqui && (
                  <span className="text-xs text-text-muted">desde {formatDate(celula.valor.vigencia_inicio)}</span>
                )}
              </div>
            ) : (
              <span className="text-text-muted" aria-label="Sem valor nesta vigência">
                –
              </span>
            )}
          </td>
        ))}
        <td className="px-4 py-3 text-right align-top">
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onEditar(faixa, atual)}
              data-testid={`grade-editar-${faixa.id}`}
            >
              {atual ? "Editar valor" : "Cadastrar valor"}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onAlternar}
              aria-expanded={expandida}
              disabled={historico.length === 0}
              data-testid={`grade-historico-${faixa.id}`}
            >
              Histórico
            </Button>
          </div>
        </td>
      </tr>
      {expandida && (
        <tr>
          <td colSpan={colunas} className="bg-surface-muted/40 px-4 py-3">
            <table className="w-full text-sm" data-testid={`historico-faixa-${faixa.id}`}>
              <caption className="pb-2 text-left text-xs font-semibold text-text-muted">
                Histórico de vigências de {faixa.nome}
              </caption>
              <thead>
                <tr className="text-left text-xs text-text-muted">
                  <th scope="col" className="py-1 pr-4 font-medium">Vigência</th>
                  <th scope="col" className="py-1 pr-4 font-medium">Valor</th>
                  <th scope="col" className="py-1 pr-4 font-medium">Origem</th>
                  <th scope="col" className="py-1 pr-4 font-medium">Situação</th>
                  <th scope="col" className="py-1 pr-4 font-medium">Cadastrado por</th>
                  <th scope="col" className="py-1 font-medium">
                    <span className="sr-only">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {historico.map((v) => {
                  const situacao = situacaoDoValor(v, hoje);
                  return (
                    <tr key={v.id} data-testid={`historico-valor-${v.id}`}>
                      <td className="py-1.5 pr-4 tabular-nums text-text">
                        {formatDate(v.vigencia_inicio)} a {v.vigencia_fim ? formatDate(v.vigencia_fim) : "em aberto"}
                      </td>
                      <td className="py-1.5 pr-4 tabular-nums text-text">{formatCurrencyBRL(v.valor)}</td>
                      <td className="py-1.5 pr-4">
                        <Origem origem={v.origem} />
                      </td>
                      <td className="py-1.5 pr-4 text-text-muted">{SITUACAO_LABEL[situacao]}</td>
                      <td className="py-1.5 pr-4 text-text-muted">{v.criado_por_nome ?? "Carga inicial"}</td>
                      <td className="py-1.5 text-right">
                        {situacao === "futuro" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onExcluir(v)}
                            data-testid={`historico-excluir-${v.id}`}
                          >
                            Excluir
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}
