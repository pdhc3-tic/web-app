"use client";

import Link from "next/link";
import { List, Map } from "lucide-react";
import { useSearchParams } from "next/navigation";

type Props = {
  active: "lista" | "mapa";
};

export function ViewToggle({ active }: Props) {
  const params = useSearchParams();
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  const listaHref = `/sgp/upfs/${suffix}`;
  const mapaHref = `/sgp/upfs/mapa/${suffix}`;

  return (
    <div
      role="group"
      aria-label="Alternar visualização"
      className="inline-flex overflow-hidden rounded-md border border-border bg-surface"
    >
      <Segment href={listaHref} active={active === "lista"} label="Lista" icon={<List className="h-4 w-4" />} />
      <Segment href={mapaHref} active={active === "mapa"} label="Mapa" icon={<Map className="h-4 w-4" />} />
    </div>
  );
}

function Segment({
  href,
  active,
  label,
  icon,
}: {
  href: string;
  active: boolean;
  label: string;
  icon: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition ${
        active
          ? "bg-primary text-white"
          : "text-text-muted hover:bg-surface-muted hover:text-text"
      }`}
    >
      {icon}
      {label}
    </Link>
  );
}
