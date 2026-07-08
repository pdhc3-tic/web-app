import { FileText } from "lucide-react";
import { ModulePlaceholder } from "@/app/components/layout/ModulePlaceholder";

export default function SGDPage() {
  return (
    <ModulePlaceholder
      shortName="SGD"
      fullName="Sistema de Gestão de Demandas"
      Icon={FileText}
      description="Acompanhamento de pedidos, ordens e demandas geradas pelas equipes em campo e pelas instâncias gestoras do PDHC III."
      features={[
        "Cadastro e rastreamento de demandas por território",
        "Workflow de aprovação por instância",
        "Notificações de prazo e status",
        "Integração com o SGE para conversão em atividades",
      ]}
    />
  );
}
