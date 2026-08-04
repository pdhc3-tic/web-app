"use client";

import { useState } from "react";
import { Camera, Pencil, X } from "lucide-react";
import { Avatar } from "@/app/components/ui/Avatar/Avatar";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { Button } from "@/app/components/ui/Button/Button";
import { PhotoUploader } from "@/app/components/sgp/PhotoUploader/PhotoUploader";
import { maskCpf } from "@/app/lib/format";
import type { UpfDetail } from "@/app/lib/upfs";

type UpfHeaderProps = {
  upf: UpfDetail;
  /** Chamado após upload/remoção de foto com sucesso, para refletir imediatamente na ficha. */
  onPhotoChange: (url: string | null) => void;
};

/** Cabeçalho da UPF: foto + nome + CPF mascarado + chips de local/status + Editar. */
export function UpfHeader({ upf, onPhotoChange }: UpfHeaderProps) {
  const cpf = maskCpf(upf.titular.cpf);
  const [photoOpen, setPhotoOpen] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <button
          type="button"
          onClick={() => setPhotoOpen((o) => !o)}
          aria-expanded={photoOpen}
          aria-label="Trocar foto do titular"
          className="group relative shrink-0 rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
        >
          <Avatar
            name={upf.titular.nome_completo}
            src={upf.foto_url || null}
            size="lg"
            className="shadow-sm"
          />
          <span className="pointer-events-none absolute inset-0 flex items-center justify-center gap-1 rounded-full bg-black/50 text-2xs font-medium text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
            <Camera className="h-3.5 w-3.5" aria-hidden="true" />
            Trocar foto
          </span>
        </button>

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-semibold tracking-tight text-text">
            {upf.titular.nome_completo}
          </h1>
          <p className="mt-0.5 text-sm text-text-muted tabular-nums">
            {cpf || "CPF não informado"}
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Chip>{upf.municipio.nome}</Chip>
            {upf.territorio && <Chip>{upf.territorio.nome}</Chip>}
            <Badge status={upf.ativa ? "ativo" : "inativo"} />
          </div>
        </div>

        <div className="shrink-0">
          <Button
            as="a"
            href={`/sgp/upfs/${upf.id}/editar/`}
            variant="secondary"
            size="sm"
            leftIcon={<Pencil className="h-4 w-4" />}
          >
            Editar
          </Button>
        </div>
      </div>

      {photoOpen && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text">Foto do titular</h2>
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<X className="h-4 w-4" />}
              onClick={() => setPhotoOpen(false)}
            >
              Fechar
            </Button>
          </div>
          <PhotoUploader
            currentUrl={upf.foto_url || null}
            onChange={onPhotoChange}
            uploadUrlEndpoint={`/api/v1/upfs/${upf.id}/foto/upload-url/`}
            confirmEndpoint={`/api/v1/upfs/${upf.id}/foto/confirm/`}
            deleteEndpoint={`/api/v1/upfs/${upf.id}/foto/`}
          />
        </div>
      )}
    </div>
  );
}
