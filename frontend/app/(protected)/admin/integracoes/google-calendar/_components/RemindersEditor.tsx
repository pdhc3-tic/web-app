"use client";

import { useState, type KeyboardEvent } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Label } from "@/app/components/ui/Label/Label";
import { ErrorIcon } from "@/app/components/icons";
import {
  REMINDER_MAX_COUNT,
  formatReminder,
  validateReminder,
} from "@/app/lib/integracoes";

type Props = {
  id: string;
  value: number[];
  onChange: (reminders: number[]) => void;
  disabled?: boolean;
};

/**
 * Lista de lembretes em minutos antes do evento.
 *
 * A validação replica os limites do Google Calendar (máx. 5 lembretes, até
 * 40320 minutos) para o erro aparecer aqui, e não silenciosamente na
 * sincronização. Os lembretes ficam ordenados do mais próximo ao mais distante.
 */
export function RemindersEditor({ id, value, onChange, disabled }: Props) {
  const [rascunho, setRascunho] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const cheio = value.length >= REMINDER_MAX_COUNT;

  function adicionar() {
    const minutos = Number(rascunho.trim());
    if (rascunho.trim() === "") {
      setErro("Informe os minutos de antecedência.");
      return;
    }

    const problema = validateReminder(minutos, value);
    if (problema) {
      setErro(problema);
      return;
    }

    onChange([...value, minutos].sort((a, b) => a - b));
    setRascunho("");
    setErro(null);
  }

  function remover(minutos: number) {
    onChange(value.filter((m) => m !== minutos));
    setErro(null);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      // Sem isto o Enter submeteria o formulário inteiro em vez de adicionar.
      e.preventDefault();
      adicionar();
    }
  }

  const errorId = erro ? `${id}-error` : undefined;

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>Lembretes</Label>

      <div className="flex items-start gap-2">
        <input
          id={id}
          type="number"
          inputMode="numeric"
          min={1}
          step={1}
          value={rascunho}
          disabled={disabled || cheio}
          placeholder="Minutos antes"
          aria-invalid={!!erro || undefined}
          aria-errormessage={errorId}
          aria-describedby={`${id}-help`}
          onChange={(e) => {
            setRascunho(e.target.value);
            setErro(null);
          }}
          onKeyDown={onKeyDown}
          className="h-9 w-40 rounded-md border border-border bg-surface px-3 text-sm text-text outline-none transition duration-120 enabled:hover:border-text-muted focus:border-2 focus:border-primary disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-70"
        />
        <Button
          type="button"
          variant="secondary"
          onClick={adicionar}
          disabled={disabled || cheio}
          leftIcon={<Plus className="h-4 w-4" />}
        >
          Adicionar
        </Button>
      </div>

      <p id={`${id}-help`} className="text-xs text-text-muted">
        {cheio
          ? `Limite de ${REMINDER_MAX_COUNT} lembretes atingido. Remova um para adicionar outro.`
          : `Até ${REMINDER_MAX_COUNT} lembretes, de 1 a 40320 minutos (4 semanas) antes do evento.`}
      </p>

      {erro && (
        <span
          id={errorId}
          role="alert"
          className="inline-flex items-center gap-1 text-xs leading-[1.4] text-error-text"
        >
          <ErrorIcon />
          {erro}
        </span>
      )}

      {value.length > 0 ? (
        <ul className="flex flex-wrap gap-2">
          {value.map((minutos) => (
            <li
              key={minutos}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-muted py-1 pl-3 pr-1 text-xs text-text"
            >
              <span>{formatReminder(minutos)}</span>
              <button
                type="button"
                disabled={disabled}
                aria-label={`Remover lembrete de ${formatReminder(minutos)}`}
                onClick={() => remover(minutos)}
                className="inline-flex h-5 w-5 items-center justify-center rounded-full text-text-muted hover:bg-surface hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
              >
                <X className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-text-muted">
          Nenhum lembrete configurado — os eventos serão criados sem aviso prévio.
        </p>
      )}
    </div>
  );
}
