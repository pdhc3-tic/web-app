"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { AlertTriangle, ArrowRight, CheckCircle2, GitCompareArrows } from "lucide-react";
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
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  fetchPainelOrcamento,
  nomeDoPool,
  type PoolOrcamentoApi,
} from "@/app/lib/orcamento";
import {
  confirmarRemanejamento,
  mensagemDeErro,
  simularRemanejamento,
  type ImpactoNoPool,
  type RemanejamentoPayload,
  type SimulacaoRemanejamento,
} from "@/app/lib/remanejamentoSgp";

type Form = {
  origem: string;
  destino: string;
  valor: string;
  justificativa: string;
};

const FORM_VAZIO: Form = { origem: "", destino: "", valor: "", justificativa: "" };

function payloadDoForm(form: Form): RemanejamentoPayload | null {
  const origem_allocation = Number(form.origem);
  const destino_allocation = Number(form.destino);
  if (
    !origem_allocation ||
    !destino_allocation ||
    origem_allocation === destino_allocation ||
    !form.valor ||
    !form.justificativa.trim()
  ) {
    return null;
  }
  return {
    origem_allocation,
    destino_allocation,
    valor: form.valor,
    justificativa: form.justificativa.trim(),
  };
}

function opcoesDePool(pools: PoolOrcamentoApi[]): SelectOption[] {
  return pools.map((p) => ({
    value: String(p.id),
    label: `${nomeDoPool(p)} · ${p.rubrica.nome} · disponível ${formatCurrencyBRL(p.saldo_disponivel)}`,
  }));
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

  const [form, setForm] = useState<Form>(FORM_VAZIO);
  const [simulacao, setSimulacao] = useState<SimulacaoRemanejamento | null>(null);
  const [payloadSimulado, setPayloadSimulado] = useState<RemanejamentoPayload | null>(null);
  const [simulando, setSimulando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const pools = useQuery({
    queryKey: ["sgp", "orcamento", "painel", "remanejamento"],
    queryFn: ({ signal }) => fetchPainelOrcamento({}, signal),
    staleTime: 30_000,
    enabled: status === "authenticated" && canRemanejarOrcamento(session?.user),
  });

  const opcoes = useMemo(() => opcoesDePool(pools.data ?? []), [pools.data]);
  const payloadAtual = payloadDoForm(form);
  const podeSimular = payloadAtual !== null && !simulando;
  const podeConfirmar =
    simulacao !== null &&
    payloadSimulado !== null &&
    payloadAtual !== null &&
    JSON.stringify(payloadAtual) === JSON.stringify(payloadSimulado) &&
    !confirmando;

  function atualizar<K extends keyof Form>(campo: K, valor: Form[K]) {
    setForm((prev) => ({ ...prev, [campo]: valor }));
    // Qualquer mudança invalida a simulação anterior.
    if (simulacao) {
      setSimulacao(null);
      setPayloadSimulado(null);
    }
    setErro(null);
  }

  async function onSimular() {
    if (!payloadAtual) return;
    setSimulando(true);
    setErro(null);
    try {
      const resultado = await simularRemanejamento(payloadAtual);
      setSimulacao(resultado);
      setPayloadSimulado(payloadAtual);
    } catch (e) {
      setErro(mensagemDeErro(e));
      setSimulacao(null);
      setPayloadSimulado(null);
    } finally {
      setSimulando(false);
    }
  }

  async function onConfirmar() {
    if (!payloadSimulado) return;
    setConfirmando(true);
    setErro(null);
    try {
      await confirmarRemanejamento(payloadSimulado);
      showToast("Remanejamento confirmado.", "success");
      router.push("/sgp/orcamento");
    } catch (e) {
      setErro(mensagemDeErro(e));
      // INSUFFICIENT_BALANCE: invalida a simulação para forçar nova rodada.
      setSimulacao(null);
      setPayloadSimulado(null);
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
          { label: "Novo remanejamento" },
        ]}
      />
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-text">Novo remanejamento</h1>
        <p className="mt-1 text-sm text-text-muted">
          Exceção à distribuição hierárquica: a UGP move saldo entre dois pools. A simulação
          mostra o antes e depois com a mudança de faixa; a confirmação relê o saldo no
          servidor.
        </p>
      </header>

      <form
        className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-6"
        onSubmit={(e) => {
          e.preventDefault();
          void onSimular();
        }}
        data-testid="remanejamento-form"
      >
        <Select
          id="remanejamento-origem"
          label="Pool de origem"
          required
          options={opcoes}
          value={form.origem}
          onChange={(v) => atualizar("origem", v)}
          placeholder={pools.isPending ? "Carregando…" : "Selecione..."}
        />
        <Select
          id="remanejamento-destino"
          label="Pool de destino"
          required
          options={opcoes}
          value={form.destino}
          onChange={(v) => atualizar("destino", v)}
          placeholder={pools.isPending ? "Carregando…" : "Selecione..."}
        />
        {form.origem && form.origem === form.destino && (
          <p role="alert" className="text-sm text-error-text" data-testid="remanejamento-erro-mesmo">
            Origem e destino precisam ser pools diferentes.
          </p>
        )}
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
        <Textarea
          id="remanejamento-justificativa"
          label="Justificativa"
          required
          rows={3}
          value={form.justificativa}
          onChange={(e) => atualizar("justificativa", e.target.value)}
        />
        <div className="flex gap-2">
          <Button
            type="submit"
            variant="secondary"
            disabled={!podeSimular}
            loading={simulando}
            leftIcon={<GitCompareArrows className="h-4 w-4" />}
            data-testid="remanejamento-simular"
          >
            Simular
          </Button>
        </div>
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
            {!podeConfirmar && !confirmando && (
              <span className="text-xs text-text-muted">
                Qualquer alteração no formulário cancela a simulação.
              </span>
            )}
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
 * simulam o impacto antes e confirmam usando o mesmo payload.
 */
export default function NovoRemanejamentoPage() {
  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">SGP</span>
      </PageHeader>
      <NovoRemanejamentoView />
    </>
  );
}
