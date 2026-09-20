/* ============================================================
   万物智能 WUWU® — UI
   ------------------------------------------------------------
   预加载 / 章节主题色 / 导航 / 标签页 / 复制 / 迷你灯阵 /
   自定义光标 / 两个 three.js 场景的调度（一个主循环驱动）
   ============================================================ */

import { initLedPanel } from './led-panel.js';
import { initFlow } from './flow.js';

const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const damp = (a, b, l, dt) => a + (b - a) * (1 - Math.exp(-l * dt));
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const finePointer = matchMedia('(pointer: fine)').matches;

history.scrollRestoration = 'manual';
window.scrollTo(0, 0);

/* ── 时钟 ──────────────────────────────────────────────────── */

const clockEl = $('#clock');
const fmt = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
});
const tickClock = () => { if (clockEl) clockEl.textContent = fmt.format(new Date()); };
tickClock();
setInterval(tickClock, 1000);

/* ── 迷你 8×8 灯阵（工作流卡片） ───────────────────────────── */

$$('.led-mini').forEach((box) => {
  const frag = document.createDocumentFragment();
  for (let i = 0; i < 64; i++) {
    const dot = document.createElement('i');
    const r = Math.floor(i / 8);
    const c = i % 8;
    dot.style.setProperty('--i', i);
    dot.style.setProperty('--r', r);
    dot.style.setProperty('--c', c);
    dot.style.setProperty('--d', (Math.random() * 2).toFixed(2) + 's');
    frag.appendChild(dot);
  }
  box.appendChild(frag);
});

/* ── 跑马灯（复制一份实现无缝循环） ─────────────────────────── */

const marqueeGroup = $('#marqueeGroup');
if (marqueeGroup) marqueeGroup.parentElement.appendChild(marqueeGroup.cloneNode(true));

/* ── 滚动揭示 ─────────────────────────────────────────────── */

const io = new IntersectionObserver((entries) => {
  for (const en of entries) {
    if (en.isIntersecting) { en.target.classList.add('in-view'); io.unobserve(en.target); }
  }
}, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
$$('[data-reveal]').forEach((el) => io.observe(el));

// 兜底：万一观察器不工作，别让内容永远停在透明状态
setTimeout(() => {
  $$('[data-reveal]:not(.in-view)').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.top < window.innerHeight) el.classList.add('in-view');
  });
}, 4000);

/* ── 章节：主题色 + 导航高亮 ───────────────────────────────── */

const sections = $$('[data-sec]');
let tops = [];
const measure = () => {
  tops = sections.map((s) => s.offsetTop);
  scrollMax = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
};
let scrollMax = 1;

const navLinks = $$('.site-nav a');
const sideBtns = $$('.side-index button');
let activeIdx = -1;
let lastAcc = '';

function setActive(i) {
  if (i === activeIdx) return;
  activeIdx = i;
  navLinks.forEach((a, k) => a.classList.toggle('active', k === i));
  sideBtns.forEach((b, k) => b.classList.toggle('active', k === i));
  const acc = sections[i] && sections[i].dataset.acc;
  if (acc && acc !== lastAcc) {
    lastAcc = acc;
    document.documentElement.style.setProperty('--acc', acc);
  }
}

/* ── 导航跳转 ─────────────────────────────────────────────── */

const menu = $('#menu');
const burger = $('#burger');
const closeMenu = () => {
  document.body.classList.remove('menu-open');
  document.body.style.overflow = '';
  if (burger) burger.setAttribute('aria-expanded', 'false');
  if (menu) menu.setAttribute('aria-hidden', 'true');
};

if (burger) {
  burger.addEventListener('click', () => {
    const open = document.body.classList.toggle('menu-open');
    document.body.style.overflow = open ? 'hidden' : '';
    burger.setAttribute('aria-expanded', String(open));
    menu.setAttribute('aria-hidden', String(!open));
  });
}

$$('[data-target]').forEach((el) => {
  el.addEventListener('click', (e) => {
    e.preventDefault();
    const i = parseInt(el.dataset.target, 10);
    const target = sections[i];
    if (!target) return;
    closeMenu();
    window.scrollTo({ top: target.offsetTop, behavior: reduced ? 'auto' : 'smooth' });
  });
});

window.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });

/* ── 标签页 ───────────────────────────────────────────────── */

const tabs = $$('.tab');
const panels = $$('.panel');
tabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    tabs.forEach((t) => {
      const on = t === tab;
      t.classList.toggle('is-on', on);
      t.setAttribute('aria-selected', String(on));
    });
    panels.forEach((p) => p.classList.toggle('is-on', p.dataset.panel === tab.dataset.tab));
  });
});

/* ── 复制 ─────────────────────────────────────────────────── */

$$('.copy').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const src = $('#code-' + btn.dataset.copy);
    if (!src) return;
    const text = src.textContent;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch { /* noop */ }
      ta.remove();
    }
    const prev = btn.textContent;
    btn.textContent = '已复制';
    btn.classList.add('done');
    setTimeout(() => { btn.textContent = prev; btn.classList.remove('done'); }, 1600);
  });
});

/* ── 自定义光标 ───────────────────────────────────────────── */

const dotEl = $('.c-dot');
const ringEl = $('.c-ring');
const cur = { x: innerWidth / 2, y: innerHeight / 2, dx: 0, dy: 0, rx: 0, ry: 0, on: false };

if (finePointer && !reduced) {
  window.addEventListener('pointermove', (e) => {
    cur.x = e.clientX; cur.y = e.clientY;
    if (!cur.on) {
      cur.on = true;
      cur.dx = cur.rx = cur.x;
      cur.dy = cur.ry = cur.y;
      document.body.classList.add('cursor-on');
    }
  });
  document.addEventListener('mouseover', (e) => {
    document.body.dataset.cursor = e.target.closest('a, button, [data-hover]') ? 'hover' : '';
  });
}

