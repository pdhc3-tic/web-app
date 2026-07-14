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
 * Máscara progressiva de CPF para input em tempo real: "XXX.XXX.XXX-XX".
 * Formata conforme o usuário digita (limita a 11 dígitos).
 */
export function formatCpfInput(value: string | null | undefined): string {
  const d = onlyDigits(value).slice(0, 11);
  const parts: string[] = [];
  if (d.length > 0) parts.push(d.slice(0, 3));
  if (d.length >= 4) parts.push(d.slice(3, 6));
  if (d.length >= 7) parts.push(d.slice(6, 9));
  let out = parts.join(".");
  if (d.length >= 10) out += `-${d.slice(9, 11)}`;
  return out;
}

/**
 * Valida CPF pelos dígitos verificadores. Rejeita tamanhos != 11 e todos os
 * dígitos iguais. Espelha a regra do backend (apps/sgp/validators.py).
 */
export function isValidCpf(value: string | null | undefined): boolean {
  const cpf = onlyDigits(value);
  if (cpf.length !== 11) return false;
  if (cpf === cpf[0].repeat(11)) return false;

  const calcDigit = (len: number): number => {
    let sum = 0;
    for (let i = 0; i < len; i++) {
      sum += Number(cpf[i]) * (len + 1 - i);
    }
    const rest = (sum * 10) % 11;
    return rest === 10 ? 0 : rest;
  };

  return calcDigit(9) === Number(cpf[9]) && calcDigit(10) === Number(cpf[10]);
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

/**
 * Máscara progressiva de telefone para input em tempo real.
 * Formata conforme digita: "(99) 9999-9999" (fixo) → "(99) 99999-9999" (celular),
 * limitando a 11 dígitos.
 */
export function formatPhoneInput(value: string | null | undefined): string {
  const d = onlyDigits(value).slice(0, 11);
  if (d.length === 0) return "";
  if (d.length <= 2) return `(${d}`;

  const ddd = d.slice(0, 2);
  const rest = d.slice(2);
  if (rest.length <= 4) return `(${ddd}) ${rest}`;
  if (d.length <= 10) {
    return `(${ddd}) ${rest.slice(0, 4)}-${rest.slice(4)}`;
  }
  return `(${ddd}) ${rest.slice(0, 5)}-${rest.slice(5)}`;
}

/** Telefone válido: 10 (fixo) ou 11 (celular) dígitos, incluindo DDD. */
export function isValidPhone(value: string | null | undefined): boolean {
  const d = onlyDigits(value);
  return d.length === 10 || d.length === 11;
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
