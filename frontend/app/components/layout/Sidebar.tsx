"use client";

import { KeyboardEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  Database,
  FileText,
  Heart,
  LayoutDashboard,
  LogOut,
  SlidersHorizontal,
  Smartphone,
  Users,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { BrandMark } from "@/app/components/icons";
import Spinner from "@/app/components/icons/Spinner";
import { logout } from "@/app/lib/api";
import { ThemeToggle } from "./ThemeToggle";

type ModuleItem = {
  href: string;
  label: string;
  Icon: LucideIcon;
  badge?: number;
};

const STORAGE_KEY = "sidebar.collapsed";

const DASHBOARD: ModuleItem = {
  href: "/dashboard",
  label: "Dashboard",
  Icon: LayoutDashboard,
};

// Badges mock: substituir por /api/v1/notifications/me/unread-count/ em sprint futura
const MODULES: ModuleItem[] = [
  { href: "/core", label: "Core", Icon: Database },
  { href: "/sgp", label: "SGP", Icon: Users, badge: 3 },
  { href: "/sgf", label: "SGF", Icon: Wallet },
  { href: "/sgd", label: "SGD", Icon: FileText, badge: 1 },
  { href: "/sgs", label: "SGS", Icon: Heart },
  { href: "/sge", label: "SGE", Icon: Calendar, badge: 2 },
  { href: "/sca", label: "SCA", Icon: Smartphone },
];

function getIniciais(nome: string): string {
  const partes = nome.split(" ").filter(Boolean);
  if (partes.length === 0) return "?";
  if (partes.length === 1) return partes[0][0]?.toUpperCase() ?? "?";
  return (
    (partes[0][0] ?? "") + (partes[partes.length - 1][0] ?? "")
  ).toUpperCase();
}

function isActive(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  if (pathname === href) return true;
  return pathname.startsWith(href + "/");
}

type SidebarItemProps = {
  item: ModuleItem;
  active: boolean;
  collapsed: boolean;
};

function SidebarItem({ item, active, collapsed }: SidebarItemProps) {
  const { Icon, label, href, badge } = item;
  const base =
    "group relative flex items-center gap-3 h-10 rounded-md text-sm border-l-[3px] transition-colors duration-150";
  const layout = collapsed ? "px-2 justify-center" : "pl-3 pr-3";
  const state = active
    ? "border-primary bg-success-bg text-success-text font-medium"
    : "border-transparent text-text-muted hover:bg-surface-muted hover:text-text";
  const badgeClass = collapsed
    ? "absolute top-0.5 right-0.5 min-w-[16px] h-[16px] px-1 rounded-full text-[10px] font-medium bg-primary text-surface flex items-center justify-center"
    : "ml-auto min-w-[20px] h-[20px] px-1.5 rounded-full text-[10px] font-medium bg-primary text-surface flex items-center justify-center";

  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      aria-current={active ? "page" : undefined}
      className={`${base} ${layout} ${state}`}
    >
      <Icon
        className="h-4.5 w-4.5 shrink-0 transition-transform group-hover:scale-105"
        strokeWidth={active ? 2 : 1.75}
      />
      {!collapsed && <span className="flex-1 truncate">{label}</span>}
      {badge && badge > 0 && <span className={badgeClass}>{badge}</span>}
    </Link>
  );
}

type UserMenuProps = {
  collapsed: boolean;
};

