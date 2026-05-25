import { ReactNode } from "react";
import { Header } from "./Header";
import { SkipLinks } from "./SkipLinks";

type AppShellProps = {
  sidebar: ReactNode;
  children: ReactNode;
};

export function AppShell({ sidebar, children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-bg">
      <SkipLinks />

      <aside className="hidden md:flex fixed top-0 left-0 h-screen w-60 bg-surface border-r border-border flex-col z-10">
        <nav
          id="main-nav"
          aria-label="Navegação principal"
          className="flex flex-col h-full"
        >
          {sidebar}
        </nav>
      </aside>

      <div className="md:ml-60 flex flex-col min-h-screen">
        <Header />
        <main id="main-content" className="flex-1 p-6 pb-20 md:pb-6">
          {children}
        </main>
      </div>

      <nav
        aria-label="Navegação principal (móvel)"
        className="md:hidden fixed bottom-0 left-0 right-0 h-14 bg-surface border-t border-border flex items-center justify-center z-10"
      >
        <p className="text-micro font-mono text-text-muted">
          Bottom nav placeholder · sprint do SCA
        </p>
      </nav>
    </div>
  );
}
