import { Wallet } from "lucide-react";
import { ModulePlaceholder } from "@/app/components/layout/ModulePlaceholder";

export default function SGFPage() {
  return (
    <ModulePlaceholder
      shortName="SGF"
      fullName="Sistema de Gestão de Formulários"
      Icon={Wallet}
      description="Catálogo de formulários do programa, com versões, regras de preenchimento e exportações para coleta em campo."
      features={[
        "Editor visual de formulários com perguntas e validações",
        "Versionamento e histórico de alterações por instrumento",
        "Publicação para uso pelo módulo SCA em campo",
        "Exportação consolidada das respostas recebidas",
      ]}
    />
  );
}
