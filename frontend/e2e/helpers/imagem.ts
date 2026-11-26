import { randomBytes } from "node:crypto";
import { deflateSync, crc32 } from "node:zlib";

/**
 * PNG RGB de ruído, `lado × lado`, gerado na hora. Ruído quase não comprime
 * em PNG, então um lado de 1000 px já passa de 2 MB: serve para testar a
 * compressão automática da foto (#464) sem guardar binário no repositório.
 */
export function pngDeRuido(lado: number): Buffer {
  const linha = 1 + lado * 3;
  const cru = randomBytes(linha * lado);
  for (let y = 0; y < lado; y++) cru[y * linha] = 0; // filtro "None" em cada linha

  const bloco = (tipo: string, dados: Buffer) => {
    const tamanho = Buffer.alloc(4);
    tamanho.writeUInt32BE(dados.length);
    const corpo = Buffer.concat([Buffer.from(tipo, "ascii"), dados]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(corpo));
    return Buffer.concat([tamanho, corpo, crc]);
  };

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(lado, 0);
  ihdr.writeUInt32BE(lado, 4);
  ihdr[8] = 8; // 8 bits por canal
  ihdr[9] = 2; // RGB
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    bloco("IHDR", ihdr),
    bloco("IDAT", deflateSync(cru)),
    bloco("IEND", Buffer.alloc(0)),
  ]);
}
