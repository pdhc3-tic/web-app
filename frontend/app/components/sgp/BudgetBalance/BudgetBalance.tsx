"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Ban, Wallet } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { ApiError } from "@/app/lib/api";
import { isAdtAcr } from "@/app/lib/auth/roles";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  BLOQUEIO_SALDO_ZERO,
  fetchSaldoPorRubrica,
  type SaldoRubrica,
} from "@/app/lib/orcamento";
import { useSession } from "next-auth/react";

type Props = {
  /**
   * Meta cujo saldo será exibido. Obrigatória: cada Meta tem teto próprio, e
   * uma rubrica somada entre Metas não autoriza gasto nenhum.
   */
  metaId: number | string | null;
  /** Cabeçalho do card. O SGD passará o seu próprio ao embutir o componente. */
  titulo?: string;
};

/**
 * Saldo por rubrica no contexto do território (Issue #232).
 *
 * Componente autônomo: busca os próprios dados e resolve os próprios estados de
 * carga, erro e vazio. É assim porque o formulário de demanda do SGD vai
 * embuti-lo sem herdar nada da tela de orçamento — a única entrada é a Meta.
 *
 * ─── Por que o "sem território" sai da SESSÃO, e não da API ─────────────────
 *
 * `resolver_nivel_painel` responde 403 a um ADT/ACR sem território, com a MESMA
 * mensagem que devolve a quem não tem acesso nenhum ao orçamento. Pela resposta
 * é impossível separar "você não tem território" de "esta tela não é para o seu
 * perfil" — e os dois pedem telas diferentes: estado vazio explicativo no
 * primeiro caso, RestrictedAccess no segundo.
 *
 * A sessão já sabe a diferença: `user.territorios` vem do /me. Então o
 * componente decide ANTES de chamar a API e nem gasta a requisição.
 */
export function BudgetBalance({ metaId, titulo = "Saldo por rubrica" }: Props) {
  const { data: session, status } = useSession();
  const sessaoCarregando = status === "loading";
  const user = session?.user;

  // Só o ADT/ACR depende de território para ter saldo; os demais perfis são
  // resolvidos pelo backend em nível estadual ou nacional.
  const semTerritorio =
    !sessaoCarregando && isAdtAcr(user) && (user?.territorios ?? []).length === 0;

  const [saldos, setSaldos] = useState<SaldoRubrica[] | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);

  const recarregar = useCallback(() => setTentativa((n) => n + 1), []);

  useEffect(() => {
    if (sessaoCarregando || semTerritorio || metaId === null || metaId === "") {
      return;
    }

    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCarregando(true);
    setErro(null);

    fetchSaldoPorRubrica(metaId, controller.signal)
      .then((lista) => {
        if (controller.signal.aborted) return;
        setSaldos(lista);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setSaldos(null);
        setErro(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar o saldo das rubricas.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setCarregando(false);
      });

    return () => controller.abort();
  }, [metaId, sessaoCarregando, semTerritorio, tentativa]);

  const bloqueadas = useMemo(
    () => (saldos ?? []).filter((s) => s.bloqueada).length,
    [saldos],
  );

  return (
    <section
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4"
      data-testid="budget-balance"
      aria-labelledby="budget-balance-titulo"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2
          id="budget-balance-titulo"
          className="inline-flex items-center gap-2 text-base font-semibold text-text"
        >
          <Wallet className="h-4 w-4 text-text-muted" aria-hidden="true" />
          {titulo}
        </h2>
        {saldos && bloqueadas > 0 && (
          <span className="text-xs text-text-muted" data-testid="budget-balance-resumo">
            {bloqueadas} de {saldos.length}{" "}
            {bloqueadas === 1 ? "rubrica bloqueada" : "rubricas bloqueadas"}
          </span>
        )}
      </header>

      <Corpo
        sessaoCarregando={sessaoCarregando}
        semTerritorio={semTerritorio}
        semMeta={metaId === null || metaId === ""}
        carregando={carregando}
        erro={erro}
        saldos={saldos}
        onRetry={recarregar}
      />
    </section>
  );
}

// ─── Corpo: um estado por vez, na ordem em que se resolvem ──────────────────

