"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

type Theme = "system" | "light" | "dark";

const STORAGE_KEY = "theme";
const CYCLE: Theme[] = ["system", "light", "dark"];

function readSavedTheme(): Theme {
  if (typeof window === "undefined") return "system";
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return "system";
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
    localStorage.removeItem(STORAGE_KEY);
  } else {
    root.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }
}

const META: Record<Theme, { Icon: typeof Sun; label: string }> = {
  system: { Icon: Monitor, label: "Tema do sistema" },
  light: { Icon: Sun, label: "Tema claro" },
  dark: { Icon: Moon, label: "Tema escuro" },
};

type ThemeToggleProps = {
  collapsed: boolean;
};

export function ThemeToggle({ collapsed }: ThemeToggleProps) {
  const [theme, setTheme] = useState<Theme>("system");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(readSavedTheme());
  }, []);

  function cycle() {
    const next = CYCLE[(CYCLE.indexOf(theme) + 1) % CYCLE.length];
    setTheme(next);
    applyTheme(next);
  }

  const { Icon, label } = META[theme];

  const buttonClass = collapsed
    ? "p-2 rounded-lg text-text-muted hover:bg-surface-muted hover:text-text transition-colors"
    : "inline-flex items-center justify-center h-8 w-8 rounded-lg text-text-muted hover:bg-surface-muted hover:text-text transition-colors";

  return (
    <button
      type="button"
      onClick={cycle}
      title={label}
      aria-label={label}
      className={buttonClass}
    >
      <Icon className={collapsed ? "h-4 w-4" : "h-3.5 w-3.5"} />
    </button>
  );
}
