import { Fragment, type ReactNode } from "react";

export type DefinitionItem = {
  label: string;
  value: ReactNode;
};

export type DefinitionListProps = {
  items: DefinitionItem[];
  className?: string;
};

/** Considera vazio: null, undefined e string só com espaços. */
function isEmpty(value: ReactNode): boolean {
  return (
    value === null ||
    value === undefined ||
    (typeof value === "string" && value.trim() === "")
  );
}

/**
 * Lista de definições (<dl>): pares rótulo/valor em grid.
 * Valores ausentes são exibidos como em-dash "—".
 */
export function DefinitionList({ items, className }: DefinitionListProps) {
  return (
    <dl
      className={`grid grid-cols-[auto_1fr] items-baseline gap-x-6 gap-y-3 text-sm ${
        className ?? ""
      }`}
    >
      {items.map((item) => (
        <Fragment key={item.label}>
          <dt className="whitespace-nowrap text-text-muted">{item.label}</dt>
          <dd className="min-w-0 font-medium text-text">
            {isEmpty(item.value) ? (
              <span className="text-text-muted">—</span>
            ) : (
              item.value
            )}
          </dd>
        </Fragment>
      ))}
    </dl>
  );
}
