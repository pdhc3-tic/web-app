import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import postcss from "postcss";
import tailwindcss from "@tailwindcss/postcss";

const entrada = new URL("../app/styleguide/govbr-spike/govbr-spike.css", import.meta.url);
const saida = new URL("../public/govbr-spike.css", import.meta.url);
const resultado = await postcss([tailwindcss()]).process(await readFile(entrada, "utf8"), {
  from: fileURLToPath(entrada),
  to: fileURLToPath(saida),
});
await writeFile(saida, resultado.css);
