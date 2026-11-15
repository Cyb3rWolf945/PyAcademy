# GSAP (vendor)

- Versão fixa: **gsap@3.12.5** (npm tarball `gsap-3.12.5.tgz`, sha256 `134ab4f04f6d98d5fd55f89b6f07726a3b9660c483d4ca31acc0efec62fd5236`).
- Ficheiros (builds UMD minificados de `dist/`, carregados por `<script>` dinâmico em `services/motion.js`; só o necessário):

| Ficheiro | gzip | sha256 |
|---|---|---|
| gsap.min.js | 28 KB | 28033e449a31ebcc396e5be8b13b63152bf03094288fb5867034321927bce087 |
| Flip.min.js | 9.5 KB | f2622faa488dbbe4e281d6e2f23d3f408928c26273506b8a75d8cb769e9770db |
| ScrollTrigger.min.js | 17.7 KB | ad33c2df9ada8a663c2147357828f980d0b7ca731ef33eb3c6e4f327c3b2cda5 |

- Licença: "Standard 'no charge' license" da GreenSock (https://gsap.com/standard-license): uso gratuito, incluindo plugins desde a 3.12. Os cabeçalhos `@license` dos ficheiros mantêm-se.
- Nunca é carregado de CDN, só depois do primeiro pixel, e só se o utilizador não pedir movimento reduzido (ver `frontend/services/motion.js`).
- Para atualizar: `npm pack gsap@<versão>` num contentor `node:20-alpine`, copiar os 3 ficheiros e atualizar esta tabela.

## CSP (`style-src 'self'`)
Os ficheiros estão **sem alterações**. O GSAP/Flip/ScrollTrigger escrevem `style.cssText = "..."` em elementos auxiliares ao arrancar, o que a CSP bloqueia (avisos na consola). `services/motion.js` instala antes de os carregar um pequeno "shim" que faz o setter de `cssText` aplicar as propriedades uma a uma (CSSOM, permitido). O ScrollTrigger só é carregado quando `revealOnScroll()` é chamado.
