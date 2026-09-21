/* ============================================================
   万物智能 WUWU® — SIGNAL FLOW
   ------------------------------------------------------------
   03 REGISTRY 里的 3D 信号流：一句话 → 注册表 → 执行 → 汇报。
   四个节点 + 沿链路奔跑的光点；光点经过时对应节点被点亮。
   标签是 HTML，每帧按投影定位（横向错开两行、竖向放在右侧），
   所以文字永远清晰、四个标签永不互相压到。窄屏自动转竖向链路。
   ============================================================ */

import * as THREE from 'three';
import { clamp, damp, smoothstep, radialTexture } from './three-common.js';

/* 链路节点：value 桌面用、short 窄屏用 */
const NODES = [
  { key: '01 · 你说的话',      value: '「灯板设成红色」',         short: '「灯板设成红色」',   color: '#FF4B3E' },
  { key: '02 · 匹配 commands', value: 'devices.json',            short: 'devices.json',       color: '#A78BFF' },
  { key: '03 · 执行',          value: 'led_cli.py color 255 0 0', short: 'led_cli.py 255 0 0', color: '#FFB020' },
  { key: '04 · 一句话汇报',    value: '好了，灯板已设成红色',     short: '好了，灯板已设成红色', color: '#C6FF4A' },
];

const PULSES = 14;
const SPAN_H = 3.2;    // 横向：首尾节点 x = ±3.2
const SPAN_V = 2.05;   // 竖向：首尾节点 y = ±2.05
const MIN_H = 3.6;     // 横向布局至少保证的可视高度（世界单位）
const RING_R = 0.4;    // 圆环半径

