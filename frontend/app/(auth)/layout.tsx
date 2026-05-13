import type { ReactNode } from "react";

const PILARES = [
  "Territórios",
  "Famílias",
  "Cadeias produtivas",
  "Eventos e atividades",
];

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] bg-background">
      <aside className="hidden lg:flex flex-col justify-between bg-primary text-white px-12 py-10 relative overflow-hidden">
        <div
          aria-hidden="true"
          className="absolute -top-32 -right-32 h-96 w-96 rounded-full bg-white/5 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="absolute -bottom-40 -left-20 h-80 w-80 rounded-full bg-white/5 blur-3xl"
        />

        <header className="relative flex items-center gap-2">
          <svg
            viewBox="0 0 24 24"
            className="h-7 w-7"
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
          <span className="text-xl font-semibold tracking-tight">
            PDHC <span className="font-light italic lowercase opacity-80">iii</span>
          </span>
        </header>

        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold leading-tight text-balance">
            Plataforma de Desenvolvimento das Cadeias Produtivas
          </h2>
          <p className="mt-3 text-base text-white/75 leading-relaxed">
            Da agricultura familiar do semiárido brasileiro.
          </p>
        </div>

        <ul className="relative space-y-2 text-sm text-white/70">
          {PILARES.map((p) => (
            <li key={p} className="flex items-center gap-2">
              <span aria-hidden="true" className="h-1 w-1 rounded-full bg-white/60" />
              {p}
            </li>
          ))}
        </ul>
      </aside>

      <main className="flex items-center justify-center px-4 py-10 lg:px-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center justify-center gap-2 mb-8 text-primary">
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
              PDHC <span className="font-light italic lowercase opacity-80">iii</span>
            </span>
          </div>

          <div className="bg-surface rounded-lg border border-border shadow-sm p-8">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
