import { PAGE_HEADER_SLOT_ID } from "./PageHeader";

export function Header() {
  return (
    <header className="sticky top-0 z-20 h-14 bg-surface flex items-center px-6 shadow-[0_1px_0_0_color-mix(in_srgb,var(--color-border)_60%,transparent)]">
      <div id={PAGE_HEADER_SLOT_ID} className="flex-1 min-w-0" />
    </header>
  );
}
