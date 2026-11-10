"use client";

import { FileText, HandCoins } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { formatDate } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import { pedeRecursoExtra, type SaldoDaRubrica, type SemaforoSaldo } from "@/app/lib/meuSaldo";
import { valorNumerico } from "@/app/lib/orcamento";

const ROTULO_SEMAFORO: Record<SemaforoSaldo, string> = {
  verde: "Com folga",
  amarelo: "Atenção",
  vermelho: "Crítico",
};

type Props = {
  saldo: SaldoDaRubrica;
  onExtrato: () => void;
  onRecursoExtra: () => void;
};

function Valor({ rotulo, valor, destaque }: { rotulo: string; valor: string; destaque?: boolean }) {
  const negativo = valorNumerico(valor) < 0;
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-2xs font-medium uppercase tracking-[0.06em] text-text-muted">{rotulo}</dt>
      <dd
        className={`tabular-nums ${destaque ? "text-lg font-semibold" : "text-sm"} ${
          negativo ? "text-error-text" : "text-text"
        }`}
      >
        {formatCurrencyBRL(valor)}
      </dd>
    </div>
  );
}

/**
 * Card de uma rubrica do "Meu saldo" (#401): limite, comprometido, executado,
 * disponível e semáforo, como o backend calculou. Amarelo ou vermelho ganham o
 * atalho do recurso extra (#321).
 */
export function CardSaldo({ saldo, onExtrato, onRecursoExtra }: Props) {
  return (
    <article
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5"
      data-testid={`meu-saldo-card-${saldo.rubrica}`}
      data-semaforo={saldo.semaforo}
      aria-labelledby={`meu-saldo-${saldo.rubrica}-titulo`}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id={`meu-saldo-${saldo.rubrica}-titulo`} className="text-sm font-semibold text-text">
            {saldo.rubrica_nome}
          </h2>
          {!saldo.rubrica_ativa && (
            <p className="text-xs text-text-muted">Rubrica inativa: não recebe demandas novas.</p>
          )}
        </div>
        <SemaforoBadge nivel={saldo.semaforo} label={ROTULO_SEMAFORO[saldo.semaforo]} />
      </header>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        <div className="col-span-2" data-testid="meu-saldo-disponivel">
          <Valor rotulo="Disponível" valor={saldo.disponivel} destaque />
        </div>
        <Valor rotulo="Limite" valor={saldo.limite} />
        <div data-testid="meu-saldo-comprometido">
          <Valor rotulo="Comprometido" valor={saldo.comprometido} />
        </div>
        <Valor rotulo="Executado" valor={saldo.executado} />
      </dl>

      <ul className="flex flex-col gap-1 text-xs text-text-muted">
        <li>
          {saldo.periodo_fim
            ? `Período até ${formatDate(saldo.periodo_fim)}${
                saldo.dias_restantes !== null
                  ? ` (${saldo.dias_restantes} dia${saldo.dias_restantes === 1 ? "" : "s"})`
                  : ""
              }`
            : `Período desde ${formatDate(saldo.periodo_inicio)}, sem fim definido`}
          {saldo.acumula_saldo && " · o saldo não usado passa para o período seguinte"}
        </li>
        {saldo.saldo_territorio !== null && (
          <li title="Mesmo com limite, a reserva também precisa caber no pool do território.">
            Pool do território: {formatCurrencyBRL(saldo.saldo_territorio)}
          </li>
        )}
      </ul>

      <footer className="mt-auto flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="secondary"
          leftIcon={<FileText className="h-4 w-4" />}
          onClick={onExtrato}
          data-testid="meu-saldo-ver-extrato"
        >
          Ver extrato
        </Button>
        {pedeRecursoExtra(saldo) && (
          <Button
            size="sm"
            variant="secondary"
            leftIcon={<HandCoins className="h-4 w-4" />}
            onClick={onRecursoExtra}
            data-testid="meu-saldo-recurso-extra"
          >
            Solicitar recurso extra
          </Button>
        )}
      </footer>
    </article>
  );
}
