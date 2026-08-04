import { MapPinOff } from "lucide-react";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Button } from "@/app/components/ui/Button/Button";

/**
 * 404 customizada da rota de detalhe da UPF. É acionada via notFound() e cobre
 * tanto "UPF inexistente" quanto "fora do escopo/território" — o backend retorna
 * 404 nos dois casos, sem distinção.
 */
export default function UpfNotFound() {
  return (
    <div className="mx-auto max-w-5xl pt-8">
      <EmptyState
        icon={<MapPinOff className="h-7 w-7" />}
        title="UPF não encontrada ou fora do seu escopo"
        description="A unidade que você tentou abrir não existe ou está fora do seu território de atuação."
        action={
          <Button as="a" href="/sgp/upfs/" variant="secondary">
            Voltar para UPFs
          </Button>
        }
      />
    </div>
  );
}
