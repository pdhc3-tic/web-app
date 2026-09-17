import Link from "next/link";
import type { LucideIcon } from "lucide-react";

/**
 * Card de submódulo das telas-índice de módulo (SGP, SCA). Nasceu no SGP e
 * subiu para cá quando ganhou o segundo consumidor — o comportamento é o mesmo
 * nas duas: `href` ausente marca o card como "Em breve", e `count` opcional
 * mostra o número do submódulo ativo.
 */
type SubmoduleCardProps = {
  title: string;
  description: string;
  Icon: LucideIcon;
  /** Presença define o card como ativo (navegável). Ausência => "Em breve". */
  href?: string;
  /** Contador do card ativo: número exibido, `null` = carregando/erro ("—"). Omitir = sem contador. */
  count?: number | null;
};

const CARD_BASE =
  "group relative flex flex-col gap-3 rounded-lg border border-border bg-surface p-5 transition-colors";

function CardBody({
  title,
  description,
  Icon,
  active,
  count,
}: {
  title: string;
  description: string;
  Icon: LucideIcon;
  active: boolean;
  count?: number | null;
}) {
  return (
    <>
      <div className="flex items-start justify-between gap-3">
        <span
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
            active
              ? "bg-secondary/10 text-secondary"
              : "bg-surface-muted text-text-muted"
          }`}
        >
          <Icon className="h-5 w-5" aria-hidden="true" strokeWidth={1.75} />
        </span>

        {active ? (
          count !== undefined && (
            <span className="text-2xl font-semibold text-text tabular-nums leading-none">
              {count === null ? "—" : count.toLocaleString("pt-BR")}
            </span>
          )
        ) : (
          <span className="inline-flex items-center rounded-full bg-neutral-bg px-2 py-0.5 text-2xs font-medium text-neutral-text">
            Em breve
          </span>
        )}
      </div>

      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-text">{title}</h2>
        <p className="mt-1 line-clamp-1 text-xs text-text-muted">{description}</p>
      </div>
    </>
  );
}

export function SubmoduleCard({
  title,
  description,
  Icon,
  href,
  count,
}: SubmoduleCardProps) {
  if (href) {
    return (
      <Link
        href={href}
        className={`${CARD_BASE} hover:border-primary/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary`}
      >
        <CardBody
          title={title}
          description={description}
          Icon={Icon}
          active
          count={count}
        />
      </Link>
    );
  }

  return (
    <div
      aria-disabled="true"
      className={`${CARD_BASE} cursor-not-allowed opacity-60`}
    >
      <CardBody
        title={title}
        description={description}
        Icon={Icon}
        active={false}
      />
    </div>
  );
}