function Corpo({
  sessaoCarregando,
  semTerritorio,
  semMeta,
  carregando,
  erro,
  saldos,
  onRetry,
}: {
  sessaoCarregando: boolean;
  semTerritorio: boolean;
  semMeta: boolean;
  carregando: boolean;
  erro: string | null;
  saldos: SaldoRubrica[] | null;
  onRetry: () => void;
}) {
  if (sessaoCarregando || (carregando && !saldos)) {
    return <SaldoSkeleton />;
  }

  if (semTerritorio) {
    return (
      <EmptyState
        icon={<Wallet className="h-6 w-6" aria-hidden="true" />}
        title="Nenhum território atribuído"
        description="O saldo é apurado por território. Peça ao gestor do projeto para vincular o seu perfil a um território para acompanhar as rubricas."
      />
    );
  }

  if (semMeta) {
    return (
      <EmptyState
        icon={<Wallet className="h-6 w-6" aria-hidden="true" />}
        title="Selecione uma Meta"
        description="Cada Meta tem teto próprio — escolha uma para ver o saldo das rubricas."
      />
    );
  }

  if (erro) {
    return (
      <div
        className="flex flex-col items-center gap-3 rounded-md border border-border px-4 py-8 text-center"
        role="alert"
        data-testid="budget-balance-erro"
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-error-bg text-error-text">
          <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        </span>
        <p className="max-w-sm text-sm text-text-muted">{erro}</p>
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          data-testid="budget-balance-retry"
        >
          Tentar novamente
        </Button>
      </div>
    );
  }

  if (!saldos || saldos.length === 0) {
    return (
      <EmptyState
        icon={<Wallet className="h-6 w-6" aria-hidden="true" />}
        title="Sem rubricas nesta Meta"
        description="Nenhuma rubrica foi encontrada para a Meta selecionada."
      />
    );
  }

  return (
    <ul
      className="flex list-none flex-col gap-1.5"
      data-testid="budget-balance-lista"
    >
      {saldos.map((item) => (
        <LinhaRubrica key={item.rubrica.slug} item={item} />
      ))}
    </ul>
  );
}

// ─── Uma rubrica ────────────────────────────────────────────────────────────

function LinhaRubrica({ item }: { item: SaldoRubrica }) {
  const { rubrica, saldo, bloqueada, negativa } = item;

  return (
    <li
      className={`flex flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-md border px-3 py-2 ${
        bloqueada ? "border-border bg-surface-muted/50" : "border-border bg-surface"
      }`}
      data-testid={`budget-balance-rubrica-${rubrica.slug}`}
      data-bloqueada={bloqueada ? "true" : "false"}
    >
      <span
        className={`inline-flex items-center gap-1.5 text-sm ${
          bloqueada ? "text-text-muted" : "text-text"
        }`}
      >
        {bloqueada && (
          <Ban className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        )}
        {rubrica.nome}
      </span>

      <span
        className={`text-sm font-semibold tabular-nums ${
          negativa
            ? "text-error-text"
            : bloqueada
              ? "text-text-muted"
              : "text-text"
        }`}
        data-testid={`budget-balance-valor-${rubrica.slug}`}
      >
        {formatCurrencyBRL(saldo)}
      </span>

      {/* A razão fica na própria linha, e não num tooltip: o critério pede que
          ela seja explícita, e um bloqueio que só aparece no hover não é. */}
      {bloqueada && (
        <p
          className="w-full text-xs text-text-muted"
          data-testid={`budget-balance-motivo-${rubrica.slug}`}
        >
          {negativa
            ? `Saldo negativo por remanejamento. ${BLOQUEIO_SALDO_ZERO}`
            : BLOQUEIO_SALDO_ZERO}
        </p>
      )}
    </li>
  );
}

// ─── Skeleton ───────────────────────────────────────────────────────────────

const RUBRICAS = 6;

/**
 * Reproduz as seis linhas em vez de um spinner: o número de rubricas é fixo, e
 * a forma certa evita o salto de layout quando os valores chegam.
 */
function SaldoSkeleton() {
  return (
    <div
      className="flex flex-col gap-1.5"
      aria-busy="true"
      aria-label="Carregando o saldo das rubricas"
      data-testid="budget-balance-skeleton"
    >
      {Array.from({ length: RUBRICAS }).map((_, i) => (
        <div
          key={i}
          className="flex items-center justify-between rounded-md border border-border px-3 py-2.5"
        >
          <div
            className="h-3.5 animate-pulse rounded bg-surface-muted"
            style={{ width: `${7 + (i % 3) * 2}rem` }}
          />
          <div className="h-3.5 w-20 animate-pulse rounded bg-surface-muted" />
        </div>
      ))}
    </div>
  );
}
