import Link from "next/link";
import { BrandMark } from "@/app/components/icons";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
];

export function Sidebar() {
  return (
    <div className="flex flex-col h-full">
      <div className="h-14 px-4 flex items-center border-b border-border shrink-0">
        <BrandMark />
      </div>
      <ul className="flex-1 p-2 space-y-1">
        {NAV_ITEMS.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className="block px-3 py-2 rounded-md text-sm text-text hover:bg-surface-muted transition-colors"
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
      <div className="p-3 border-t border-border">
        <p className="text-micro font-mono text-text-muted text-center">
          Sidebar placeholder · FE-04
        </p>
      </div>
    </div>
  );
}
