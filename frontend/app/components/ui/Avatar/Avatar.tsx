type AvatarSize = "sm" | "md";

const sizeClass: Record<AvatarSize, string> = {
  sm: "h-8 w-8 text-2xs",
  md: "h-9 w-9 text-xs",
};

function getIniciais(nome: string): string {
  const partes = nome.split(" ").filter(Boolean);
  if (partes.length === 0) return "?";
  if (partes.length === 1) return partes[0][0]?.toUpperCase() ?? "?";
  return (
    (partes[0][0] ?? "") + (partes[partes.length - 1][0] ?? "")
  ).toUpperCase();
}

export type AvatarProps = {
  /** Nome completo — usado para derivar as iniciais e o alt. */
  name: string;
  /** URL da foto. Quando ausente, renderiza as iniciais. */
  src?: string | null;
  size?: AvatarSize;
  /** Classes extras (sombra, ring, etc.). */
  className?: string;
};

/** Avatar circular: foto quando disponível, senão iniciais sobre gradiente. */
export function Avatar({ name, src, size = "sm", className }: AvatarProps) {
  const base = `${sizeClass[size]} shrink-0 rounded-full flex items-center justify-center`;

  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={name}
        className={`${base} object-cover ring-2 ring-surface ${className ?? ""}`}
      />
    );
  }

  return (
    <div
      aria-hidden="true"
      className={`${base} bg-linear-to-br from-primary to-secondary text-surface font-medium ${className ?? ""}`}
    >
      {getIniciais(name)}
    </div>
  );
}
