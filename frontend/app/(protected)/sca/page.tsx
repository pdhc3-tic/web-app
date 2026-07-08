import { Smartphone } from "lucide-react";
import { ModulePlaceholder } from "@/app/components/layout/ModulePlaceholder";

export default function SCAPage() {
  return (
    <ModulePlaceholder
      shortName="SCA"
      fullName="Sistema de Coleta em Campo"
      Icon={Smartphone}
      description="Aplicativo e ferramentas para coleta de dados em campo, com suporte a operação offline em áreas sem conectividade."
      features={[
        "Coleta offline com sincronização posterior",
        "Captura de fotos, GPS e assinaturas digitais",
        "Formulários publicados pelo SGF",
        "Validação local e envio em lote ao retornar à internet",
      ]}
    />
  );
}
