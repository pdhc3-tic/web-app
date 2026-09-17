import { BadgeStatusIcon, type BadgeStatus } from "@/app/components/icons";

export type { BadgeStatus };

export type BadgeProps = {
  status: BadgeStatus;
  label?: string;
};

/**
 * Cor por status.
 *
 * Os oito estados de Atividade seguem `STATUS_COR_MAP`
 * (backend/apps/sgp/serializers.py), que é o mesmo mapa que pinta o calendário
 * e a exportação. A correspondência é matiz a matiz:
 *
 *   planejado    gray-500    → neutral       agendado      blue-500    → info
 *   em_andamento amber-500   → warning       concluido     emerald-500 → success
 *   sem_evidencia teal-500   → pendente      adiada        violet-500  → reagendado
 *   nao_realizada red-500    → error         cancelada     gray-400    → neutral
 *
 * `planejado` era azul e `adiada`/`sem-evidencia` eram os dois âmbar: a ficha
 * dizia uma cor e o calendário, outra, para o mesmo registro. Os dois cinzas
 * (planejado e cancelada) são o próprio mapa do domínio — o que os separa na
 * tela é o ícone e o risco do texto, não a matiz.
 *
 * Os quatro últimos não são status de Atividade: servem a listagens e badges de
 * procedência, e por isso continuam nos tokens genéricos.
 */
const statusClass: Record<BadgeStatus, string> = {
  planejado: "bg-neutral-bg text-neutral-text border-neutral-text",
  agendado: "bg-info-bg text-info-text border-info-text",
  "em-andamento": "bg-warning-bg text-warning-text border-warning-text",
  concluido: "bg-success-bg text-success-text border-success-text",
  // Concluída sem evidência é uma pendência, não um estado inerte. A borda
  // tracejada mantém a distinção de "concluido" cheio.
  "sem-evidencia":
    "bg-pendente-bg text-pendente-text border-pendente-text border-dashed",
  adiada:
    "bg-reagendado-bg text-reagendado-text border-reagendado-text border-dashed",
  "nao-realizada": "bg-error-bg text-error-text border-error-text",
  cancelada: "bg-neutral-bg text-neutral-text border-neutral-text line-through decoration-1",
  atrasada: "bg-error-bg text-error-text border-error-text border-dashed",
  ativo: "bg-success-bg text-success-text border-success-text",
  inativo: "bg-neutral-bg text-neutral-text border-neutral-text",
  info: "bg-info-bg text-info-text border-info-text",
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
  ativo: "Ativo",
  inativo: "Inativo",
  info: "Informação",
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
