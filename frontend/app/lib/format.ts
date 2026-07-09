// Utilitários de formatação para exibição (pt-BR). Valores ausentes ficam a cargo
// do chamador / do DefinitionList (que exibe "—"); aqui retornamos string vazia
// quando não há o que formatar.

/** Só os dígitos de uma string (ou string vazia). */
function onlyDigits(value: string | null | undefined): string {
  return (value ?? "").replace(/\D/g, "");
}

/**
 * CPF com privacidade: mantém os 3 primeiros e os 2 últimos dígitos, oculta o miolo.
 * Ex.: "12345678909" → "123.***.***-09". Retorna "" quando não há 11 dígitos.
 */
export function maskCpf(value: string | null | undefined): string {
  const digits = onlyDigits(value);
  if (digits.length !== 11) return "";
  return `${digits.slice(0, 3)}.***.***-${digits.slice(9)}`;
}

/**
 * Telefone brasileiro com máscara: "(99) 99999-9999" (celular, 11 díg.) ou
 * "(99) 9999-9999" (fixo, 10 díg.). Fora desses tamanhos retorna o valor original.
 */
export function formatPhone(value: string | null | undefined): string {
  const digits = onlyDigits(value);
  if (digits.length === 11) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
  }
  if (digits.length === 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  }
  return value?.trim() ?? "";
}

/** Área em hectares com 2 casas: 12.3 → "12,30 ha". Retorna "" para nulo/NaN. */
export function formatArea(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return "";
  return `${n.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ha`;
}

/** Boolean → "Sim"/"Não". Retorna "" para nulo/indefinido. */
export function formatBool(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return "";
  return value ? "Sim" : "Não";
}

/** CEP "12345678" → "12345-678". Retorna o valor original se não tiver 8 dígitos. */
export function formatCep(value: string | null | undefined): string {
  const digits = onlyDigits(value);
  if (digits.length !== 8) return value?.trim() ?? "";
  return `${digits.slice(0, 5)}-${digits.slice(5)}`;
}
