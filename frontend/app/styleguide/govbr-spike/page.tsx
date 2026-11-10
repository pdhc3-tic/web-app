"use client";

import { notFound } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ChevronLeftIcon } from "@/app/components/icons";
import "./govbr-spike.css";

/**
 * Spike da ADR 001 (Issue #397): GOV.BR DS e Tailwind prefixado (`tw-*`)
 * convivendo numa rota isolada, sem tocar `globals.css`, `postcss.config.mjs`
 * nem as demais telas.
 *
 * O CSS do GOV.BR DS é carregado via `<link>` montado no efeito, para que o
 * `href` só entre na página quando o spike é aberto. Ao desmontar, o `<link>`
 * sai — nada do estilo vaza para `/dashboard`, `/sgp/*`, `/sgd/*`.
 *
 * As utilidades de layout nos blocos demonstrativos já usam o prefixo `tw-`
 * (`tw-grid`, `tw-gap-4`, `tw-p-6`, `tw-flex`, `tw-flex-col`) via
 * `govbr-spike.css`, validando a sintaxe e a divisão de camadas da ADR 001.
 *
 * Dev only: em produção, a rota responde 404 (mesmo padrão do `/styleguide`).
 */

const GOVBR_CSS = "https://cdn.jsdelivr.net/npm/@govbr-ds/core@4.3.0/dist/core.min.css";

export default function GovbrSpikePage() {
  if (process.env.NODE_ENV === "production") {
    notFound();
  }

  const [erroCss, setErroCss] = useState<string | null>(null);

  useEffect(() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = GOVBR_CSS;
    link.onerror = () => setErroCss("Falha ao carregar o CSS do GOV.BR DS.");
    document.head.appendChild(link);
    return () => {
      document.head.removeChild(link);
    };
  }, []);

  return (
    <div className="min-h-screen bg-bg p-6">
      <div className="mx-auto max-w-4xl flex flex-col gap-6">
        <header className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-text">Spike · GOV.BR DS + Tailwind</h1>
            <p className="mt-1 text-sm text-text-muted">
              Demonstra convivência dos dois sistemas na mesma página, sem tocar o resto da
              aplicação. Dev only · NODE_ENV = {process.env.NODE_ENV}.
            </p>
          </div>
          <Link
            href="/styleguide"
            className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            <ChevronLeftIcon /> Voltar ao styleguide
          </Link>
        </header>

        {erroCss && (
          <p
            role="alert"
            data-testid="govbr-spike-erro-css"
            className="rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
          >
            {erroCss} Rode offline? O spike precisa de rede para o CDN do GOV.BR DS.
          </p>
        )}

        {/* ── Bloco GOV.BR DS ──────────────────────────────────────────── */}
        <section
          aria-labelledby="govbr-titulo"
          data-testid="govbr-spike-bloco-govbr"
          className="rounded-lg border border-border bg-surface p-6"
        >
          <h2 id="govbr-titulo" className="text-base font-semibold text-text">
            Componentes do GOV.BR DS
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            As classes <code className="rounded bg-surface-muted px-1 py-0.5">br-*</code> vêm
            do CSS do GOV.BR DS carregado no efeito acima. Sem tocar <code>globals.css</code>.
          </p>

          <div className="mt-4 flex flex-col gap-3">
            <label className="br-input">
              <span>Nome completo</span>
              <input type="text" placeholder="Digite seu nome" data-testid="govbr-input-nome" />
            </label>

            <div className="flex gap-2">
              <button
                type="button"
                className="br-button primary"
                data-testid="govbr-botao-primario"
              >
                Enviar
              </button>
              <button
                type="button"
                className="br-button secondary"
                data-testid="govbr-botao-secundario"
              >
                Cancelar
              </button>
            </div>

            <div
              className="br-message warning"
              role="status"
              data-testid="govbr-mensagem"
            >
              <div className="icon">
                <i className="fas fa-exclamation-triangle" aria-hidden="true" />
              </div>
              <div className="content">
                <span className="message-title">Atenção</span>
                <span className="message-body">
                  Preencha os dados antes de enviar. Esta é uma mensagem do GOV.BR DS.
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* ── Bloco Tailwind (layout) ──────────────────────────────────── */}
        <section
          aria-labelledby="tw-titulo"
          data-testid="govbr-spike-bloco-tailwind"
          className="rounded-lg border border-border bg-surface tw-p-6"
        >
          <h2 id="tw-titulo" className="text-base font-semibold text-text">
            Layout com Tailwind prefixado (<code>tw-*</code>)
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            As classes do Tailwind seguem servindo o <strong>layout</strong> com prefixo{" "}
            <code>tw-</code> (<code>tw-grid</code>, <code>tw-gap-4</code>, <code>tw-p-6</code>):
            grid, gap, padding e posicionamento restritos à estrutura.
          </p>

          <div
            data-testid="govbr-spike-grid-tw"
            className="tw-mt-4 tw-grid tw-grid-cols-1 tw-gap-4 sm:tw-grid-cols-3"
          >
            {["Território", "Meta", "Rubrica"].map((rotulo) => (
              <div
                key={rotulo}
                className="tw-flex tw-flex-col tw-gap-1 rounded-md border border-border bg-surface-muted/50 tw-p-3"
                data-testid={`govbr-spike-card-${rotulo.toLowerCase()}`}
              >
                <span className="text-xs text-text-muted">{rotulo}</span>
                <span className="text-sm font-medium text-text">Valor do {rotulo.toLowerCase()}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── Convivência lado a lado ─────────────────────────────────── */}
        <section
          aria-labelledby="junto-titulo"
          data-testid="govbr-spike-conviv"
          className="rounded-lg border border-border bg-surface tw-p-6"
        >
          <h2 id="junto-titulo" className="text-base font-semibold text-text">
            Os dois juntos
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            O botão do GOV.BR DS (<code>br-button</code>) dentro de uma grade Tailwind prefixada (
            <code>tw-grid tw-gap-4 tw-p-6</code>): componente de um lado, layout do outro, sem
            brigar.
          </p>

          <div className="tw-mt-4 tw-grid tw-grid-cols-1 tw-gap-4 sm:tw-grid-cols-2">
            <div className="tw-flex tw-flex-col tw-gap-2">
              <span className="text-xs text-text-muted">Primária</span>
              <button type="button" className="br-button primary block">
                Autorizar
              </button>
            </div>
            <div className="tw-flex tw-flex-col tw-gap-2">
              <span className="text-xs text-text-muted">Secundária</span>
              <button type="button" className="br-button secondary block">
                Devolver
              </button>
            </div>
          </div>
        </section>

        <footer className="rounded-md border border-dashed border-border bg-surface-muted/30 px-4 py-3 text-xs text-text-muted">
          <p>
            Esta página <strong>não</strong> altera <code>globals.css</code>,
            <code> postcss.config.mjs</code> nem nenhum componente existente. É o primeiro
            passo do plano documentado na ADR 001 (
            <code>frontend/docs/adr-001-govbr-ds-tailwind.md</code>). O próximo PR ativa o
            prefixo <code>tw-</code> no Tailwind global e roda o codemod no projeto inteiro.
          </p>
        </footer>
      </div>
    </div>
  );
}
