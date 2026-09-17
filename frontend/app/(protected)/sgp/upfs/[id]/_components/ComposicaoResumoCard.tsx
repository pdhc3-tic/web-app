"use client";

import { useId } from "react";
import { AlertTriangle } from "lucide-react";
import {
  FAIXAS_ETARIAS,
  type FaixaEtariaKey,
  type ResumoMembros,
} from "@/app/lib/membros";

type Props = {
  /** Resposta de BE-23; `null` enquanto carrega ou quando a chamada falhou. */
  resumo: ResumoMembros | null;
  loading: boolean;
  /**
   * UPF sem Titular. `null` sempre que o resumo estiver em voo — na primeira
   * carga e nas revalidações — e nesse estado o alerta não é renderizado, para
   * não afirmar nada antes de a consulta concluir.
   *
   * Vem do pai porque, quando o resumo falha, ele ainda consegue derivar o
   * sinal da listagem — o alerta é a parte que não pode sumir por causa de uma
   * request que deu errado.
   */
  semTitular: boolean | null;
  onRetry: () => void;
};

/**
 * Card-resumo no topo da aba Membros (FE-23): total de membros, distribuição
 * por faixa etária e o alerta de UPF sem Titular.
 *
 * Os números vêm do endpoint `membros/resumo/` e não de contagens sobre a
 * listagem: a agregação por idade é feita no banco, sobre `data_nascimento`, e
 * refazê-la aqui só criaria duas verdades para o mesmo indicador.
 */
export function ComposicaoResumoCard({
  resumo,
  loading,
  semTitular,
  onRetry,
}: Props) {
  const tituloId = useId();

  return (
    <section
      data-testid="membros-resumo"
      aria-labelledby={tituloId}
      // Na revalidação os números anteriores seguem na tela em vez de virar
      // skeleton — o que muda de fato é raramente a faixa inteira, e piscar o
      // card a cada gravação custa mais do que informa. `aria-busy` é o que
      // conta ao leitor de tela que o conteúdo visível está sendo conferido.
      aria-busy={loading || undefined}
      className="space-y-3 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 id={tituloId} className="text-sm font-semibold text-text">
          Composição familiar
        </h3>
        {resumo && (
          <p className="text-sm text-text-muted">
            <span
              data-testid="membros-resumo-total"
              className="text-base font-semibold tabular-nums text-text"
            >
              {resumo.total_membros}
            </span>{" "}
            {resumo.total_membros === 1 ? "membro" : "membros"}
          </p>
        )}
      </div>

      {loading && !resumo && <ResumoSkeleton />}

      {!loading && !resumo && (
        <div className="flex flex-wrap items-center gap-2 text-sm text-text-muted">
          <span>Não foi possível carregar o resumo da composição.</span>
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md text-sm font-medium text-primary underline underline-offset-2 transition hover:text-secondary"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {resumo && (
        <ul className="flex flex-wrap gap-2">
          {FAIXAS_ETARIAS.map(({ key, label }) => (
            <li key={key}>
              <FaixaPill
                faixa={key}
                label={label}
                total={resumo.faixa_etaria[key] ?? 0}
              />
            </li>
          ))}
        </ul>
      )}

      {/* `=== true` e não truthy: `null` é "ainda não sei" — inclusive durante
          uma revalidação, quando o resumo em memória ainda é o de antes da
          gravação —, e nesse estado o alerta fica fora da tela em vez de ser
          afirmado por antecipação. */}
      {semTitular === true && <AlertaSemTitular />}
    </section>
  );
}

/**
 * Pastilha de uma faixa etária. Faixa zerada continua visível, em tom apagado:
 * "nenhuma criança" é informação, e esconder a linha faria a lista dançar a
 * cada cadastro.
 */
function FaixaPill({
  faixa,
  label,
  total,
}: {
  faixa: FaixaEtariaKey;
  label: string;
  total: number;
}) {
  return (
    <span
      data-testid={`membros-resumo-faixa-${faixa}`}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
        total > 0 ? "bg-surface-muted text-text" : "bg-surface-muted/60 text-text-muted"
      }`}
    >
      <span className="text-sm leading-none tabular-nums">{total}</span>
      {label}
    </span>
  );
}

/** Paleta "Atenção" do design system — a UPF precisa de um Titular. */
function AlertaSemTitular() {
  return (
    <p
      role="status"
      data-testid="membros-sem-titular-alerta"
      className="flex items-start gap-2 rounded-md border border-warning-text bg-warning-bg px-3 py-2 text-sm text-warning-text"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span>
        <strong className="font-semibold">Esta UPF não tem Titular.</strong>{" "}
        Cadastre o Titular da família ou edite um membro já cadastrado para o
        grau de parentesco &ldquo;Titular&rdquo;.
      </span>
    </p>
  );
}

function ResumoSkeleton() {
  return (
    <div className="flex flex-wrap gap-2" data-testid="membros-resumo-loading">
      {FAIXAS_ETARIAS.map(({ key }) => (
        <div key={key} className="h-7 w-28 rounded-full bg-surface-muted" />
      ))}
    </div>
  );
}
