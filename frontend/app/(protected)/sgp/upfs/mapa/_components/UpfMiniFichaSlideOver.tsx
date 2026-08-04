"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Avatar } from "@/app/components/ui/Avatar/Avatar";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import type { UpfMapa } from "../_mock/mapaMock";

type Props = {
  upf: UpfMapa | null;
  onClose: () => void;
};

export function UpfMiniFichaSlideOver({ upf, onClose }: Props) {
  const open = upf !== null;

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={upf?.nome_titular ?? "UPF"}
      footer={
        upf && (
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>Fechar</Button>
            <Link href={`/sgp/upfs/${upf.id}/`}>
              <Button leftIcon={<ExternalLink className="h-4 w-4" />}>
                Abrir ficha completa
              </Button>
            </Link>
          </div>
        )
      }
    >
      {upf && (
        <div className="flex flex-col gap-4 px-4 py-4">
          <div className="flex items-center gap-3">
            <Avatar name={upf.nome_titular} src={upf.foto_url ?? undefined} size="lg" />
            <div className="min-w-0">
              <p className="truncate text-base font-semibold text-text">{upf.nome_titular}</p>
              <p className="text-xs text-text-muted">
                {upf.ativa ? "UPF ativa" : "UPF inativa"}
              </p>
            </div>
          </div>

          <DefinitionList
            items={[
              { label: "CPF", value: upf.cpf },
              { label: "Município", value: upf.municipio },
              { label: "Território", value: upf.territorio ?? undefined },
              { label: "Coordenadas", value: `${upf.latitude.toFixed(5)}, ${upf.longitude.toFixed(5)}` },
            ]}
          />
        </div>
      )}
    </SlideOver>
  );
}