function UserMenu({ collapsed }: UserMenuProps) {
  const { data: session } = useSession();
  const [leaving, setLeaving] = useState(false);

  async function handleLogout() {
    setLeaving(true);
    await logout();
  }

  if (!session?.user) return null;

  const { nome_completo, foto_url, perfis } = session.user;
  const nome = nome_completo || "Usuário";
  const iniciais = getIniciais(nome);
  const perfilPrincipal =
    perfis && perfis.length > 0 ? perfis[0].nome : "Sem perfil";

  const avatar = foto_url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={foto_url}
      alt=""
      className="h-9 w-9 rounded-full object-cover ring-2 ring-surface shadow-md shrink-0"
    />
  ) : (
    <div
      aria-hidden="true"
      className="h-9 w-9 rounded-full bg-linear-to-br from-primary to-secondary text-surface text-xs font-medium flex items-center justify-center shadow-md shadow-primary/20 shrink-0"
    >
      {iniciais}
    </div>
  );

  if (collapsed) {
    return (
      <div className="px-2 py-3 flex flex-col items-center gap-2.5">
        <span title={`${nome} · ${perfilPrincipal}`}>{avatar}</span>
        <Link
          href="/preferencias"
          title="Preferências"
          className="p-2 rounded-lg text-text-muted hover:bg-surface-muted hover:text-text transition-colors"
        >
          <SlidersHorizontal className="h-4 w-4" />
        </Link>
        <button
          type="button"
          onClick={handleLogout}
          disabled={leaving}
          title="Sair"
          className="p-2 rounded-lg text-text-muted hover:bg-error-bg hover:text-error-text transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {leaving ? (
            <Spinner className="h-4 w-4 animate-spin" />
          ) : (
            <LogOut className="h-4 w-4" />
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="p-3 space-y-3">
      <div className="flex items-center gap-3 min-w-0 px-1">
        {avatar}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-text truncate leading-tight">
            {nome}
          </p>
          <p className="text-xs text-text-muted truncate mt-0.5">
            {perfilPrincipal}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <Link
          href="/preferencias"
          className="flex-1 inline-flex items-center justify-center gap-1.5 h-8 px-2 rounded-lg text-xs text-text-muted hover:bg-surface-muted hover:text-text transition-colors"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
          <span>Preferências</span>
        </Link>
        <button
          type="button"
          onClick={handleLogout}
          disabled={leaving}
          className="inline-flex items-center justify-center gap-1.5 h-8 px-2.5 rounded-lg text-xs text-text-muted hover:bg-error-bg hover:text-error-text transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {leaving ? (
            <Spinner className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <LogOut className="h-3.5 w-3.5" />
          )}
          <span>{leaving ? "Saindo" : "Sair"}</span>
        </button>
      </div>
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const listRef = useRef<HTMLUListElement | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY) === "true";
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCollapsed(saved);
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(collapsed));
    document.documentElement.style.setProperty(
      "--sidebar-width",
      collapsed ? "4rem" : "15rem",
    );
  }, [collapsed]);

  function onListKeyDown(e: KeyboardEvent<HTMLUListElement>) {
    if (!listRef.current) return;
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const links = Array.from(
      listRef.current.querySelectorAll<HTMLAnchorElement>("a"),
    );
    const currentIndex = links.findIndex((l) => l === document.activeElement);
    if (currentIndex === -1) return;
    e.preventDefault();
    const nextIndex =
      e.key === "ArrowDown"
        ? Math.min(currentIndex + 1, links.length - 1)
        : Math.max(currentIndex - 1, 0);
    links[nextIndex]?.focus();
  }

  return (
    <div className="flex flex-col h-full bg-surface">
      <div
        className={`h-14 flex items-center shrink-0 shadow-[0_1px_0_0_color-mix(in_srgb,var(--color-border)_60%,transparent)] ${
          collapsed ? "px-2 justify-center" : "px-4"
        }`}
      >
        {collapsed ? (
          <button
            type="button"
            onClick={() => setCollapsed(false)}
            title="Expandir sidebar"
            aria-label="Expandir sidebar"
            className="p-2 rounded-lg hover:bg-surface-muted/60 text-text-muted hover:text-text transition-colors"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        ) : (
          <>
            <BrandMark />
            <button
              type="button"
              onClick={() => setCollapsed(true)}
              title="Recolher sidebar"
              aria-label="Recolher sidebar"
              className="ml-auto p-1.5 rounded-lg hover:bg-surface-muted/60 text-text-muted hover:text-text transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      <ul
        ref={listRef}
        onKeyDown={onListKeyDown}
        className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5"
      >
        <li>
          <SidebarItem
            item={DASHBOARD}
            active={isActive(pathname, DASHBOARD.href)}
            collapsed={collapsed}
          />
        </li>
        {collapsed ? (
          <li aria-hidden="true" className="mx-3 my-3 h-px bg-border/40" />
        ) : (
          <li
            aria-hidden="true"
            className="px-3 pt-5 pb-1.5 text-micro font-medium uppercase tracking-[0.18em] text-text-muted/70"
          >
            Módulos
          </li>
        )}
        {MODULES.map((m) => (
          <li key={m.href}>
            <SidebarItem
              item={m}
              active={isActive(pathname, m.href)}
              collapsed={collapsed}
            />
          </li>
        ))}
      </ul>

      <div
        className={`shrink-0 ${
          collapsed
            ? "px-2 py-2 flex justify-center"
            : "px-3 py-2 flex justify-end"
        }`}
      >
        <ThemeToggle collapsed={collapsed} />
      </div>

      <UserMenu collapsed={collapsed} />
    </div>
  );
}
