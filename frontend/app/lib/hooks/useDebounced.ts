import { useEffect, useState } from "react";

/** O valor, só depois de `ms` sem mudar — para não consultar a API a cada tecla. */
export function useDebounced<T>(valor: T, ms = 400): T {
  const [adiado, setAdiado] = useState(valor);
  useEffect(() => {
    const t = setTimeout(() => setAdiado(valor), ms);
    return () => clearTimeout(t);
  }, [valor, ms]);
  return adiado;
}
