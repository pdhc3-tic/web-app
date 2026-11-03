import { excedenteDoPago } from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";

/**
 * Aviso não bloqueante da conclusão (#360): pagar acima do autorizado é
 * permitido, e o backend registra o excedente como risco de glosa.
 */
export function AvisoAcimaDoAutorizado({
  solicitacaoId,
  pago,
  autorizado,
}: {
  solicitacaoId: number;
  pago: string;
  autorizado: string;
}) {
  const excedente = excedenteDoPago(pago, autorizado);
  if (excedente === null) return null;
  return (
    <p role="status" className="text-sm text-warning-text" data-testid={`aviso-acima-do-autorizado-${solicitacaoId}`}>
      {formatCurrencyBRL(excedente)} acima do autorizado; será registrado no relatório de risco de glosa.
    </p>
  );
}
