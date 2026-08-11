/**
 * Paleta semântica de status — espelha `STATUS_COR_MAP` do backend em
 * apps/sgp/serializers.py. As atividades do calendário já vêm com `cor` HEX
 * pronto no payload; este mapa serve como fallback local e para colorir a
 * legenda quando não há eventos.
 */
export const STATUS_HEX_COLORS: Record<string, string> = {
  planejado: "#6B7280",
  agendado: "#3B82F6",
  em_andamento: "#F59E0B",
  concluido: "#10B981",
  concluido_sem_evidencia: "#14B8A6",
  adiada: "#8B5CF6",
  nao_realizada: "#EF4444",
  cancelada: "#9CA3AF",
};

export function statusHexColor(status: string): string {
  return STATUS_HEX_COLORS[status] ?? STATUS_HEX_COLORS.planejado;
}
