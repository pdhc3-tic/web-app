const bar = "animate-pulse rounded bg-surface-muted";

/** Placeholder de carregamento da tela de detalhe da UPF. */
export function UpfDetailSkeleton() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Breadcrumb */}
      <div className={`h-4 w-64 ${bar}`} />

      {/* Header */}
      <div className="flex items-center gap-4">
        <div className={`h-16 w-16 shrink-0 rounded-full ${bar}`} />
        <div className="flex-1 space-y-2">
          <div className={`h-6 w-56 ${bar}`} />
          <div className={`h-4 w-40 ${bar}`} />
          <div className="flex gap-2 pt-1">
            <div className={`h-5 w-24 ${bar}`} />
            <div className={`h-5 w-24 ${bar}`} />
          </div>
        </div>
        <div className={`h-9 w-24 ${bar}`} />
      </div>

      {/* Barra de abas */}
      <div className="flex gap-4 border-b border-border pb-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className={`h-4 w-20 ${bar}`} />
        ))}
      </div>

      {/* Conteúdo da aba */}
      <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="space-y-1.5">
            <div className={`h-3 w-24 ${bar}`} />
            <div className={`h-4 w-40 ${bar}`} />
          </div>
        ))}
      </div>
    </div>
  );
}
