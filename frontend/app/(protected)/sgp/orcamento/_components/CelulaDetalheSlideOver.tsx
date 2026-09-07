"use client";

import { useEffect, useState } from "react";
import { Layers } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  fetchOrcamentoDaMeta,
  labelSemaforoOrcamento,
  nivelOrcamentoLabel,
  valorNumerico,
  type AlocacaoApi,
  type RubricaOrcamentoApi,
} from "@/app/lib/orcamento";
import { formatPercentual } from "@/app/lib/semaforo";
import type { CelulaOrcamento } from "./tipos";

type Props = {
  celula: CelulaOrcamento | null;
  onClose: () => void;
  /**
   * ADT/ACR: suprime a seção nacional.
   *
   * `GET /sgp/metas/{id}/orcamento/` ENTREGA os agregados nacionais a qualquer
   * perfil — o backend considera que nacional não é dado sensível por
   * território (§B2). O critério de aceite desta tela é mais estrito ("sem
   * colunas ou controles de outros níveis"), e é ele que vale aqui. O
   * `detalhamento` já vem recortado pelo backend, então a lista de níveis
   * abaixo nunca precisou de filtro nosso.
   */
  soTerritorio: boolean;
};

/** Nome do escopo de uma alocação: "Pernambuco (PE)" ou o nome do território. */
function escopoDaAlocacao(alocacao: AlocacaoApi): string {
  if (alocacao.territorio) return alocacao.territorio.nome;
  if (alocacao.estado) return `${alocacao.estado.nome} (${alocacao.estado.sigla})`;
  return "Nacional";
}

