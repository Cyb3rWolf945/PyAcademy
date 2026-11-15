#!/bin/sh
# Compila o bundle CodeMirror dentro de um contentor descartável (node:20-alpine fixo por digest).
# Uso (a partir da raiz do projeto): sh frontend/vendor/codemirror/build.sh
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
docker run --rm -v "$HERE:/out" node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 sh -c '
  set -eu
  mkdir /build && cd /build && cp /out/src/entry.js .
  npm init -y >/dev/null
  npm install --no-audit --no-fund --save-exact \
    esbuild@0.28.2 @codemirror/state@6.7.6 @codemirror/view@6.43.15 @codemirror/commands@6.11.1 \
    @codemirror/language@6.13.1 @codemirror/lang-python@6.2.1 @codemirror/autocomplete@6.20.4 @lezer/highlight@1.2.5
  npx esbuild entry.js --bundle --minify --format=esm --target=es2020 --legal-comments=none --outfile=/out/codemirror.js
  cp package-lock.json /out/package-lock.json
'
