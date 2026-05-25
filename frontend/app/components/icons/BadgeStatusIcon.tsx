import type { ReactNode } from "react";

export type BadgeStatus =
  | "planejado"
  | "agendado"
  | "em-andamento"
  | "concluido"
  | "sem-evidencia"
  | "adiada"
  | "nao-realizada"
  | "cancelada"
  | "atrasada";

type BadgeStatusIconProps = {
  status: BadgeStatus;
  className?: string;
};

export function BadgeStatusIcon({
  status,
  className = "w-3 h-3 shrink-0",
}: BadgeStatusIconProps): ReactNode {
  const common = {
    className,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.75,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  switch (status) {
    case "planejado":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M8 5v3l2 1.5" />
        </svg>
      );
    case "agendado":
      return (
        <svg {...common}>
          <rect x="2.5" y="3.5" width="11" height="10" rx="1.5" />
          <path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" />
        </svg>
      );
    case "em-andamento":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M6 5.5l4 2.5-4 2.5z" fill="currentColor" stroke="none" />
        </svg>
      );
    case "concluido":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M5 8l2 2 4-4" />
        </svg>
      );
    case "sem-evidencia":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M6.5 6.25a1.5 1.5 0 113 0c0 .8-.7 1.1-1.2 1.5-.3.2-.3.6-.3 1" />
          <circle cx="8" cy="11.25" r="0.6" fill="currentColor" stroke="none" />
        </svg>
      );
    case "adiada":
      return (
        <svg {...common}>
          <path d="M2.5 7.5a5.5 5.5 0 015.5-5.5h.5l-2 -2M13.5 8.5a5.5 5.5 0 01-5.5 5.5h-.5l2 2" />
        </svg>
      );
    case "nao-realizada":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" />
        </svg>
      );
    case "cancelada":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M4 4l8 8" />
        </svg>
      );
    case "atrasada":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M8 5v3.5M8 11.25v.25" />
        </svg>
      );
  }
}
