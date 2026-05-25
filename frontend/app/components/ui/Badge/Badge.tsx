import { BadgeStatusIcon, type BadgeStatus } from "@/app/components/icons";

export type { BadgeStatus };

export type BadgeProps = {
  status: BadgeStatus;
  label?: string;
};

const statusClass: Record<BadgeStatus, string> = {
  planejado: "bg-info-bg text-info-text border-info-text",
  agendado: "bg-info-bg text-info-text border-info-text",
  "em-andamento": "bg-warning-bg text-warning-text border-warning-text",
  concluido: "bg-success-bg text-success-text border-success-text",
  "sem-evidencia": "bg-neutral-bg text-neutral-text border-border border-dashed",
  adiada: "bg-warning-bg text-warning-text border-warning-text border-dashed",
  "nao-realizada": "bg-error-bg text-error-text border-error-text",
  cancelada: "bg-neutral-bg text-neutral-text border-neutral-text line-through decoration-1",
  atrasada: "bg-error-bg text-error-text border-error-text border-dashed",
};

const defaultLabel: Record<BadgeStatus, string> = {
  planejado: "Planejado",
  agendado: "Agendado",
  "em-andamento": "Em andamento",
  concluido: "Concluído",
  "sem-evidencia": "Sem evidência",
  adiada: "Adiada",
  "nao-realizada": "Não realizada",
  cancelada: "Cancelada",
  atrasada: "Atrasada",
};

export function Badge({ status, label }: BadgeProps) {
  const text = label ?? defaultLabel[status];
  return (
    <span
      className={`inline-flex items-center gap-1 py-0.5 px-2 rounded-full border text-2xs font-medium leading-[1.4] whitespace-nowrap ${statusClass[status]}`}
    >
      <BadgeStatusIcon status={status} />
      {text}
    </span>
  );
}
