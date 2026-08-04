"use client";

import { KeyboardEvent, ReactNode, useRef } from "react";

export type TabItem = {
  id: string;
  label: string;
  content: ReactNode;
};

export type TabsProps = {
  items: TabItem[];
  /** Id da aba ativa (componente controlado). */
  value: string;
  onValueChange: (id: string) => void;
  /** Rótulo acessível da lista de abas. */
  "aria-label": string;
};

/**
 * Abas horizontais acessíveis (WAI-ARIA tabs pattern).
 * - role="tablist"/"tab"/"tabpanel", aria-selected, roving tabindex.
 * - Teclado: ←/→ navegam com ativação automática; Home/End vão para primeira/última;
 *   Enter/Espaço ativam a aba focada.
 */
export function Tabs({
  items,
  value,
  onValueChange,
  "aria-label": ariaLabel,
}: TabsProps) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const activeIndex = Math.max(
    0,
    items.findIndex((t) => t.id === value),
  );

  function activateByIndex(index: number) {
    const item = items[index];
    if (!item) return;
    onValueChange(item.id);
    tabRefs.current[index]?.focus();
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const last = items.length - 1;
    let next: number | null = null;

    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        next = activeIndex >= last ? 0 : activeIndex + 1;
        break;
      case "ArrowLeft":
      case "ArrowUp":
        next = activeIndex <= 0 ? last : activeIndex - 1;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = last;
        break;
      default:
        return;
    }

    e.preventDefault();
    activateByIndex(next);
  }

  const active = items[activeIndex];

  return (
    <div>
      <div className="overflow-x-auto border-b border-border">
        <div
          role="tablist"
          aria-label={ariaLabel}
          onKeyDown={onKeyDown}
          className="flex min-w-max"
        >
          {items.map((item, index) => {
            const selected = index === activeIndex;
            return (
              <button
                key={item.id}
                ref={(el) => {
                  tabRefs.current[index] = el;
                }}
                type="button"
                role="tab"
                id={`tab-${item.id}`}
                aria-selected={selected}
                aria-controls={`panel-${item.id}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => onValueChange(item.id)}
                className={`-mb-px whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition-colors duration-[120ms] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                  selected
                    ? "border-primary text-primary"
                    : "border-transparent text-text-muted hover:border-border hover:text-text"
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      {active && (
        <div
          role="tabpanel"
          id={`panel-${active.id}`}
          aria-labelledby={`tab-${active.id}`}
          tabIndex={0}
          className="pt-6 focus-visible:outline-none"
        >
          {active.content}
        </div>
      )}
    </div>
  );
}
