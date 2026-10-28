"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { fetchAtividadeCount } from "@/app/lib/atividades";
import { fetchPainel } from "@/app/lib/painel";
import { AlertCard, type CardState } from "./_components/AlertCard";

function getPrimeiroNome(nome: string): string {
  return nome.split(" ").filter(Boolean)[0] ?? "";
}

function getSaudacao(date: Date = new Date()): string {
  const h = date.getHours();
  if (h >= 5 && h < 12) return "Bom dia";
  if (h >= 12 && h < 18) return "Boa tarde";
  return "Boa noite";
}

export default function DashboardPage() {
  const { data: session, status } = useSession();

  const [semEvidencia, setSemEvidencia] = useState<CardState>({ phase: "loading" });
  const [atrasadas, setAtrasadas] = useState<CardState>({ phase: "loading" });
  const [acoesCriticas, setAcoesCriticas] = useState<CardState>({ phase: "loading" });

  // Depende de quem é o usuário, não do objeto da sessão: o next-auth entrega
  // um objeto novo a cada recarga da sessão (inclusive as disparadas por outra
  // aba), e refazer as buscas a cada recarga gerava um laço entre abas.
  const usuarioId = session?.user?.id;

  useEffect(() => {
    if (status !== "authenticated" || !usuarioId) return;

    const controller = new AbortController();

    // Sem territorio_id: o backend aplica RLS sobre todos os territórios do
    // usuário, evitando o bug de considerar apenas o primeiro território.
    fetchAtividadeCount(
      { status: "concluido_sem_evidencia" },
      controller.signal,
    )
      .then((c) => setSemEvidencia({ phase: "ok", count: c }))
      .catch(() => setSemEvidencia({ phase: "error" }));

    fetchAtividadeCount(
      { atrasada: true },
      controller.signal,
    )
      .then((c) => setAtrasadas({ phase: "ok", count: c }))
      .catch(() => setAtrasadas({ phase: "error" }));

    fetchPainel({}, controller.signal)
      .then((data) => {
        const total = data.metas.reduce((sum, m) => sum + m.resumo.vermelho, 0);
        setAcoesCriticas({ phase: "ok", count: total });
      })
      .catch(() => setAcoesCriticas({ phase: "error" }));

    return () => controller.abort();
  }, [usuarioId, status]);

  if (status === "loading") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  const nome = session!.user.nome_completo || "Usuário";
  const primeiroNome = getPrimeiroNome(nome) || "por aqui";

  return (
    <>
      <PageHeader>
        <h1 className="truncate text-base font-semibold text-text">Dashboard</h1>
      </PageHeader>

      <div className="mx-auto max-w-6xl space-y-6">
        <section className="relative overflow-hidden rounded-lg border border-border bg-primary p-6 text-surface sm:p-8">
          <div
            aria-hidden="true"
            className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-white/10 blur-3xl"
          />
          <div className="relative">
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-white/70">
              Painel inicial
            </p>
            <h2 className="mt-3 text-2xl font-semibold leading-tight sm:text-3xl">
              {getSaudacao()}, {primeiroNome}.
            </h2>
          </div>
        </section>

        <section aria-label="Alertas do SGP" className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <AlertCard
            title="Sem evidência"
            description="Atividades concluídas sem registro de evidência"
            state={semEvidencia}
            href="/sgp/atividades?status=concluido_sem_evidencia"
          />
          <AlertCard
            title="Atrasadas"
            description="Atividades com data de fim ultrapassada ainda abertas"
            state={atrasadas}
            href="/sgp/atividades?atrasada=true"
          />
          <AlertCard
            title="Ações críticas"
            description="Ações do Plano de Trabalho com execução abaixo do esperado"
            state={acoesCriticas}
            // `?criticas=1` liga o filtro dedicado do painel (semaforo vermelho).
            // Antes ia para `situacao=em_atraso`, que é outro critério — a
            // listagem podia trazer menos ou mais linhas que a contagem do card.
            href="/sgp/painel?criticas=1"
          />
        </section>
      </div>
    </>
  );
}
