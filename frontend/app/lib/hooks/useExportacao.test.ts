import { describe, expect, it } from "vitest";
import { intervaloDoPolling } from "./useExportacao";

describe("intervaloDoPolling (A4 da #302)", () => {
  it("começa em 2 s e cresce a cada leitura", () => {
    expect(intervaloDoPolling(0)).toBe(2_000);
    expect(intervaloDoPolling(1)).toBe(3_000);
    expect(intervaloDoPolling(2)).toBe(4_500);
    expect(intervaloDoPolling(3)).toBeGreaterThan(intervaloDoPolling(2));
  });

  it("para de crescer em 15 s, por mais longa que seja a tarefa", () => {
    expect(intervaloDoPolling(5)).toBe(15_000);
    expect(intervaloDoPolling(100)).toBe(15_000);
  });
});
