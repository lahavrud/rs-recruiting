import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import { importX } from "eslint-plugin-import-x";
import tseslint from "typescript-eslint";
import eslintConfigPrettier from "eslint-config-prettier";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  globalIgnores(["dist"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      eslintConfigPrettier,
    ],
    plugins: {
      "import-x": importX,
    },
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // File-length guardrail — error at 600 (blank lines and comments excluded).
      // Extract to co-located components/ subfolder per CLAUDE.md conventions.
      "max-lines": ["error", { max: 600, skipBlankLines: true, skipComments: true }],

      // Bare magic numbers: warn to encourage named constants.
      // HTTP status codes, small integers, and common boundary values are allowed.
      "no-magic-numbers": [
        "warn",
        {
          ignore: [-1, 0, 1, 2, 3, 100, 200, 201, 204, 400, 401, 403, 404, 409, 422, 429, 500],
          ignoreArrayIndexes: true,
          ignoreDefaultValues: true,
          ignoreClassFieldInitialValues: true,
        },
      ],

      // Import order: React first, then other third-party packages, then the
      // `@/` alias (internal source), then relative imports, blank line
      // between each group. Only the `order` rule is registered (not the
      // `recommended`/`typescript` presets) — those add resolution-based
      // checks (no-unresolved, named, ...) that need a module resolver this
      // project doesn't configure, and which TypeScript already covers.
      "import-x/order": [
        "error",
        {
          groups: ["external", "internal", ["parent", "sibling", "index"], "type"],
          pathGroups: [
            { pattern: "react", group: "external", position: "before" },
            { pattern: "react-dom/**", group: "external", position: "before" },
            { pattern: "@/**", group: "internal", position: "before" },
          ],
          pathGroupsExcludedImportTypes: ["react"],
          "newlines-between": "always",
          alphabetize: { order: "asc", caseInsensitive: true },
        },
      ],
    },
  },
]);
