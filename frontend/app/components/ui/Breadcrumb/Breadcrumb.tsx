import { Fragment } from "react";
import Link from "next/link";

export type BreadcrumbItem = {
  label: string;
  /** Sem href = item atual (último), marcado com aria-current="page". */
  href?: string;
};

export type BreadcrumbProps = {
  items: BreadcrumbItem[];
};

/** Trilha de navegação: "Início › SGP › UPFs › …" com o último item como página atual. */
export function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-1.5 text-sm text-text-muted">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <Fragment key={`${item.label}-${index}`}>
              <li className="min-w-0">
                {item.href && !isLast ? (
                  <Link
                    href={item.href}
                    className="rounded transition-colors hover:text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  >
                    {item.label}
                  </Link>
                ) : (
                  <span
                    aria-current={isLast ? "page" : undefined}
                    className={
                      isLast ? "truncate font-medium text-text" : undefined
                    }
                  >
                    {item.label}
                  </span>
                )}
              </li>
              {!isLast && (
                <li aria-hidden="true" className="text-text-muted/60">
                  ›
                </li>
              )}
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
