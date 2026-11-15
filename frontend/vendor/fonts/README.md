# Fontes (vendor)

Fontes pixel com licença **SIL OFL 1.1** (ver `OFL-*.txt`). Servidas localmente, sem CDN.

Origem: repositório `google/fonts` no commit fixo `cc39c4c2c304bc368c9b7c311ea2bcc6013299fe`
(`ofl/pressstart2p/PressStart2P-Regular.ttf` e `ofl/pixelifysans/PixelifySans[wght].ttf`).

Foram reduzidas (subset) a Latin básico + Latin-1 + Latin Extended-A + pontuação, setas e ★ com `fonttools` (`pyftsubset`) e convertidas para woff2.

| Ficheiro | Uso | sha256 do ficheiro vendorizado | sha256 do TTF original |
|---|---|---|---|
| PressStart2P-latin.woff2 | `font-pixel` (títulos, botões, números) | 7c0328f69b7f69e714dd59835c7f758cb93b9b6bbbd0af873ce8aa932c38030e | 034c77f1f05ec89421e4a63f0e3a4ca1ecf852cc6d2bf611f126f275728e017d |
| PixelifySans-latin.woff2 | `font-ui` (texto de interface, peso 400–700) | 17edade2f906cc1af643109cc5f51c390ce3243360e8dc20032f1fede36c16bc | 9ba86cd010a4de309d263ceff8e8044092c9db7efda869620cb9ff1c4389e8a5 |

`font-mono` não usa ficheiro: é a pilha monoespaçada do sistema (código e enunciados).
