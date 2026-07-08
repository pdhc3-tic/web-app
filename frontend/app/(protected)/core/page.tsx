import { Database } from "lucide-react";
import { ModulePlaceholder } from "@/app/components/layout/ModulePlaceholder";

export default function CorePage() {
  return (
    <ModulePlaceholder
      shortName="Core"
      fullName="Módulo Central"
      Icon={Database}
      description="Concentra dados base, usuários, perfis, territórios e configurações compartilhadas por todos os módulos do ecossistema PDHC III."
      features={[
        "Cadastro e gestão de usuários e perfis de acesso",
        "Territórios e municípios atendidos pelo programa",
        "Configurações gerais e parâmetros do sistema",
        "Auditoria centralizada das ações dos usuários",
      ]}
    />
  );
}
