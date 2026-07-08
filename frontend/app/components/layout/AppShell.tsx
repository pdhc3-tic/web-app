import { ReactNode } from "react";
import { Header } from "./Header";
import { SkipLinks } from "./SkipLinks";

type AppShellProps = {
  sidebar: ReactNode;
  children: ReactNode;
};

export function AppShell({ sidebar, children }: AppShellProps) {
  return (
    <div className="min-h-screen">
      <SkipLinks />

      <aside className="hidden md:flex fixed top-0 left-0 h-screen w-[var(--sidebar-width)] flex-col z-10 transition-[width] duration-200 shadow-[1px_0_0_0_color-mix(in_srgb,var(--color-border)_50%,transparent)]">
        <nav
          id="main-nav"
          aria-label="Navegação principal"
          className="flex flex-col h-full"
        >
          {sidebar}
        </nav>
      </aside>

      <div className="md:ml-[var(--sidebar-width)] flex flex-col min-h-screen transition-[margin-left] duration-200">
        <Header />
        <main id="main-content" className="flex-1 p-6 pb-20 md:pb-6">
          {children}
        </main>
        <footer className="px-6 py-4">
          <p className="text-micro font-mono text-text-muted/60 text-center">
            Ecossistema PDHC III
          </p>
        </footer>
      </div>

      <nav
        aria-label="Navegação principal (móvel)"
        className="md:hidden fixed bottom-0 left-0 right-0 h-14 bg-surface/80 backdrop-blur-md flex items-center justify-center z-10 shadow-[0_-1px_0_0_color-mix(in_srgb,var(--color-border)_60%,transparent)]"
      >
        <p className="text-micro font-mono text-text-muted">
          Bottom nav placeholder · sprint do SCA
        </p>
      </nav>
    </div>
  );
}
