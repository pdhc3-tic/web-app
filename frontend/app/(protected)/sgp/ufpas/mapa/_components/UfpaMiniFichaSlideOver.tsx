"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Avatar } from "@/app/components/ui/Avatar/Avatar";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { maskCpf } from "@/app/lib/format";
import { getUfpaDetail, type UfpaDetail, type UfpaMapa } from "@/app/lib/ufpas";

type Props = {
  ufpa: UfpaMapa | null;
  onClose: () => void;
};

export function UfpaMiniFichaSlideOver({ ufpa, onClose }: Props) {
  const open = ufpa !== null;
  const ufpaId = ufpa?.id ?? null;

  // O GeoJSON do mapa traz só o essencial do marcador. CPF, foto e comunidade
  // vêm do detalhe, buscado sob demanda ao abrir a ficha.
  const [detalhe, setDetalhe] = useState<UfpaDetail | null>(null);
  const [carregando, setCarregando] = useState(false);

  useEffect(() => {
    if (ufpaId === null) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDetalhe(null);
    setCarregando(true);
    getUfpaDetail(ufpaId, controller.signal)
      .then((d) => {
        if (!controller.signal.aborted) setDetalhe(d);
      })
      .catch(() => {})
      .finally(() => {
        if (!controller.signal.aborted) setCarregando(false);
      });
    return () => controller.abort();
  }, [ufpaId]);

  const cpf = detalhe ? maskCpf(detalhe.titular.cpf) : carregando ? "Carregando…" : undefined;

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={ufpa?.nome_titular ?? "UFPA"}
      footer={
        ufpa && (
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>Fechar</Button>
            <Link href={`/sgp/ufpas/${ufpa.id}/`}>
              <Button leftIcon={<ExternalLink className="h-4 w-4" />}>
                Abrir ficha completa
              </Button>
            </Link>
          </div>
        )
      }
    >
      {ufpa && (
        <div className="flex flex-col gap-4 px-4 py-4">
          <div className="flex items-center gap-3">
            <Avatar name={ufpa.nome_titular} src={detalhe?.foto_url || undefined} size="lg" />
            <div className="min-w-0">
              <p className="truncate text-base font-semibold text-text">{ufpa.nome_titular}</p>
              <p className="text-xs text-text-muted">
                {ufpa.ativo ? "UFPA ativa" : "UFPA inativa"}
              </p>
            </div>
          </div>

          <DefinitionList
            items={[
              { label: "CPF", value: cpf },
              { label: "Município", value: ufpa.municipio?.nome },
              { label: "Território", value: ufpa.territorio ?? undefined },
              { label: "Comunidade", value: detalhe?.comunidade?.nome },
              {
                label: "Coordenadas",
                value: `${ufpa.latitude.toFixed(5)}, ${ufpa.longitude.toFixed(5)}`,
              },
            ]}
          />
        </div>
      )}
    </SlideOver>
  );
}
