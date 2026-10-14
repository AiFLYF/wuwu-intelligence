/* ============================================================
   万物智能 WUWU® — LED PANEL
   ------------------------------------------------------------
   首屏主视觉：一块真实的 8×8 WS2812B-64 灯板，用 three.js 渲染。
   64 颗灯珠各自独立发光（自定义 additive point shader），
   循环播放 7 套效果，切换时逐颗平滑过渡。
   纯几何 + 加法混合自发光，不依赖后处理，离线可跑。
   ============================================================ */

import * as THREE from 'three';
import { clamp, damp, radialTexture } from './three-common.js';

import { PATTERNS } from './demo-model.js';

const FADE = 5.5;   // 过渡阻尼

/* ---------- shaders ---------- */

const LED_VERT = /* glsl */ `
attribute vec3 aColor;
attribute float aSize;
uniform float uSize;
uniform float uDpr;
varying vec3 vColor;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mv;
  float dist = max(0.5, -mv.z);
  gl_PointSize = uSize * aSize * uDpr * (20.0 / dist);
  vColor = aColor;
}`;

const LED_FRAG = /* glsl */ `
varying vec3 vColor;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  if (d > 1.0) discard;
  float halo = pow(1.0 - d, 3.4);          // 外圈柔光
  float core = pow(max(0.0, 1.0 - d * 2.5), 6.0); // 灯芯高光
  vec3 col = vColor * (halo * 0.85 + core * 1.7) + vColor * (core * 0.55);
  col += vColor * 0.045;                    // 未点亮时的灯珠本体
  gl_FragColor = vec4(col, 1.0);
}`;

const DUST_VERT = /* glsl */ `
attribute float aSize;
attribute float aSeed;
uniform float uSize;
uniform float uDpr;
uniform float uTime;
varying float vA;
void main() {
  vec3 p = position;
  p.y += sin(uTime * 0.32 + aSeed * 6.28) * 0.5;
  p.x += cos(uTime * 0.24 + aSeed * 4.71) * 0.5;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float dist = max(0.5, -mv.z);
  gl_PointSize = uSize * aSize * uDpr * (20.0 / dist);
  vA = 0.35 + 0.65 * (0.5 + 0.5 * sin(uTime * 0.9 + aSeed * 12.0));
}`;

const DUST_FRAG = /* glsl */ `
varying float vA;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  if (d > 1.0) discard;
  float a = pow(1.0 - d, 2.6) * vA;
  gl_FragColor = vec4(vec3(0.62, 0.66, 0.72) * a, a);
}`;

/* ---------- scene ---------- */

const G = 8;          // 8 × 8
const PLATE = 8.7;    // 板子边长
const Z_LED = 0.2;

