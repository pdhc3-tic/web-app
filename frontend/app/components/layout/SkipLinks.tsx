const linkClass =
  "sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-surface focus:rounded-md focus:shadow-md focus:text-sm focus:font-medium";

export function SkipLinks() {
  return (
    <>
      <a href="#main-content" className={linkClass}>
        Pular para o conteúdo principal
      </a>
      <a href="#main-nav" className={linkClass}>
        Pular para navegação
      </a>
    </>
  );
}
