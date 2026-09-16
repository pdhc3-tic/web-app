"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/app/lib/api";

export type FetchState<T> = {
  data: T;
  /** Update local state sem disparar um novo fetch (ex.: update otimista). */
  setData: React.Dispatch<React.SetStateAction<T>>;
  loading: boolean;
  error: string | null;
  reload: () => void;
};

/**
 * Encapsula o padrão useState+useEffect+AbortController para chamadas de API
 * em componentes de abas. O `fetcher` é estabilizado via ref — pode ser uma
 * arrow inline sem precisar de useCallback no caller.
 *
 * `deps` deve listar as variáveis externas que, quando mudam, disparam um novo
 * fetch (equivalente ao array de deps do useEffect). `reload()` também dispara.
 */
export function useFetch<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  initialData: T,
  deps: unknown[],
): FetchState<T> {
  const [data, setData] = useState<T>(initialData);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const fetcherRef = useRef(fetcher);
  // eslint-disable-next-line react-hooks/refs
  fetcherRef.current = fetcher;

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    fetcherRef.current(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError ? e.message : "Não foi possível carregar.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  return { data, setData, loading, error, reload };
}
