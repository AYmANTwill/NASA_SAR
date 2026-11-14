import js from "@eslint/js";
import tseslint from "typescript-eslint";
import hooks from "eslint-plugin-react-hooks";
import globals from "globals";

export default tseslint.config(
  { ignores: ["dist", "dist-demo", "node_modules", "test-results", "playwright-report", ".claude", ".tools"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": hooks },
    rules: hooks.configs.recommended.rules,
  },
  { files: ["scripts/**/*.mjs", "e2e/**/*.ts", "*.config.{js,ts}"], languageOptions: { globals: { ...globals.node, ...globals.browser } } },
);
