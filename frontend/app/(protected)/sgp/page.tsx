import { Users } from "lucide-react";
import { ModulePlaceholder } from "@/app/components/layout/ModulePlaceholder";

export default function SGPPage() {
  return (
    <ModulePlaceholder
      shortName="SGP"
      fullName="Sistema de Gestão de Projetos"
      Icon={Users}
      description="Planejamento, execução e acompanhamento de projetos territoriais articulados com a agricultura familiar."
      features={[
        "Cadastro de projetos com vínculo a territórios e cadeias produtivas",
        "Cronograma físico e financeiro por etapa",
        "Acompanhamento de beneficiários e famílias atendidas",
        "Indicadores e relatórios consolidados de execução",
      ]}
    />
  );
}
