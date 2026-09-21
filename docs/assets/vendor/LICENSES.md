# Vendored assets

Self-hosted third-party assets (bundled so the site works without any external CDN):

| Asset | Version | License | Source |
|---|---|---|---|
| `three.module.min.js` | three.js r160 | MIT | https://github.com/mrdoob/three.js |
| `../fonts/f02–f03.woff2` (Clash Display 600/700) | — | ITF Free Font License | https://www.fontshare.com/fonts/clash-display |
| `../fonts/f04–f05.woff2` (Instrument Serif Italic) | — | SIL OFL 1.1 | https://fonts.google.com/specimen/Instrument+Serif |
| `../fonts/f07–f08, f10–f11.woff2` (Space Mono 400/700) | — | SIL OFL 1.1 | https://fonts.google.com/specimen/Space+Mono |

> 页面里的图标全部是内联 SVG，不再依赖 lucide（原 `lucide.min.js` 已移除）。
>
> 2026-09-21：清掉三个无人引用的字体文件 —— `f01`（Clash Display 500，全站没有元素用它）、
> `f06` / `f09`（既不在任何 `@font-face` 里，也不在授权清单的范围内）。共减 29 876 字节。