export function initFlow(canvas, labelHost) {
  if (!canvas) return null;

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch (err) {
    console.warn('[wuwu] WebGL unavailable for flow scene:', err);
    return null;
  }

  const dpr = clamp(window.devicePixelRatio || 1, 1, 2);
  renderer.setPixelRatio(dpr);
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(26, 1, 0.1, 200);

  const group = new THREE.Group();
  group.rotation.set(0.1, -0.12, 0);
  scene.add(group);

  const glowTex = radialTexture();
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- 节点 ---------- */
  const ringGeo = new THREE.TorusGeometry(RING_R, 0.012, 8, 64);
  const coreGeo = new THREE.SphereGeometry(0.095, 18, 18);

  const nodes = NODES.map((n) => {
    const c = new THREE.Color(n.color);

    const glowMat = new THREE.SpriteMaterial({
      map: glowTex, color: c, transparent: true, opacity: 0.4,
      depthWrite: false, blending: THREE.AdditiveBlending,
    });
    const glow = new THREE.Sprite(glowMat);
    glow.scale.set(1.12, 1.12, 1);

    const ringMat = new THREE.MeshBasicMaterial({
      color: c, transparent: true, opacity: 0.5, depthWrite: false,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = 0.44;

    const coreMat = new THREE.MeshBasicMaterial({
      color: c, transparent: true, opacity: 0.9,
    });
    const core = new THREE.Mesh(coreGeo, coreMat);

    const g = new THREE.Group();
    g.add(glow, ring, core);
    group.add(g);

    return { data: n, color: c, g, glow, ring, core, glowMat, ringMat, coreMat };
  });

  /* ---------- 连线 ---------- */
  const linkGeo = new THREE.BufferGeometry();
  linkGeo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array((NODES.length - 1) * 6), 3));
  const linkMat = new THREE.LineBasicMaterial({
    color: 0x9aa1ad, transparent: true, opacity: 0.28, depthWrite: false,
  });
  group.add(new THREE.LineSegments(linkGeo, linkMat));

  /* ---------- 沿链路奔跑的光点 ---------- */
  const pPos = new Float32Array(PULSES * 3);
  const pCol = new Float32Array(PULSES * 3);
  const pSiz = new Float32Array(PULSES);
  const pProg = new Float32Array(PULSES);
  const pAlpha = new Float32Array(PULSES);
  const pRamp = NODES.map((n) => new THREE.Color(n.color));

  for (let i = 0; i < PULSES; i++) {
    pProg[i] = i / PULSES;
    pSiz[i] = 0.85 + Math.random() * 0.5;
  }

  const pulseGeo = new THREE.BufferGeometry();
  pulseGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
  pulseGeo.setAttribute('aColor', new THREE.BufferAttribute(pCol, 3));
  pulseGeo.setAttribute('aSize', new THREE.BufferAttribute(pSiz, 1));
  pulseGeo.setAttribute('aAlpha', new THREE.BufferAttribute(pAlpha, 1));

  const pulseMat = new THREE.ShaderMaterial({
    uniforms: { uSize: { value: 9 }, uDpr: { value: dpr }, uRef: { value: 8 } },
    vertexShader: /* glsl */`
      attribute vec3 aColor;
      attribute float aSize;
      attribute float aAlpha;
      uniform float uSize;
      uniform float uDpr;
      uniform float uRef;
      varying vec3 vColor;
      varying float vA;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mv;
        float dist = max(0.5, -mv.z);
        gl_PointSize = uSize * aSize * uDpr * (uRef / dist) * (0.55 + aAlpha * 0.8);
        vColor = aColor;
        vA = aAlpha;
      }`,
    fragmentShader: /* glsl */`
      varying vec3 vColor;
      varying float vA;
      void main() {
        float d = length(gl_PointCoord - 0.5) * 2.0;
        if (d > 1.0) discard;
        float halo = pow(1.0 - d, 2.8);
        float core = pow(max(0.0, 1.0 - d * 2.6), 6.0);
        vec3 col = vColor * (halo * 1.0 + core * 1.4) + vec3(core * 0.5);
        gl_FragColor = vec4(col, vA);
      }`,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const pulses = new THREE.Points(pulseGeo, pulseMat);
  pulses.frustumCulled = false;
  group.add(pulses);

  /* ---------- HTML 标签 ---------- */
  const labels = NODES.map((n) => {
    const el = document.createElement('div');
    el.className = 'fl';
    el.innerHTML = '<span class="fl-k"></span><span class="fl-v"></span>';
    el.querySelector('.fl-k').textContent = n.key;
    const v = el.querySelector('.fl-v');
    v.textContent = n.value;
    v.style.color = n.color;
    el._v = v;
    if (labelHost) labelHost.appendChild(el);
    return el;
  });

  /* ---------- 布局 ---------- */
  let vertical = false;
  const tmpA = new THREE.Vector3();
  const tmpB = new THREE.Vector3();

  function layout() {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    const aspect = w / h;
    camera.aspect = aspect;
    camera.updateProjectionMatrix();   // 必须：否则投影矩阵会一直用初始 aspect

    const tan = Math.tan((camera.fov * Math.PI) / 360);
    const needW = SPAN_H * 2 + 1.8;

    // 可视高度固定时能容纳的宽度不够 → 改用竖向链路
    vertical = aspect < needW / MIN_H;

    nodes.forEach((n, i) => {
      const f = i / (NODES.length - 1) - 0.5;      // -0.5 … 0.5
      if (vertical) n.g.position.set(0, -f * SPAN_V * 2, 0);
      else n.g.position.set(f * SPAN_H * 2, 0, 0);
    });

    const lp = linkGeo.attributes.position.array;
    for (let i = 0; i < NODES.length - 1; i++) {
      const a = nodes[i].g.position, b = nodes[i + 1].g.position;
      lp[i * 6] = a.x; lp[i * 6 + 1] = a.y; lp[i * 6 + 2] = a.z;
      lp[i * 6 + 3] = b.x; lp[i * 6 + 4] = b.y; lp[i * 6 + 5] = b.z;
    }
    linkGeo.attributes.position.needsUpdate = true;

    // 相机距离：横向同时满足「链路横向铺开」与「最小可视高度」
    const z = vertical
      ? ((SPAN_V * 2 + 1.5) / 2) / tan
      : Math.max((needW / 2) / (tan * aspect), (MIN_H / 2) / tan);
    camera.position.set(0, 0, z);
    camera.lookAt(0, 0, 0);
    pulseMat.uniforms.uRef.value = z;

    // 竖向：整体左移，给右侧标签腾地方；横向：整体上移，给下方标签腾地方
    group.position.set(vertical ? -0.45 : 0, vertical ? 0 : 0.3, 0);

    labels.forEach((el, i) => {
      el._v.textContent = vertical ? NODES[i].short : NODES[i].value;
      if (vertical) {
        el.style.transform = 'translate(0, -50%)';
        el.style.textAlign = 'left';
        el.style.alignItems = 'flex-start';
        el.style.whiteSpace = 'normal';
      } else {
        el.style.transform = 'translate(-50%, 0)';
        el.style.textAlign = 'center';
        el.style.alignItems = 'center';
        el.style.whiteSpace = 'nowrap';
        el.style.maxWidth = 'none';
      }
    });
  }

  /* ---------- 渲染 ---------- */
  let elapsed = 0;
  let active = true;
  const tmpC = new THREE.Color();

  /* 标签定位：每帧调用，也在 resize / 重新激活时立刻调一次，
     避免场景暂停期间标签停在未定位的 (0,0)、滚入视口时先闪一下再归位。 */
  function placeLabels() {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    nodes.forEach((n, i) => {
      tmpA.copy(n.g.position).applyMatrix4(group.matrixWorld).project(camera);
      const x = (tmpA.x * 0.5 + 0.5) * w;
      const y = (-tmpA.y * 0.5 + 0.5) * h;

      // 圆环边缘上的一点 → 换算成屏幕像素，让标签让开圆环本身
      tmpB.copy(n.g.position);
      if (vertical) tmpB.x += RING_R + 0.06;
      else tmpB.y -= RING_R + 0.06;
      tmpB.applyMatrix4(group.matrixWorld).project(camera);
      const ex = (tmpB.x * 0.5 + 0.5) * w;
      const ey = (-tmpB.y * 0.5 + 0.5) * h;

      const el = labels[i];
      if (vertical) {
        const left = Math.round(clamp(ex + 12, 12, w - 40));
        el.style.left = `${left}px`;
        el.style.top = `${Math.round(clamp(y, 26, h - 26))}px`;
        el.style.maxWidth = `${Math.max(96, Math.round(w - left - 14))}px`;
      } else {
        // 交错两行，四个标签永不互相压到
        const row = i % 2 ? 36 : 0;
        el.style.left = `${Math.round(clamp(x, 70, w - 70))}px`;
        el.style.top = `${Math.round(clamp(ey + 12 + row, 0, h - 52))}px`;
      }
      el.classList.add('on');
    });
  }

  function update(dt) {
    if (!active || dt <= 0) return;
    elapsed += dt;

    const t = reduced ? 0.34 : elapsed;
    const speed = reduced ? 0 : 0.17;

    // 光点沿链路前进
    for (let i = 0; i < PULSES; i++) {
      pProg[i] += dt * speed;
      if (pProg[i] > 1) pProg[i] -= 1;
      const p = pProg[i];

      // 首尾淡入淡出，避免循环时突然跳回起点
      pAlpha[i] = smoothstep(0, 0.07, p) * (1 - smoothstep(0.93, 1, p));

      const f = p * (NODES.length - 1);                 // 0 … 3
      const i0 = Math.min(NODES.length - 2, Math.floor(f));
      const k = f - i0;
      const a = nodes[i0].g.position;
      const b = nodes[i0 + 1].g.position;
      pPos[i * 3] = a.x + (b.x - a.x) * k;
      pPos[i * 3 + 1] = a.y + (b.y - a.y) * k;
      pPos[i * 3 + 2] = a.z + (b.z - a.z) * k;

      tmpC.copy(pRamp[i0]).lerp(pRamp[i0 + 1], k);
      pCol[i * 3] = tmpC.r; pCol[i * 3 + 1] = tmpC.g; pCol[i * 3 + 2] = tmpC.b;
    }
    pulseGeo.attributes.position.needsUpdate = true;
    pulseGeo.attributes.aColor.needsUpdate = true;
    pulseGeo.attributes.aAlpha.needsUpdate = true;

    // 节点被光点经过时点亮
    nodes.forEach((n, i) => {
      const at = i / (NODES.length - 1);
      let boost = 0;
      for (let p = 0; p < PULSES; p++) {
        const d = Math.abs(pProg[p] - at);
        boost = Math.max(boost, 1 - Math.min(d, 1 - d) / 0.09);
      }
      boost = clamp(boost, 0, 1);
      const s = 1 + boost * 0.18 + (reduced ? 0 : Math.sin(t * 1.2 + i) * 0.015);
      n.g.scale.setScalar(damp(n.g.scale.x, s, 8, dt));
      n.ring.material.opacity = 0.5 + boost * 0.5;
      n.glow.material.opacity = 0.34 + boost * 0.4;
      n.core.material.opacity = 0.75 + boost * 0.25;
    });

    // 缓慢摆动，制造纵深
    group.rotation.y = -0.12 + (reduced ? 0 : Math.sin(elapsed * 0.22) * 0.06);
    group.rotation.x = 0.1 + (reduced ? 0 : Math.cos(elapsed * 0.17) * 0.04);

    renderer.render(scene, camera);

    // 标签跟随投影
    placeLabels();
  }

  function resize() {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    renderer.setSize(w, h, false);
    layout();
    group.updateMatrixWorld(true);
    placeLabels();
  }

  resize();

  return {
    setActive(v) {
      active = v;
      if (v) { group.updateMatrixWorld(true); placeLabels(); }
    },
    update,
    resize,
    dispose() {
      active = false;
      scene.clear();
      ringGeo.dispose(); coreGeo.dispose();
      linkGeo.dispose(); pulseGeo.dispose();
      pulseMat.dispose(); linkMat.dispose(); glowTex.dispose();
      nodes.forEach((n) => { n.glowMat.dispose(); n.ringMat.dispose(); n.coreMat.dispose(); });
      labels.forEach((el) => el.remove());
      renderer.dispose();
    },
  };
}
