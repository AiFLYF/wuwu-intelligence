/* ============================================================
   万物智能 WUWU® — SHARED THREE.JS HELPERS
   ------------------------------------------------------------
   灯板（led-panel.js）与信号流（flow.js）共用的数学工具和
   柔光贴图 —— 同一段代码不再各存一份。
   ============================================================ */

import * as THREE from 'three';

export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const damp = (a, b, l, dt) => a + (b - a) * (1 - Math.exp(-l * dt));
export const smoothstep = (e0, e1, x) => {
  const t = clamp((x - e0) / (e1 - e0), 0, 1);
  return t * t * (3 - 2 * t);
};

/* 径向柔光贴图：灯板背光、节点光晕共用一张即可，各自持有独立实例
   （两个 scene 各有一个 WebGLRenderer，纹理不跨 renderer 复用）。 */
export function radialTexture() {
  const S = 256;
  const cv = document.createElement('canvas');
  cv.width = cv.height = S;
  const cx = cv.getContext('2d');
  const g = cx.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
  g.addColorStop(0.00, 'rgba(255,255,255,0.88)');
  g.addColorStop(0.26, 'rgba(255,255,255,0.31)');
  g.addColorStop(0.60, 'rgba(255,255,255,0.07)');
  g.addColorStop(1.00, 'rgba(255,255,255,0)');
  cx.fillStyle = g;
  cx.fillRect(0, 0, S, S);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
