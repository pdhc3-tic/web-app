import { MapPinOff } from "lucide-react";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Button } from "@/app/components/ui/Button/Button";

/**
 * 404 customizada da rota de detalhe da UFPA. É acionada via notFound() e cobre
 * tanto "UFPA inexistente" quanto "fora do escopo/território" — o backend retorna
 * 404 nos dois casos, sem distinção.
 */
export default function UfpaNotFound() {
  return (
    <div className="mx-auto max-w-5xl pt-8">
      <EmptyState
        icon={<MapPinOff className="h-7 w-7" />}
        title="UFPA não encontrada ou fora do seu escopo"
        description="A unidade que você tentou abrir não existe ou está fora do seu território de atuação."
        action={
          <Button as="a" href="/sgp/ufpas/" variant="secondary">
            Voltar para UFPAs
          </Button>
        }
      />
    </div>
  );
}
