// Configuração 3D de cada tema (cores dos voxels do bioma, luz e partículas). As cores de interface vêm do CSS;
// aqui ficam só as das cenas. Para um tema novo: acrescentar uma entrada e um bioma em lobby-island.js.
export const SCENES = {
  floresta: { biome: "forest", top: 0x6fcf4a, side: 0x7a5230, deep: 0x4a3220, sun: 0xfff3d0, amb: 0xbfd8ff, cloud: 0xffffff, fx: { color: 0xfff08a, kind: "float", n: 22 } },
  masmorra: { biome: "dungeon", top: 0x7d7a93, side: 0x56536c, deep: 0x34324a, sun: 0xc9b6ff, amb: 0x9a8cc0, cloud: 0x8a7aa8, fx: { color: 0xff9a3c, kind: "rise", n: 24 } },
  oceano: { biome: "ocean", top: 0xf2dca0, side: 0xd2b070, deep: 0xa07e48, sun: 0xfff2d0, amb: 0xb8e0ff, cloud: 0xffffff, fx: { color: 0xffffff, kind: "float", n: 16 } },
  deserto: { biome: "desert", top: 0xf0c070, side: 0xd49a50, deep: 0xa8703a, sun: 0xffe0a0, amb: 0xffd8b0, cloud: 0xfff0d8, fx: { color: 0xf6dca0, kind: "drift", n: 26 } },
  neve: { biome: "snow", top: 0xffffff, side: 0xbcd4ec, deep: 0x7f9cc0, sun: 0xffffff, amb: 0xc8dcff, cloud: 0xffffff, fx: { color: 0xffffff, kind: "fall", n: 40 } },
  tropico: { biome: "tropic", top: 0xf4b58c, side: 0xb4587c, deep: 0x5a2a72, sun: 0xffb27a, amb: 0xc58ad8, cloud: 0xff9fb0, water: [0x1b2f73, 0x2b4a9c], fx: { color: 0xffd9a0, kind: "float", n: 20 } },
  noite: { biome: "night", top: 0x3a3a7a, side: 0x26265a, deep: 0x16163a, sun: 0xb8b0ff, amb: 0x6a68c0, cloud: 0x4a4890, fx: { color: 0xffffff, kind: "twinkle", n: 30 } },
};
export const sceneFor = (theme) => SCENES[theme] || SCENES.floresta;
