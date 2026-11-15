# three.js (vendor)

- Versão fixa: **three@0.170.0** (npm), ficheiro `build/three.module.min.js` do tarball `three-0.170.0.tgz` (sha256 do tarball: 4a608a355dcaba72e0e5383cdc814303f5b6060b43c238cdf6932dceb699238d).
- sha256 de `three.module.min.js`: 08fd7545d13d2c7fb65ab691530a802dafefd638596501854f267d0fb13c39e7 (~170 KB gzip).
- Licença MIT (`LICENSE`).
- Esta versão é um módulo **único e sem imports**, por isso não foi preciso corrigir especificadores nem vendorizar *addons*.
  A pixelização (renderer a baixa resolução + `image-rendering: pixelated`) está em `frontend/scenes/scene-base.js`, sem `RenderPixelatedPass`.
- Importa-se por caminho absoluto: `import("/vendor/three/three.module.min.js")` (a CSP proíbe import maps inline).
- Só é carregado por `frontend/scenes/*`, com `import()` dinâmico depois do primeiro pixel, e nunca na página do editor.
- Para atualizar: `npm pack three@<versão>` num contentor descartável, copiar o ficheiro, atualizar o sha256 aqui. Cuidado: a partir da r171 o `.min.js` passa a importar `three.core.min.js`.
