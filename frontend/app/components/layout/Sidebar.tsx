import Link from "next/link";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
];

function BrandMark() {
  return (
    <div className="flex items-center gap-2 text-primary">
      <svg
        viewBox="0 0 24 24"
        className="h-6 w-6"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 3 L20 19 L4 19 Z"
        />
      </svg>
      <span className="text-base font-semibold tracking-tight">
        PDHC <span className="font-light italic lowercase opacity-80">iii</span>
      </span>
    </div>
  );
}

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
