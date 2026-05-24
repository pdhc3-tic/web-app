import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Proibir cores hard-coded em inline styles — todos os valores de cor devem
  // usar var(--color-*) do design system definido em globals.css.
  {
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "JSXAttribute[name.name='style'] ObjectExpression Property > Literal[value=/^#[0-9a-fA-F]{3,8}|^rgba?\\(|^hsla?\\(/i]",
          message:
            "Cor hard-coded em inline style. Use var(--color-*) do design system (globals.css).",
        },
      ],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