function LinhaNivel({ alocacao }: { alocacao: AlocacaoApi }) {
  const saldo = valorNumerico(alocacao.saldo_disponivel);

  return (
    <li
      className="rounded-md border border-border bg-surface p-3"
      data-testid={`orcamento-detalhe-alocacao-${alocacao.id}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium text-text">
          {escopoDaAlocacao(alocacao)}
        </span>
        <span className="shrink-0 rounded-full bg-surface-muted px-2 py-0.5 text-2xs font-medium uppercase tracking-[0.06em] text-text-muted">
          {nivelOrcamentoLabel(alocacao.nivel)}
        </span>
      </div>

      <DefinitionList
        className="mt-2 text-xs"
        items={[
          { label: "Alocado", value: formatCurrencyBRL(alocacao.valor_alocado) },
          {
            label: "Comprometido",
            value: formatCurrencyBRL(alocacao.valor_comprometido),
          },
          {
            label: "Executado",
            value: formatCurrencyBRL(alocacao.valor_executado),
          },
          {
            label: "Disponível",
            value: (
              <span className={saldo < 0 ? "text-error-text" : undefined}>
                {formatCurrencyBRL(alocacao.saldo_disponivel)}
              </span>
            ),
          },
        ]}
      />
    </li>
  );
}

/**
 * Drill-down de uma célula da matriz: como aquele valor se reparte entre os
 * níveis.
 *
 * A matriz mostra UM nível por vez — é o que o endpoint do painel devolve. Este
 * painel responde a pergunta que a matriz não responde: de onde veio e para
 * onde desceu o dinheiro daquela Meta/Rubrica. Vem de outro endpoint
 * (`/sgp/metas/{id}/orcamento/`), buscado só quando o SlideOver abre — carregar
 * o detalhamento das ~42 células junto com a matriz seria pagar adiantado por
 * algo que o gestor abre uma ou duas vezes.
 */
export function CelulaDetalheSlideOver({ celula, onClose, soTerritorio }: Props) {
  const [rubricas, setRubricas] = useState<RubricaOrcamentoApi[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const metaId = celula?.linha.meta.id ?? null;

  useEffect(() => {
    if (metaId === null) return;

    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setErro(null);
    // Zera o detalhamento anterior: sem isto, abrir outra célula mostraria por
    // um instante os níveis da célula anterior sob o novo título.
    setRubricas(null);

    fetchOrcamentoDaMeta(metaId, controller.signal)
      .then(setRubricas)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setErro(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar o detalhamento.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [metaId]);

  const linha = celula?.linha ?? null;
  // A resposta traz todas as rubricas da Meta; a célula clicada é uma delas.
  const daRubrica = linha
    ? rubricas?.find((r) => r.rubrica.slug === linha.rubrica.slug)
    : undefined;
  const detalhamento = daRubrica?.detalhamento ?? [];

  // O SlideOver anima o próprio fechamento e só desmonta ao fim da transição:
  // devolver `null` aqui quando não há célula cortaria essa animação pela
  // metade. Mesmo padrão do AcaoDetalheSlideOver do painel do PT.
  return (
    <SlideOver
      open={celula !== null}
      onClose={onClose}
      title={
        linha ? `${linha.rubrica.nome} — Meta ${linha.meta.numero}` : "Orçamento"
      }
      width="wide"
      badge={
        celula ? (
          <SemaforoBadge
            nivel={celula.nivelSemaforo}
            label={labelSemaforoOrcamento(celula.nivelSemaforo)}
          />
        ) : undefined
      }
    >
      {linha === null ? null : (
      <div className="flex flex-col gap-5" data-testid="orcamento-detalhe">
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-text-muted">
            Nível exibido na matriz — {nivelOrcamentoLabel(linha.nivel)}
          </h3>
          <DefinitionList
            items={[
              { label: "Aprovado", value: formatCurrencyBRL(linha.valor_aprovado) },
              {
                label: "Distribuído",
                value: formatCurrencyBRL(linha.valor_distribuido),
              },
              {
                label: "Comprometido",
                value: `${formatCurrencyBRL(linha.valor_comprometido)} (${formatPercentual(celula?.percentual ?? null)})`,
              },
              {
                label: "Executado",
                value: formatCurrencyBRL(linha.valor_executado),
              },
              {
                label: "Disponível",
                value: (
                  <span
                    className={
                      valorNumerico(linha.saldo_disponivel) < 0
                        ? "text-error-text"
                        : undefined
                    }
                  >
                    {formatCurrencyBRL(linha.saldo_disponivel)}
                  </span>
                ),
              },
            ]}
          />
        </section>

        {/* Nacional consolidado: o mesmo dado que a matriz já mostra quando o
            usuário está no nível nacional, mas que some da vista assim que ele
            desce um nível. Aqui ele volta como referência do teto. */}
        {!soTerritorio && daRubrica && (
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-text-muted">
              Consolidado nacional da rubrica
            </h3>
            <DefinitionList
              items={[
                {
                  label: "Aprovado",
                  value: formatCurrencyBRL(daRubrica.valor_aprovado),
                },
                {
                  label: "Distribuído aos estados",
                  value: formatCurrencyBRL(daRubrica.valor_distribuido),
                },
                {
                  label: "Disponível",
                  value: formatCurrencyBRL(daRubrica.saldo_disponivel),
                },
              ]}
            />
          </section>
        )}

        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-text-muted">
            Detalhamento por nível
          </h3>

          {loading ? (
            <div className="flex justify-center py-8">
              <Spinner className="h-5 w-5 animate-spin text-text-muted" />
            </div>
          ) : erro ? (
            <p className="rounded-md border border-border bg-error-bg px-3 py-2 text-sm text-error-text">
              {erro}
            </p>
          ) : detalhamento.length === 0 ? (
            <EmptyState
              icon={<Layers className="h-6 w-6" />}
              title="Sem distribuição para os níveis abaixo"
              description={
                soTerritorio
                  ? "Esta rubrica ainda não recebeu alocação no seu território."
                  : "O valor desta rubrica ainda não foi distribuído para estados ou territórios."
              }
            />
          ) : (
            <ul
              className="flex flex-col gap-2"
              data-testid="orcamento-detalhe-niveis"
            >
              {detalhamento.map((alocacao) => (
                <LinhaNivel key={alocacao.id} alocacao={alocacao} />
              ))}
            </ul>
          )}
        </section>
      </div>
      )}
    </SlideOver>
  );
}
