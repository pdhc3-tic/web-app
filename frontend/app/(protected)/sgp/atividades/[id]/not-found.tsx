import { CalendarOff } from "lucide-react";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Button } from "@/app/components/ui/Button/Button";

/**
 * 404 customizada da rota de detalhe da Atividade. É acionada via notFound() e
 * cobre tanto "atividade inexistente" quanto "fora do escopo territorial" — o
 * backend responde 404 nos dois casos, sem distinção, para não revelar a
 * existência de registros de outro território.
 */
export default function AtividadeNotFound() {
  return (
    <div className="mx-auto max-w-5xl pt-8">
      <EmptyState
        icon={<CalendarOff className="h-7 w-7" />}
        title="Atividade não encontrada ou fora do seu escopo"
        description="A atividade que você tentou abrir não existe ou está fora do seu território de atuação."
        action={
          <Button as="a" href="/sgp/atividades/" variant="secondary">
            Voltar para Atividades
          </Button>
        }
      />
    </div>
  );
}