/* ── three.js 场景 ────────────────────────────────────────── */

const ledCanvas = $('#led');
const flowCanvas = $('#flow');

const ledPanel = initLedPanel(ledCanvas, {
  onPattern(i, p) {
    const nameEl = $('#ledPattern');
    if (nameEl) nameEl.textContent = `PATTERN ${String(i + 1).padStart(2, '0')} — ${p.name}`;
    $$('#ledDots button').forEach((b, k) => b.classList.toggle('on', k === i));
  },
});

const flow = initFlow(flowCanvas, $('#flowLabels'));

// 灯板效果切换按钮
if (ledPanel) {
  const dotsHost = $('#ledDots');
  if (dotsHost) {
    ledPanel.patterns.forEach((p, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('role', 'tab');
      b.title = p.cn;
      b.setAttribute('aria-label', p.cn);
      b.addEventListener('click', () => ledPanel.setPattern(i));
      dotsHost.appendChild(b);
    });
    dotsHost.addEventListener('mouseover', (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      const k = [...dotsHost.children].indexOf(b);
      if (k >= 0) $('#ledPattern').textContent =
        `PATTERN ${String(k + 1).padStart(2, '0')} — ${ledPanel.patterns[k].name}`;
    });
    dotsHost.addEventListener('mouseleave', () => {
      const p = ledPanel.patterns[ledPanel.index];
      $('#ledPattern').textContent =
        `PATTERN ${String(ledPanel.index + 1).padStart(2, '0')} — ${p.name}`;
    });
  }
  const nextBtn = $('#ledNext');
  if (nextBtn) nextBtn.addEventListener('click', () => ledPanel.next());
  ledPanel.setPattern(0);
}

// 离屏时暂停，省电也省风扇
const visObs = new IntersectionObserver((entries) => {
  for (const en of entries) {
    const on = en.isIntersecting;
    if (en.target === ledCanvas && ledPanel) ledPanel.setActive(on);
    if (en.target === flowCanvas && flow) flow.setActive(on);
  }
}, { threshold: 0.01 });
if (ledCanvas) visObs.observe(ledCanvas);
if (flowCanvas) visObs.observe(flowCanvas);

/* ── 预加载 ───────────────────────────────────────────────── */

const preCount = $('#preCount');
const preBar = $('#preBar');
const preGrid = $('#preGrid');
const LOAD_MS = reduced ? 200 : 1000;
const loadStart = performance.now();
let gridDots = [];

if (preGrid) {
  const frag = document.createDocumentFragment();
  for (let i = 0; i < 64; i++) {
    const d = document.createElement('i');
    frag.appendChild(d);
  }
  preGrid.appendChild(frag);
  gridDots = [...preGrid.children];
}

function loaderTick(now) {
  const p = clamp((now - loadStart) / LOAD_MS, 0, 1);
  const eased = 1 - Math.pow(1 - p, 3);
  if (preCount) preCount.textContent = String(Math.floor(eased * 100)).padStart(2, '0');
  if (preBar) preBar.style.transform = `scaleX(${eased})`;

  const lit = Math.floor(eased * 64);
  for (let i = 0; i < gridDots.length; i++) {
    const row = Math.floor(i / 8);
    const k = row % 2 ? row * 8 + (7 - (i % 8)) : i;   // 蛇形点亮，和 CHASE 效果一致
    gridDots[i].classList.toggle('on', k < lit);
  }

  if (p < 1) { requestAnimationFrame(loaderTick); return; }

  Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 1100))]).then(() => {
    document.body.classList.add('is-loaded');
    measure();
    requestAnimationFrame(() => {
      ledPanel && ledPanel.resize();
      flow && flow.resize();
    });
  });
}
requestAnimationFrame(loaderTick);

/* ── 主循环 ───────────────────────────────────────────────── */

const scrollBar = $('#scrollBar');
let last = performance.now();
let rafId = 0;

function frame(now) {
  rafId = requestAnimationFrame(frame);
  const dt = Math.min((now - last) / 1000, 0.05);
  last = now;

  const y = window.scrollY;

  // 进度条
  if (scrollBar) scrollBar.style.transform = `scaleX(${clamp(y / scrollMax, 0, 1)})`;

  // 当前章节
  const probe = y + window.innerHeight * 0.42;
  let idx = 0;
  for (let i = 0; i < sections.length; i++) if (probe >= tops[i]) idx = i;
  setActive(idx);

  // 光标
  if (cur.on) {
    cur.dx = damp(cur.dx, cur.x, 30, dt);
    cur.dy = damp(cur.dy, cur.y, 30, dt);
    cur.rx = damp(cur.rx, cur.x, 13, dt);
    cur.ry = damp(cur.ry, cur.y, 13, dt);
    dotEl.style.transform = `translate(${cur.dx - 3}px, ${cur.dy - 3}px)`;
    ringEl.style.transform = `translate(${cur.rx}px, ${cur.ry}px) translate(-50%, -50%)`;
  }

  if (ledPanel) ledPanel.update(dt);
  if (flow) flow.update(dt);
}
rafId = requestAnimationFrame(frame);

document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    cancelAnimationFrame(rafId);
  } else {
    last = performance.now();
    rafId = requestAnimationFrame(frame);
  }
});

/* ── resize ───────────────────────────────────────────────── */

let resizeT = 0;
window.addEventListener('resize', () => {
  clearTimeout(resizeT);
  resizeT = setTimeout(() => {
    measure();
    ledPanel && ledPanel.resize();
    flow && flow.resize();
  }, 140);
});

measure();
