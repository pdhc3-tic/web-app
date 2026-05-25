import { Calendar } from "lucide-react";
import { ModulePlaceholder } from "@/app/components/layout/ModulePlaceholder";

export default function SGEPage() {
  return (
    <ModulePlaceholder
      shortName="SGE"
      fullName="Sistema de Gestão de Eventos"
      Icon={Calendar}
      description="Calendário, planejamento e registro de eventos, oficinas e atividades realizadas nos territórios."
      features={[
        "Agenda integrada com módulos SGP e SGD",
        "Inscrições e listas de presença por evento",
        "Registro fotográfico e materiais entregues",
        "Relatório de execução com indicadores de alcance",
      ]}
    />
  );
}
