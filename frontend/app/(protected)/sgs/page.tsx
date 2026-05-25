import { Heart } from "lucide-react";
import { ModulePlaceholder } from "@/app/components/layout/ModulePlaceholder";

export default function SGSPage() {
  return (
    <ModulePlaceholder
      shortName="SGS"
      fullName="Sistema de Gestão de Seleções"
      Icon={Heart}
      description="Processos seletivos de famílias, organizações e parceiros para participação nas frentes do programa."
      features={[
        "Editais e chamadas com critérios configuráveis",
        "Inscrições e análise documental com pareceres",
        "Classificação e resultado por etapa",
        "Recursos e comunicação com inscritos",
      ]}
    />
  );
}
