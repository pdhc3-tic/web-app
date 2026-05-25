import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] bg-bg">
      <aside className="hidden lg:flex flex-col justify-between relative overflow-hidden px-14 py-12 text-white bg-[#0d2e1d]">
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(74,124,89,0.35),transparent_60%)]"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[radial-gradient(circle_at_80%_80%,rgba(27,94,59,0.45),transparent_55%)]"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-[0.025]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
            backgroundSize: "28px 28px",
          }}
        />

        <header className="relative flex items-center gap-2.5">
          <svg
            viewBox="0 0 24 24"
            className="h-7 w-7 text-white/90"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.75}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 3 L20 19 L4 19 Z"
            />
          </svg>
          <span className="text-lg font-semibold tracking-tight">
            PDHC{" "}
            <span className="font-light italic lowercase opacity-70">iii</span>
          </span>
        </header>

        <div className="relative max-w-md">
          <h2 className="text-5xl font-semibold leading-[1.05] tracking-tight">
            Cadeias produtivas
            <br />
            <span className="text-white/60">da agricultura familiar.</span>
          </h2>
          <p className="mt-5 text-sm text-white/55 leading-relaxed max-w-sm">
            Plataforma do Programa de Desenvolvimento Humano das Cadeias
            Produtivas no semiárido brasileiro.
          </p>
        </div>

        <p className="relative text-[11px] tracking-[0.2em] uppercase text-white/35 font-medium">
          Ecossistema PDHC III
        </p>
      </aside>

      <main className="flex items-center justify-center px-6 py-12 lg:px-16">
        <div className="w-full max-w-[420px]">
          <div className="lg:hidden flex items-center justify-center gap-2 mb-10 text-primary">
            <svg
              viewBox="0 0 24 24"
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.75}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 3 L20 19 L4 19 Z"
              />
            </svg>
            <span className="text-lg font-semibold tracking-tight">
              PDHC{" "}
              <span className="font-light italic lowercase opacity-70">
                iii
              </span>
            </span>
          </div>

          {children}
        </div>
      </main>
    </div>
  );
}
