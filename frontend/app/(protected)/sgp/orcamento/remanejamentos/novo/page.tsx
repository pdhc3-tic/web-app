"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { AlertTriangle, ArrowRight, CheckCircle2 } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { canRemanejarOrcamento } from "@/app/lib/auth/roles";
import { useDebounced } from "@/app/lib/hooks/useDebounced";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import {
  fetchPainelOrcamento,
  nomeDoPool,
  type PoolOrcamentoApi,
} from "@/app/lib/orcamento";
import { ApiError } from "@/app/lib/api";
import {
  confirmarRemanejamento,
  mensagemDeErro,
  simularRemanejamento,
  type ImpactoNoPool,
  type SimulacaoPayload,
} from "@/app/lib/remanejamentoSgp";

type Form = {
  origem: string;
  destino: string;
  valor: string;
  justificativa: string;
};

const FORM_VAZIO: Form = { origem: "", destino: "", valor: "", justificativa: "" };

/** Espera depois da última mudança antes de simular. */
const ATRASO_DA_SIMULACAO_MS = 500;

/** O que a simulação pede: origem, destino e valor. A justificativa fica para a confirmação. */
function simulacaoDoForm(form: Form): SimulacaoPayload | null {
  const origem_allocation = Number(form.origem);
  const destino_allocation = Number(form.destino);
  if (
    !origem_allocation ||
    !destino_allocation ||
    origem_allocation === destino_allocation ||
    !(Number(form.valor) > 0)
  ) {
    return null;
  }
  return { origem_allocation, destino_allocation, valor: form.valor };
}

const chaveDa = (p: SimulacaoPayload | null) =>
  p ? `${p.origem_allocation}|${p.destino_allocation}|${p.valor}` : "";

/**
 * O saldo da opção é o `saldo_pool` (alocado menos comprometido e executado):
 * é o que o backend aceita tirar da origem. O `saldo_disponivel` do painel
 * desconta também o que já foi distribuído aos níveis de baixo.
 */
function opcoesDePool(pools: PoolOrcamentoApi[]): SelectOption[] {
  return pools.map((p) => ({
    value: String(p.id),
    label: `${nomeDoPool(p)}${p.reserva_ugp ? " (reserva UGP)" : ""} · ${p.rubrica.nome} · saldo ${formatCurrencyBRL(p.saldo_pool)}`,
  }));
}

/** O backend só remaneja dentro da mesma rubrica. */
function destinosPossiveis(pools: PoolOrcamentoApi[], origem: PoolOrcamentoApi | undefined) {
  if (!origem) return [];
  return pools.filter((p) => p.id !== origem.id && p.rubrica.id === origem.rubrica.id);
}

function CartaoImpacto({
  titulo,
  impacto,
  testId,
}: {
  titulo: string;
  impacto: ImpactoNoPool;
  testId: string;
}) {
  const mudouFaixa = impacto.faixa_antes !== impacto.faixa_depois;
  return (
    <div
      className="rounded-lg border border-border bg-surface p-4"
      data-testid={testId}
    >
      <h3 className="text-sm font-semibold text-text">{titulo}</h3>
      <dl className="mt-3 grid grid-cols-[auto_1fr_auto_1fr] gap-x-3 gap-y-2 text-sm">
        <dt className="text-text-muted">Saldo</dt>
        <dd className="tabular-nums text-text" data-testid={`${testId}-saldo-antes`}>
          {formatCurrencyBRL(impacto.saldo_antes)}
        </dd>
        <dd className="text-text-muted">→</dd>
        <dd className="font-medium tabular-nums text-text" data-testid={`${testId}-saldo-depois`}>
          {formatCurrencyBRL(impacto.saldo_depois)}
        </dd>

        <dt className="text-text-muted">Comprometido</dt>
        <dd className="tabular-nums text-text">{impacto.percentual_antes}%</dd>
        <dd className="text-text-muted">→</dd>
        <dd className="font-medium tabular-nums text-text">{impacto.percentual_depois}%</dd>
      </dl>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <SemaforoBadge nivel={impacto.faixa_antes} label="Antes" />
        <ArrowRight className="h-4 w-4 text-text-muted" aria-hidden />
        <SemaforoBadge nivel={impacto.faixa_depois} label="Depois" />
        {mudouFaixa && (
          <span
            className="inline-flex items-center gap-1 text-xs text-warning-text"
            data-testid={`${testId}-mudou-faixa`}
          >
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
            Faixa do semáforo mudou
          </span>
        )}
      </div>
    </div>
  );
}

