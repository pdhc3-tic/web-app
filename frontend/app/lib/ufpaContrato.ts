/** Compatibilidade com AJ-BE-09 enquanto o backend ainda publica o contrato antigo.
 * Só nomes de campos e discriminadores são traduzidos; conteúdo do usuário é preservado.
 */
export function nomeUfpa(texto: string): string {
  return texto.replace(/UPFs\b/g, "UFPAs").replace(/UPF\b/g, "UFPA")
    .replace(/upfs(?=\b|_)/g, "ufpas").replace(/upf(?=\b|_)/g, "ufpa");
}

export function caminhoBackendUfpa(caminho: string): string {
  return caminho.replace(/\/ufpas(?=\/|\?|$)/g, "/upfs")
    .replace(/([?&](?:entidade|tipo|escopo)=)ufpa(s?)(?=&|$)/g, "$1upf$2");
}

export function contratoUfpa(valor: unknown, escrita = false, campo = ""): unknown {
  // JSON livre de formulários e esquemas não faz parte do vocabulário da API.
  if (["respostas_json", "schema_json"].includes(campo)) return valor;
  if (Array.isArray(valor)) return valor.map((v) => contratoUfpa(v, escrita, campo));
  if (valor !== null && typeof valor === "object") {
    return Object.fromEntries(Object.entries(valor).map(([chave, v]) => {
      const nova = escrita ? chave.replace(/ufpa/g, "upf") : chave.replace(/upf/g, "ufpa");
      return [nova, contratoUfpa(v, escrita, chave)];
    }));
  }
  if (typeof valor === "string" && ["tipo", "entidade", "escopo"].includes(campo)) {
    return escrita ? valor.replace(/^ufpa(s?)$/, "upf$1") : valor.replace(/^upf(s?)$/, "ufpa$1");
  }
  if (!escrita && typeof valor === "string" && ["erro", "message", "detail", "nome_arquivo"].includes(campo)) {
    return nomeUfpa(valor);
  }
  return valor;
}

export function respostaUfpa(res: Response): Response {
  // Preserva o Response e seu stream, inclusive downloads e respostas sem corpo.
  const json = res.json.bind(res);
  res.json = async () => contratoUfpa(await json());
  return res;
}
