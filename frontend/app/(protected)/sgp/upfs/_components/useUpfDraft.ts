"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { UpfFormData } from "./upfForm";

const DRAFT_PREFIX = "sgp.upf.draft.";
const SAVE_DEBOUNCE_MS = 500;

type StoredDraft = { data: UpfFormData; at: string };

export type DraftInfo = { data: UpfFormData; at: string };

/**
 * Persistência de rascunho do wizard em localStorage.
 * Chave: `sgp.upf.draft.{id|novo}`. `save` é debounced; `existing` é lido uma vez
 * no mount (para oferecer "Continuar rascunho"). `clear` remove após submit.
 */
export function useUpfDraft(key: string) {
  const storageKey = `${DRAFT_PREFIX}${key}`;
  const [existing, setExisting] = useState<DraftInfo | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as StoredDraft;
        // eslint-disable-next-line react-hooks/set-state-in-effect
        if (parsed?.data) setExisting({ data: parsed.data, at: parsed.at });
      }
    } catch {
      /* rascunho corrompido — ignora */
    }
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [storageKey]);

  const save = useCallback(
    (data: UpfFormData) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        try {
          const payload: StoredDraft = { data, at: new Date().toISOString() };
          localStorage.setItem(storageKey, JSON.stringify(payload));
        } catch {
          /* cota cheia ou indisponível — ignora */
        }
      }, SAVE_DEBOUNCE_MS);
    },
    [storageKey],
  );

  const clear = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    try {
      localStorage.removeItem(storageKey);
    } catch {
      /* ignora */
    }
    setExisting(null);
  }, [storageKey]);

  return { existing, save, clear };
}
