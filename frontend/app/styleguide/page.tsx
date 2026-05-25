import { notFound } from "next/navigation";
import Link from "next/link";

if (process.env.NODE_ENV === "production") {
  notFound();
}

// ─── dados dos tokens ────────────────────────────────────────────────────────

const PALETTE_MAIN = [
  { cls: "bg-primary",          label: "primary",           hex: "#1B5E3B", light: false },
  { cls: "bg-secondary",        label: "secondary",         hex: "#2E7D52", light: false },
  { cls: "bg-accent-sage",      label: "accent-sage",       hex: "#4A7C59", light: false },
  { cls: "bg-accent-terracota", label: "accent-terracota",  hex: "#B05A2F", light: false },
  { cls: "bg-accent-ocre",      label: "accent-ocre",       hex: "#C9973A", light: true  },
];

const PALETTE_SURFACE = [
  { cls: "bg-bg",           label: "bg",           hex: "#F7F7F5" },
  { cls: "bg-surface",      label: "surface",      hex: "#FFFFFF"  },
  { cls: "bg-surface-muted",label: "surface-muted",hex: "#F1EFE8" },
  { cls: "bg-surface-warm", label: "surface-warm", hex: "#F5EFE0" },
  { cls: "bg-border",       label: "border",       hex: "#D3D1C7" },
  { cls: "bg-text",         label: "text",         hex: "#3D3D3A" },
  { cls: "bg-text-muted",   label: "text-muted",   hex: "#6B6B68" },
];

const SEMANTIC = [
  {
    bg: "bg-success-bg", text: "text-success-text", label: "Success",
    vars: "--color-success-bg / --color-success-text",
    sample: "Operação realizada com sucesso.",
  },
  {
    bg: "bg-warning-bg", text: "text-warning-text", label: "Warning",
    vars: "--color-warning-bg / --color-warning-text",
    sample: "Atenção: verifique os dados antes de continuar.",
  },
  {
    bg: "bg-error-bg", text: "text-error-text", label: "Error",
    vars: "--color-error-bg / --color-error-text",
    sample: "Erro ao processar a solicitação.",
  },
  {
    bg: "bg-info-bg", text: "text-info-text", label: "Info",
    vars: "--color-info-bg / --color-info-text",
    sample: "Esta ação não pode ser desfeita.",
  },
  {
    bg: "bg-neutral-bg", text: "text-neutral-text", label: "Neutral",
    vars: "--color-neutral-bg / --color-neutral-text",
    sample: "Status desconhecido ou não aplicável.",
  },
];

const RADII = [
  { cls: "rounded-sm",   label: "--radius-sm",   value: "4px"    },
  { cls: "rounded-md",   label: "--radius-md",   value: "6px"    },
  { cls: "rounded-lg",   label: "--radius-lg",   value: "8px"    },
  { cls: "rounded-full", label: "--radius-full", value: "9999px" },
];

const SHADOWS = [
  { cls: "shadow-sm", label: "--shadow-sm" },
  { cls: "shadow-md", label: "--shadow-md" },
];

const SPACING = [
  { cssVar: "--space-1", label: "–space-1", value: "4px"  },
  { cssVar: "--space-2", label: "–space-2", value: "8px"  },
  { cssVar: "--space-3", label: "–space-3", value: "12px" },
  { cssVar: "--space-4", label: "–space-4", value: "16px" },
  { cssVar: "--space-5", label: "–space-5", value: "20px" },
  { cssVar: "--space-6", label: "–space-6", value: "24px" },
  { cssVar: "--space-7", label: "–space-7", value: "28px" },
  { cssVar: "--space-8", label: "–space-8", value: "32px" },
];

// ─── helpers ─────────────────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-lg font-semibold text-text border-b border-border pb-2 mb-5">
      {children}
    </h2>
  );
}

function TokenLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-mono text-text-muted leading-tight">{children}</p>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function StyleguidePage() {
  return (
    <div className="min-h-screen bg-bg">
      <div className="max-w-5xl mx-auto px-6 py-10 space-y-14">

        {/* header */}
        <header>
          <div className="flex items-center justify-between mb-3">
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-warning-bg text-warning-text text-[10px] font-medium uppercase tracking-wide border border-border">
              Dev only · NODE_ENV = {process.env.NODE_ENV}
            </span>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-border bg-surface text-sm font-medium text-text hover:bg-surface-muted transition-colors"
            >
              <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.75} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 12L6 8l4-4" />
              </svg>
              Dashboard
            </Link>
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-text">
            Guia de Estilo · PDHC III
          </h1>
          <p className="mt-2 text-sm text-text-muted">
            Design tokens — paleta, tipografia, espaçamento, raios e sombras.<br />
            Esta página retorna 404 em produção.
          </p>
        </header>

        {/* ── 1. Paleta principal ── */}
        <section>
          <SectionTitle>1 · Paleta Principal</SectionTitle>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {PALETTE_MAIN.map((c) => (
              <div key={c.label} className={`${c.cls} rounded-lg p-4 h-28 flex flex-col justify-end`}>
                <TokenLabel>
                  <span className={c.light ? "text-black/60" : "text-white/70"}>
                    --color-{c.label}
                  </span>
                </TokenLabel>
                <p className={`text-xs font-mono font-medium ${c.light ? "text-black/80" : "text-white/90"}`}>
                  {c.hex}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ── 2. Superfícies & Neutros ── */}
        <section>
          <SectionTitle>2 · Superfícies & Neutros</SectionTitle>
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {PALETTE_SURFACE.map((c) => (
              <div key={c.label} className={`${c.cls} rounded-lg p-3 h-24 flex flex-col justify-end border border-border`}>
                <TokenLabel>--color-{c.label}</TokenLabel>
                <TokenLabel>{c.hex}</TokenLabel>
              </div>
            ))}
          </div>
        </section>

        {/* ── 3. Cores Semânticas ── */}
        <section>
          <SectionTitle>3 · Cores Semânticas</SectionTitle>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {SEMANTIC.map((s) => (
              <div key={s.label} className={`${s.bg} rounded-lg p-4 border border-border`}>
                <p className={`text-xs font-semibold uppercase tracking-wide ${s.text} mb-1.5`}>
                  {s.label}
                </p>
                <p className={`text-sm ${s.text}`}>{s.sample}</p>
                <p className="text-[10px] font-mono text-text-muted mt-2 opacity-70">{s.vars}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── 4. Tipografia ── */}
        <section>
          <SectionTitle>4 · Tipografia</SectionTitle>
          <div className="bg-surface rounded-lg border border-border divide-y divide-border">

            <div className="px-8 py-6">
              <TokenLabel>display — 48px · font-bold · tracking-tight · var(--font-sans)</TokenLabel>
              <p className="mt-2 text-5xl font-bold tracking-tight text-text leading-none">
                Ecossistema PDHC
              </p>
            </div>

            <div className="px-8 py-6">
              <TokenLabel>H1 — 36px · font-semibold</TokenLabel>
              <h1 className="mt-2 text-4xl font-semibold text-text">
                Desenvolvimento das Cadeias Produtivas
              </h1>
            </div>

            <div className="px-8 py-6">
              <TokenLabel>H2 — 28px · font-semibold</TokenLabel>
              <h2 className="mt-2 text-3xl font-semibold text-text">
                Famílias do Semiárido Brasileiro
              </h2>
            </div>

            <div className="px-8 py-6">
              <TokenLabel>H3 — 20px · font-medium</TokenLabel>
              <h3 className="mt-2 text-xl font-medium text-text">
                Territórios, Municípios e Cadeias
              </h3>
            </div>

            <div className="px-8 py-6">
              <TokenLabel>Corpo — 14px · font-normal · leading-relaxed</TokenLabel>
              <p className="mt-2 text-sm text-text leading-relaxed max-w-2xl">
                A plataforma apoia o monitoramento e a gestão de iniciativas no semiárido
                brasileiro, conectando famílias, territórios e cadeias produtivas em um
                único ecossistema digital.
              </p>
            </div>

            <div className="px-8 py-6">
              <TokenLabel>Hint / Caption — 12px · text-muted</TokenLabel>
              <p className="mt-2 text-xs text-text-muted">
                Última atualização: 22/05/2026 às 14:30 · Fonte: sistema
              </p>
            </div>

            <div className="px-8 py-6">
              <TokenLabel>Badge — 10px · uppercase · tracking-wide · rounded-full</TokenLabel>
              <div className="mt-2 flex flex-wrap gap-2">
                {["Super Admin", "Gestor Territorial", "Técnico", "Visualizador"].map((role) => (
                  <span
                    key={role}
                    className="px-2 py-0.5 rounded-full bg-surface-muted border border-border text-[10px] font-medium uppercase tracking-wide text-text-muted"
                  >
                    {role}
                  </span>
                ))}
              </div>
            </div>

            <div className="px-8 py-6">
              <TokenLabel>Mono — var(--font-mono) · CPF · GPS · Códigos</TokenLabel>
              <p className="mt-2 font-mono text-sm text-text">
                CPF: 000.000.000-00 · GPS: -9.3950, -40.4972 · ID: #4f2c9a
              </p>
            </div>

          </div>
        </section>

        {/* ── 5. Border-radius ── */}
        <section>
          <SectionTitle>5 · Border-radius</SectionTitle>
          <div className="flex flex-wrap items-end gap-8">
            {RADII.map((r) => (
              <div key={r.label} className="flex flex-col items-center gap-2">
                <div className={`${r.cls} w-16 h-16 bg-primary`} />
                <TokenLabel>{r.label}</TokenLabel>
                <p className="text-xs text-text-muted">{r.value}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── 6. Sombras ── */}
        <section>
          <SectionTitle>6 · Sombras</SectionTitle>
          <div className="flex flex-wrap items-end gap-10">
            {SHADOWS.map((s) => (
              <div key={s.label} className="flex flex-col items-center gap-3">
                <div className={`${s.cls} w-36 h-20 bg-surface rounded-lg`} />
                <TokenLabel>{s.label}</TokenLabel>
              </div>
            ))}
          </div>
        </section>

        {/* ── 7. Espaçamento ── */}
        <section>
          <SectionTitle>7 · Escala de Espaçamento</SectionTitle>
          <div className="flex flex-wrap items-end gap-3">
            {SPACING.map((s) => (
              <div key={s.cssVar} className="flex flex-col items-center gap-1.5">
                <div
                  className="bg-primary rounded-sm"
                  style={{ width: `var(${s.cssVar})`, height: `var(${s.cssVar})` }}
                />
                <TokenLabel>{s.label}</TokenLabel>
                <p className="text-[10px] text-text-muted">{s.value}</p>
              </div>
            ))}
          </div>
        </section>

        <footer className="border-t border-border pt-6">
          <p className="text-xs font-mono text-text-muted">
            /styleguide · visível apenas quando NODE_ENV ≠ production · sem dados reais
          </p>
        </footer>

      </div>
    </div>
  );
}