export function initLedPanel(canvas, opts = {}) {
  if (!canvas) return null;

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'low-power',
    });
  } catch (err) {
    console.warn('[wuwu] WebGL unavailable for LED panel:', err);
    return null;
  }

  const dpr = clamp(window.devicePixelRatio || 1, 1, 2);
  renderer.setPixelRatio(dpr);
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 160);
  camera.position.set(0, 0, 24);

  /* — 灯板本体 — */
  const group = new THREE.Group();
  group.rotation.set(-0.2, 0.3, -0.035);
  scene.add(group);

  const plateGeo = new THREE.BoxGeometry(PLATE, PLATE, 0.34);
  const plateMat = new THREE.MeshBasicMaterial({ color: 0x0a0b0e });
  group.add(new THREE.Mesh(plateGeo, plateMat));

  const edgeGeo = new THREE.EdgesGeometry(plateGeo);
  const edgeMat = new THREE.LineBasicMaterial({ color: 0x3a4048, transparent: true, opacity: 0.85 });
  group.add(new THREE.LineSegments(edgeGeo, edgeMat));

  // 8×8 单元栅格
  const gridPts = [];
  for (let i = 0; i <= G; i++) {
    const p = -4 + i;
    gridPts.push(p, -4, 0.19, p, 4, 0.19);
    gridPts.push(-4, p, 0.19, 4, p, 0.19);
  }
  const gridGeo = new THREE.BufferGeometry();
  gridGeo.setAttribute('position', new THREE.Float32BufferAttribute(gridPts, 3));
  const gridMat = new THREE.LineBasicMaterial({ color: 0x252a31, transparent: true, opacity: 0.9 });
  group.add(new THREE.LineSegments(gridGeo, gridMat));

  /* — 64 颗灯珠 — */
  const COUNT = G * G;
  const pos = new Float32Array(COUNT * 3);
  const col = new Float32Array(COUNT * 3);
  const siz = new Float32Array(COUNT);
  const ledX = new Float32Array(COUNT);
  const ledY = new Float32Array(COUNT);

  for (let r = 0; r < G; r++) {
    for (let c = 0; c < G; c++) {
      const i = r * G + c;
      ledX[i] = c;
      ledY[i] = r;
      pos[i * 3] = c - 3.5;
      pos[i * 3 + 1] = 3.5 - r;
      pos[i * 3 + 2] = Z_LED;
      siz[i] = 0.94 + ((r * 7 + c * 13) % 11) * 0.012;
    }
  }

  const ledGeo = new THREE.BufferGeometry();
  ledGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  ledGeo.setAttribute('aColor', new THREE.BufferAttribute(col, 3));
  ledGeo.setAttribute('aSize', new THREE.BufferAttribute(siz, 1));

  const ledUni = {
    uSize: { value: 46 },
    uDpr: { value: dpr },
  };
  const ledMat = new THREE.ShaderMaterial({
    uniforms: ledUni,
    vertexShader: LED_VERT,
    fragmentShader: LED_FRAG,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const leds = new THREE.Points(ledGeo, ledMat);
  leds.frustumCulled = false;
  group.add(leds);

  /* — 浮尘 — */
  const DUST = 380;
  const dPos = new Float32Array(DUST * 3);
  const dSiz = new Float32Array(DUST);
  const dSeed = new Float32Array(DUST);
  for (let i = 0; i < DUST; i++) {
    dPos[i * 3] = (Math.random() - 0.5) * 30;
    dPos[i * 3 + 1] = (Math.random() - 0.5) * 24;
    dPos[i * 3 + 2] = (Math.random() - 0.5) * 16 - 3;
    dSiz[i] = 0.5 + Math.random() * 1.7;
    dSeed[i] = Math.random();
  }
  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute('position', new THREE.BufferAttribute(dPos, 3));
  dustGeo.setAttribute('aSize', new THREE.BufferAttribute(dSiz, 1));
  dustGeo.setAttribute('aSeed', new THREE.BufferAttribute(dSeed, 1));
  const dustUni = { uSize: { value: 2.6 }, uDpr: { value: dpr }, uTime: { value: 0 } };
  const dustMat = new THREE.ShaderMaterial({
    uniforms: dustUni,
    vertexShader: DUST_VERT,
    fragmentShader: DUST_FRAG,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const dust = new THREE.Points(dustGeo, dustMat);
  dust.frustumCulled = false;
  scene.add(dust);

  /* — 板后柔光 — */
  const glowTex = radialTexture();
  const glowMat = new THREE.SpriteMaterial({
    map: glowTex,
    color: 0xff4b3e,
    transparent: true,
    opacity: 0.5,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const backGlow = new THREE.Sprite(glowMat);
  backGlow.scale.set(30, 30, 1);
  backGlow.position.z = -6;
  scene.add(backGlow);

  /* — 相机自适应：保证整块板子始终落在画面 86% 内 — */
  const corners = [];
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) {
    corners.push(new THREE.Vector3(sx * 4.75, sy * 4.75, sz * 0.3));
  }
  const baseRot = group.rotation.clone();

  function fitCamera() {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    camera.aspect = w / h;

    group.rotation.copy(baseRot);
    group.updateMatrixWorld(true);

    let z = camera.position.z;
    for (let k = 0; k < 7; k++) {
      camera.position.set(0, 0, z);
      camera.lookAt(0, 0, 0);
      camera.updateProjectionMatrix();
      camera.updateMatrixWorld(true);

      let mx = 0, my = 0;
      for (const c of corners) {
        const v = c.clone().applyMatrix4(group.matrixWorld).project(camera);
        mx = Math.max(mx, Math.abs(v.x));
        my = Math.max(my, Math.abs(v.y));
      }
      const s = Math.max(mx, my) / 0.83;
      if (Math.abs(s - 1) < 0.004) break;
      z *= s;
    }
    camera.position.z = z;
    camera.lookAt(0, 0, 0);
  }

  /* — 状态 — */
  const cur = new Float32Array(COUNT * 3);
  let patIdx = 0;
  let elapsed = 0;
  let brightness = 128 / 255;
  let solidColor = [1, 0, 0];
  let playing = true;
  let dirty = true;
  let active = true;
  let reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // 初始状态：直接落位到第一套效果，避免开场从黑里淡入太慢
  for (let i = 0; i < COUNT; i++) {
    const c = PATTERNS[0].fn(ledX[i], ledY[i], 0);
    cur[i * 3] = c[0]; cur[i * 3 + 1] = c[1]; cur[i * 3 + 2] = c[2];
  }

  // 每次换效果都要通知 HUD：自动轮播也不例外，
  // 否则标签和圆点会一直停在初始的那一套效果上，和灯板对不上。
  function setPattern(i) {
    patIdx = ((i % PATTERNS.length) + PATTERNS.length) % PATTERNS.length;
    dirty = true;
    if (opts.onPattern) opts.onPattern(patIdx, PATTERNS[patIdx]);
  }

  /* — 指针视差 — */
  const pointer = { x: 0, y: 0, tx: 0, ty: 0, on: false };
  const fine = matchMedia('(pointer: fine)').matches;

  function onMove(e) {
    if (reduced || !playing) return;
    const r = canvas.getBoundingClientRect();
    pointer.tx = ((e.clientX - r.left) / r.width) * 2 - 1;
    pointer.ty = -(((e.clientY - r.top) / r.height) * 2 - 1);
    pointer.on = true;
  }
  const onLeave = () => { pointer.tx = 0; pointer.ty = 0; };
  if (fine) {
    canvas.addEventListener('pointermove', onMove);
    canvas.addEventListener('pointerleave', onLeave);
  }



  /* — 渲染 — */
  const tmp = new THREE.Color();
  let meanR = 1, meanG = 0.29, meanB = 0.24;

  function update(dt) {
    if (!active || dt <= 0 || ((reduced || !playing) && !dirty)) return;
    if (!reduced && playing) elapsed += dt;
    dirty = false;

    // 逐颗灯珠向目标色平滑过渡
    const p = PATTERNS[patIdx];
    const tt = reduced ? 0.6 : elapsed;
    let sr = 0, sg = 0, sb = 0;
    for (let i = 0; i < COUNT; i++) {
      const c = (patIdx === 0 ? solidColor : p.fn(ledX[i], ledY[i], tt)).map(v => v * brightness);
      const i3 = i * 3;
      cur[i3]     = (reduced || !playing) ? c[0] : damp(cur[i3], c[0], FADE, dt);
      cur[i3 + 1] = (reduced || !playing) ? c[1] : damp(cur[i3 + 1], c[1], FADE, dt);
      cur[i3 + 2] = (reduced || !playing) ? c[2] : damp(cur[i3 + 2], c[2], FADE, dt);
      sr += cur[i3]; sg += cur[i3 + 1]; sb += cur[i3 + 2];
    }
    col.set(cur);
    ledGeo.attributes.aColor.needsUpdate = true;

    meanR = damp(meanR, sr / COUNT, 1.4, dt);
    meanG = damp(meanG, sg / COUNT, 1.4, dt);
    meanB = damp(meanB, sb / COUNT, 1.4, dt);
    tmp.setRGB(meanR, meanG, meanB);
    backGlow.material.color.copy(tmp);
    backGlow.material.opacity = 0.32 + 0.3 * (meanR + meanG + meanB) / 3;

    // 指针视差 + 轻微呼吸
    pointer.x = damp(pointer.x, pointer.tx, 3.2, dt);
    pointer.y = damp(pointer.y, pointer.ty, 3.2, dt);
    const idle = reduced ? 0 : Math.sin(elapsed * 0.34) * 0.05;
    camera.position.x = pointer.x * 1.5;
    camera.position.y = pointer.y * 1.1;
    camera.lookAt(0, 0, 0);
    group.rotation.y = baseRot.y + pointer.x * 0.13 + idle;
    group.rotation.x = baseRot.x - pointer.y * 0.11;

    dustUni.uTime.value = elapsed;
    dust.rotation.y = elapsed * 0.014;
    backGlow.position.x = camera.position.x * 0.4;
    backGlow.position.y = camera.position.y * 0.4;

    renderer.render(scene, camera);
  }

  function resize() {
    dirty = true;
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    renderer.setSize(w, h, false);
    ledUni.uSize.value = Math.max(26, Math.min(58, w * 0.088));
    fitCamera();
  }

  resize();

  return {
    patterns: PATTERNS,
    get index() { return patIdx; },
    setPattern,
    next: () => setPattern(patIdx + 1),
    setActive(v) { active = v; dirty = true; },
    setBrightness(v) { brightness = clamp(v, 0, 255) / 255; dirty = true; },
    setColor(v) { solidColor = v; dirty = true; },
    setPlaying(v) { playing = v; dirty = true; },
    setReducedMotion(v) { reduced = v; dirty = true; if (v) onLeave(); },
    update,
    resize,
    dispose() {
      if (fine) {
        canvas.removeEventListener('pointermove', onMove);
        canvas.removeEventListener('pointerleave', onLeave);
      }
      scene.clear();
      plateGeo.dispose(); edgeGeo.dispose(); gridGeo.dispose();
      ledGeo.dispose(); dustGeo.dispose();
      plateMat.dispose(); edgeMat.dispose(); gridMat.dispose();
      ledMat.dispose(); dustMat.dispose(); glowMat.dispose();
      glowTex.dispose();
      renderer.dispose();
    },
  };
}
