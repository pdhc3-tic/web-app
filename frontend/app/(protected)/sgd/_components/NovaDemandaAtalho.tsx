"use client";

import { Plus } from "lucide-react";
import { useSession } from "next-auth/react";
import { Button } from "@/app/components/ui/Button/Button";
import { canCreateDemanda } from "@/app/lib/auth/roles";

/** Entrada do SGD para criar demanda fora da ficha da atividade (#294). */
export function NovaDemandaAtalho() {
  const { data: session } = useSession();
  if (!canCreateDemanda(session?.user)) return null;

  return (
    <Button
      as="a"
      href="/sgd/demandas/nova"
      leftIcon={<Plus className="h-4 w-4" />}
      data-testid="sgd-nova-demanda"
    >
      Nova demanda
    </Button>
  );
}
