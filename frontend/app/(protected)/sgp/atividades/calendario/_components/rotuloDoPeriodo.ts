import { endOfWeek, format, startOfWeek } from "date-fns";
import { ptBR } from "date-fns/locale";

const primeiraMaiuscula = (texto: string) => texto.charAt(0).toLocaleUpperCase("pt-BR") + texto.slice(1);

/**
 * Rótulo do período exibido no calendário, em pt-BR. Só a primeira letra vai
 * em maiúscula: "Novembro de 2026", nunca "Novembro De 2026" (#467), que era o
 * que o `capitalize` do CSS fazia com cada palavra.
 */
export function rotuloDoPeriodo(view: "dia" | "semana" | "mes", anchor: Date): string {
  if (view === "dia") {
    return format(anchor, "dd 'de' MMMM 'de' yyyy", { locale: ptBR });
  }
  if (view === "semana") {
    const ini = startOfWeek(anchor, { weekStartsOn: 0 });
    const fim = endOfWeek(anchor, { weekStartsOn: 0 });
    return `${format(ini, "dd/MM")} — ${format(fim, "dd/MM 'de' yyyy", { locale: ptBR })}`;
  }
  return primeiraMaiuscula(format(anchor, "MMMM 'de' yyyy", { locale: ptBR }));
}
