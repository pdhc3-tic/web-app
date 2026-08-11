import { TargetIcon } from "lucide-react";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Button } from "@/app/components/ui/Button/Button";

/**
 * 404 da rota de detalhe da Meta. Acionada via notFound() tanto para id
 * inexistente quanto para id não numérico na URL.
 */
export default function MetaNotFound() {
  return (
    <div className="mx-auto max-w-5xl pt-8">
      <EmptyState
        icon={<TargetIcon className="h-7 w-7" />}
        title="Meta não encontrada"
        description="A Meta que você tentou abrir não existe ou foi removida."
        action={
          <Button as="a" href="/sgp/metas" variant="secondary">
            Voltar para as Metas
          </Button>
        }
      />
    </div>
  );
}
