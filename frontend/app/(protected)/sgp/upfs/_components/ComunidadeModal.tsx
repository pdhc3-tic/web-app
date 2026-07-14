"use client";

import { useState } from "react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { GpsCapture } from "./GpsCapture";
import { ApiError } from "@/app/lib/api";
import { createComunidade } from "@/app/lib/upfs";
import type { SelectOption } from "@/app/components/ui/Select/Select";

type ComunidadeModalProps = {
  open: boolean;
  onClose: () => void;
  municipioId: string;
  onCreated: (option: SelectOption) => void;
};

/** Cria uma comunidade sem sair do wizard (POST /municipios/{id}/comunidades/). */
export function ComunidadeModal({
  open,
  onClose,
  municipioId,
  onCreated,
}: ComunidadeModalProps) {
  const [nome, setNome] = useState("");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [saving, setSaving] = useState(false);
  const [nomeError, setNomeError] = useState<string | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);

  function reset() {
    setNome("");
    setLat("");
    setLng("");
    setNomeError(null);
    setGlobalError(null);
  }

  function handleClose() {
    if (saving) return;
    reset();
    onClose();
  }

  async function handleSave() {
    setNomeError(null);
    setGlobalError(null);

    if (!nome.trim()) {
      setNomeError("Informe o nome da comunidade.");
      return;
    }

    setSaving(true);
    try {
      const created = await createComunidade(municipioId, {
        nome: nome.trim(),
        lat: lat.trim() || null,
        lng: lng.trim() || null,
      });
      onCreated({ value: String(created.id), label: created.nome });
      reset();
      onClose();
    } catch (e) {
      const fieldMsg =
        e instanceof ApiError
          ? e.fieldErrors?.find((f) => f.field === "nome")?.message
          : undefined;
      if (fieldMsg) {
        setNomeError(fieldMsg);
      } else {
        setGlobalError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível criar a comunidade. Tente novamente.",
        );
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <SlideOver
      open={open}
      onClose={handleClose}
      title="Nova comunidade"
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={handleClose} disabled={saving}>
            Cancelar
          </Button>
          <Button onClick={handleSave} loading={saving}>
            Salvar
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4 p-4">
        {globalError && (
          <div
            role="alert"
            className="rounded-md bg-error-bg px-3 py-2 text-sm text-error-text"
          >
            {globalError}
          </div>
        )}

        <Input
          label="Nome da comunidade"
          required
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          error={nomeError ?? undefined}
          autoFocus
        />

        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Latitude"
            inputMode="decimal"
            placeholder="opcional"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
          />
          <Input
            label="Longitude"
            inputMode="decimal"
            placeholder="opcional"
            value={lng}
            onChange={(e) => setLng(e.target.value)}
          />
        </div>

        <GpsCapture
          latitude={lat}
          longitude={lng}
          onCapture={(la, ln) => {
            setLat(la);
            setLng(ln);
          }}
        />
      </div>
    </SlideOver>
  );
}
