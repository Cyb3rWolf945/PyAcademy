# CodeMirror 6 (bundle ESM único)

Bundle do editor de código usado em `components/editor.js`. Carregado só nas páginas com editor (`import()` dinâmico).
Sem CDN: tudo compilado aqui, com versões fixas (`package-lock.json` incluído).

- Ficheiro: `codemirror.js` (≈370 KB, ≈127 KB gzip)
- sha256: `bfde5c4c85a4faf396cac87a48f41782f644d277d11ba99eef8eb86d07aea67e`
- Origem do código: `src/entry.js` (Python, números de linha, indentação de 4 espaços, parênteses, tema via variáveis CSS `--c-*`)

## Versões

| pacote | versão |
|---|---|
| esbuild | 0.28.2 |
| @codemirror/state | 6.7.6 |
| @codemirror/view | 6.43.15 |
| @codemirror/commands | 6.11.1 |
| @codemirror/language | 6.13.1 |
| @codemirror/lang-python | 6.2.1 |
| @codemirror/autocomplete | 6.20.4 |
| @lezer/highlight | 1.2.5 |
| imagem Docker | node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 |

## Como recompilar

Na raiz do projeto (só precisa de Docker):

```sh
sh frontend/vendor/codemirror/build.sh
shasum -a 256 frontend/vendor/codemirror/codemirror.js   # atualizar o sha256 acima
```

O comando por baixo é `npm install --save-exact <pacotes acima>` seguido de
`npx esbuild entry.js --bundle --minify --format=esm --target=es2020 --legal-comments=none --outfile=codemirror.js`,
dentro de um contentor descartável.