function NovoRemanejamentoView() {
  const router = useRouter();
  const { data: session, status } = useSession();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const [form, setForm] = useState<Form>(FORM_VAZIO);
  const [confirmando, setConfirmando] = useState(false);
  const [erroConfirmacao, setErroConfirmacao] = useState<string | null>(null);

  const pools = useQuery({
    queryKey: qk.poolsDoRemanejamento,
    queryFn: ({ signal }) => fetchPainelOrcamento({}, signal),
    staleTime: 30_000,
    enabled: status === "authenticated" && canRemanejarOrcamento(session?.user),
  });

  const origemPool = pools.data?.find((p) => String(p.id) === form.origem);
  const opcoesOrigem = useMemo(() => opcoesDePool(pools.data ?? []), [pools.data]);
  const opcoesDestino = useMemo(
    () => opcoesDePool(destinosPossiveis(pools.data ?? [], origemPool)),
    [pools.data, origemPool],
  );
  const semPools = pools.isSuccess && pools.data.length === 0;

  // A simulação roda sozinha (#423, item 4): com origem, destino e valor, e só
  // depois de eles pararem de mudar. Mudar um deles refaz a simulação.
  const simulacaoAtual = simulacaoDoForm(form);
  const chaveAtual = chaveDa(simulacaoAtual);
  const chaveSimulada = useDebounced(chaveAtual, ATRASO_DA_SIMULACAO_MS);
  const emDia = chaveAtual !== "" && chaveAtual === chaveSimulada;
  const simulacaoQ = useQuery({
    queryKey: qk.simulacaoRemanejamento(chaveSimulada),
    queryFn: ({ signal }) => simularRemanejamento(simulacaoAtual!, signal),
    enabled: emDia,
    retry: false,
    staleTime: 0,
    gcTime: 0,
  });
  // Só vale a simulação dos campos de agora, sem erro e sem releitura em curso.
  const simulacao =
    emDia && !simulacaoQ.isError && !simulacaoQ.isFetching ? (simulacaoQ.data ?? null) : null;
  const simulando = chaveAtual !== "" && (!emDia || simulacaoQ.isFetching);
  const erro =
    erroConfirmacao ??
    (emDia && simulacaoQ.isError ? mensagemDeErro(simulacaoQ.error, "simular") : null);
  const podeConfirmar = simulacao !== null && form.justificativa.trim() !== "" && !confirmando;

  function atualizar<K extends keyof Form>(campo: K, valor: Form[K]) {
    setForm((prev) => {
      const proximo = { ...prev, [campo]: valor };
      if (campo === "origem") {
        // Trocar a origem descarta um destino que deixou de ser possível.
        const novaOrigem = pools.data?.find((p) => String(p.id) === valor);
        const aindaValido = destinosPossiveis(pools.data ?? [], novaOrigem).some(
          (p) => String(p.id) === prev.destino,
        );
        if (!aindaValido) proximo.destino = "";
      }
      return proximo;
    });
    setErroConfirmacao(null);
  }

  /**
   * O remanejamento muda o alocado de dois pools: recarrega as opções desta
   * tela, o painel e os saldos que o SGD mostra na montagem e na execução. A
   * confirmação ainda entra no histórico de remanejamentos (#466).
   */
  function recarregarSaldos() {
    void queryClient.invalidateQueries({ queryKey: ["sgp", "orcamento"] });
    void queryClient.invalidateQueries({ queryKey: qk.remanejamentos.all });
    void queryClient.invalidateQueries({ queryKey: ["sgd", "saldo"] });
    void queryClient.invalidateQueries({ queryKey: ["sgd", "execucao", "painel"] });
  }

  function saldoMudou(e: unknown) {
    return e instanceof ApiError && e.code === "INSUFFICIENT_BALANCE";
  }

  async function onConfirmar() {
    if (!simulacao || !simulacaoAtual || !form.justificativa.trim()) return;
    setConfirmando(true);
    setErroConfirmacao(null);
    try {
      // O payload da simulação exibida, mais a justificativa.
      await confirmarRemanejamento({ ...simulacaoAtual, justificativa: form.justificativa.trim() });
      recarregarSaldos();
      showToast("Remanejamento confirmado.", "success");
      router.push("/sgp/orcamento");
    } catch (e) {
      setErroConfirmacao(mensagemDeErro(e, "confirmar"));
      // O saldo mudou: recarregar os saldos refaz também a simulação.
      if (saldoMudou(e)) recarregarSaldos();
    } finally {
      setConfirmando(false);
    }
  }

  if (status === "loading") {
    return (
      <div
        role="status"
        className="flex min-h-[30vh] items-center justify-center gap-2 text-sm text-text-muted"
      >
        <Spinner className="h-5 w-5 animate-spin" />
        Carregando…
      </div>
    );
  }

  if (!canRemanejarOrcamento(session?.user)) {
    return (
      <RestrictedAccess description="O remanejamento entre pools é da UGP e do Super Admin." />
    );
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <Breadcrumb
        items={[
          { label: "Início", href: "/dashboard" },
          { label: "SGP", href: "/sgp" },
          { label: "Orçamento", href: "/sgp/orcamento" },
          { label: "Remanejamentos", href: "/sgp/orcamento/remanejamentos" },
          { label: "Novo remanejamento" },
        ]}
      />
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-text">Novo remanejamento</h1>
        <p className="mt-1 text-sm text-text-muted">
          Exceção à distribuição hierárquica: a UGP move saldo entre dois pools. Com origem,
          destino e valor, a simulação mostra o antes e depois com a mudança de faixa; a
          confirmação pede a justificativa e relê o saldo no servidor.
        </p>
      </header>

      {semPools && (
        <p
          className="rounded-md border border-border bg-surface-muted px-3 py-2.5 text-sm text-text-muted"
          data-testid="remanejamento-sem-pools"
        >
          Não há pools de orçamento para remanejar. Lance a{" "}
          <Link href="/sgp/orcamento/dotacao" className="text-primary hover:underline">
            dotação nacional
          </Link>{" "}
          das rubricas e distribua-a entre os estados antes.
        </p>
      )}
      {pools.isError && (
        <p role="alert" className="text-sm text-error-text" data-testid="remanejamento-erro-pools">
          Não foi possível carregar os pools. Recarregue a página.
        </p>
      )}

      <form
        className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-6"
        onSubmit={(e) => e.preventDefault()}
        data-testid="remanejamento-form"
      >
        <Select
          id="remanejamento-origem"
          label="Pool de origem"
          required
          options={opcoesOrigem}
          value={form.origem}
          onChange={(v) => atualizar("origem", v)}
          placeholder={pools.isPending ? "Carregando…" : "Selecione..."}
        />
        <Select
          id="remanejamento-destino"
          label="Pool de destino"
          required
          options={opcoesDestino}
          value={form.destino}
          onChange={(v) => atualizar("destino", v)}
          disabled={!origemPool}
          placeholder={origemPool ? "Selecione..." : "Escolha a origem primeiro"}
          helperText={
            origemPool
              ? opcoesDestino.length > 0
                ? `Só pools de ${origemPool.rubrica.nome}, a rubrica da origem.`
                : `Não há outro pool de ${origemPool.rubrica.nome} para receber o valor.`
              : undefined
          }
        />
        <Input
          id="remanejamento-valor"
          label="Valor (R$)"
          type="number"
          step="0.01"
          min="0.01"
          required
          value={form.valor}
          onChange={(e) => atualizar("valor", e.target.value)}
        />
        {simulando && (
          <p
            role="status"
            className="flex items-center gap-2 text-sm text-text-muted"
            data-testid="remanejamento-simulando"
          >
            <Spinner className="h-4 w-4 animate-spin" />
            Simulando…
          </p>
        )}
      </form>

      {simulacao && (
        <section
          aria-labelledby="simulacao-titulo"
          className="flex flex-col gap-3"
          data-testid="remanejamento-simulacao"
        >
          <h2 id="simulacao-titulo" className="text-base font-semibold text-text">
            Impacto da simulação
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <CartaoImpacto
              titulo="Origem"
              impacto={simulacao.origem}
              testId="impacto-origem"
            />
            <CartaoImpacto
              titulo="Destino"
              impacto={simulacao.destino}
              testId="impacto-destino"
            />
          </div>
          <Textarea
            id="remanejamento-justificativa"
            label="Justificativa"
            required
            rows={3}
            value={form.justificativa}
            onChange={(e) => atualizar("justificativa", e.target.value)}
            helperText="Fica registrada no lançamento do remanejamento."
          />
          <div className="flex items-center gap-2">
            <Button
              type="button"
              onClick={() => void onConfirmar()}
              disabled={!podeConfirmar}
              loading={confirmando}
              leftIcon={<CheckCircle2 className="h-4 w-4" />}
              data-testid="remanejamento-confirmar"
            >
              Confirmar remanejamento
            </Button>
            <span className="text-xs text-text-muted">
              Mudar origem, destino ou valor refaz a simulação.
            </span>
          </div>
        </section>
      )}

      {erro && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
          data-testid="remanejamento-erro"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {erro}
        </p>
      )}
    </div>
  );
}

/**
 * Tela de novo remanejamento entre pools (#402, AJ-FE-06). UGP/Super Admin
 * veem o impacto simulado e confirmam com o mesmo payload e a justificativa.
 */
export default function NovoRemanejamentoPage() {
  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">Novo remanejamento</span>
      </PageHeader>
      <NovoRemanejamentoView />
    </>
  );
}
