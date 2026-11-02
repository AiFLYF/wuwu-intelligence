/* Navigation and progressive enhancement. UI never waits for WebGL. */
import { initDemo } from './demo-controller.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const motion = matchMedia('(prefers-reduced-motion: reduce)');

/* 告诉 index.html 的兜底脚本「模块已经跑起来了」——从这一刻起幕布只听这里的。
   注意：html.js 由 <head> 里那段同步挂上（首帧就盖幕布，不会先闪正文），
   所以这里不再重复挂。
   如果 head 的兜底已经把 .js 摘掉（app.js 加载被判超时），页面已退回静态态，
   别再挂幕布、别再放动画。 */
window.__wuwuBoot = true;
const booted = document.documentElement.classList.contains('js');

/* 兜底：动画本该自己停，但万一中途卡住，1.8s 后无论如何都摘幕布。
   旧版这个上限是 50s，慢网络下用户要对着幕布干等。 */
setTimeout(() => document.body.classList.add('is-loaded'), 1800);

const clock = $('#clock');
const timeFormat = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
function tickClock() {
  if (clock && !document.hidden) clock.textContent = timeFormat.format(new Date());
}
tickClock();
setInterval(tickClock, 1000);

/* 刷新后别停在半路；但带 #锚点 分享出去的链接要尊重锚点 */
history.scrollRestoration = 'manual';
const hashEl = location.hash.length > 1 ? document.getElementById(location.hash.slice(1)) : null;
if (!hashEl) scrollTo(0, 0);

$$('.led-mini').forEach(box => {
  const fragment = document.createDocumentFragment();
  for (let i = 0; i < 64; i++) {
    const dot = document.createElement('i');
    dot.style.setProperty('--i', i);
    dot.style.setProperty('--r', Math.floor(i / 8));
    dot.style.setProperty('--c', i % 8);
    dot.style.setProperty('--d', `${(i * .137 % 2).toFixed(2)}s`);
    fragment.appendChild(dot);
  }
  box.appendChild(fragment);
});
const marquee = $('#marqueeGroup');
if (marquee) {
  const clone = marquee.cloneNode(true);
  clone.removeAttribute('id');
  marquee.parentElement.appendChild(clone);
}

if ('IntersectionObserver' in window) {
  const reveal = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        reveal.unobserve(entry.target);
      }
    });
  }, { threshold: .08 });
  $$('[data-reveal]').forEach(element => reveal.observe(element));
  // 兜底：观察器在某些环境里就是不上报，别让内容永远停在透明状态
  setTimeout(() => {
    $$('[data-reveal]:not(.in-view)').forEach(element => {
      if (element.getBoundingClientRect().top < innerHeight) element.classList.add('in-view');
    });
  }, 4000);
} else {
  $$('[data-reveal]').forEach(element => element.classList.add('in-view'));
}

const sections = $$('[data-sec]');
const navLinks = $$('.site-nav a');
const sideButtons = $$('.side-index button');
let tops = [], scrollMax = 1, scrollFrame = 0;
function measure() {
  tops = sections.map(section => section.offsetTop);
  scrollMax = Math.max(1, document.documentElement.scrollHeight - innerHeight);
  scheduleScroll();
}
function updateScroll() {
  scrollFrame = 0;
  const probe = scrollY + innerHeight * .42;
  let active = 0;
  tops.forEach((top, i) => { if (probe >= top) active = i; });
  [navLinks, sideButtons].forEach(links => links.forEach((link, i) => {
    link.classList.toggle('active', i === active);
    if (i === active) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  }));
  document.documentElement.style.setProperty('--acc', sections[active]?.dataset.acc || '#FF4B3E');
  const bar = $('#scrollBar');
  if (bar) bar.style.transform = `scaleX(${Math.min(1, Math.max(0, scrollY / scrollMax))})`;
}
function scheduleScroll() {
  if (!scrollFrame) scrollFrame = requestAnimationFrame(updateScroll);
}
addEventListener('scroll', scheduleScroll, { passive: true });
addEventListener('resize', measure);
document.fonts?.ready.then(measure);
if ('ResizeObserver' in window) new ResizeObserver(measure).observe(document.body);

const menu = $('#menu');
const burger = $('#burger');
function closeMenu(restoreFocus = true) {
  const wasOpen = document.body.classList.contains('menu-open');
  document.body.classList.remove('menu-open');
  document.body.style.overflow = '';
  burger?.setAttribute('aria-expanded', 'false');
  burger?.setAttribute('aria-label', '打开菜单');
  if (menu) { menu.inert = true; menu.setAttribute('aria-hidden', 'true'); }
  $('#content').inert = false;
  if (wasOpen && restoreFocus) burger?.focus();
}
burger?.addEventListener('click', () => {
  if (document.body.classList.contains('menu-open')) { closeMenu(); return; }
  document.body.classList.add('menu-open');
  document.body.style.overflow = 'hidden';
  burger.setAttribute('aria-expanded', 'true');
  burger.setAttribute('aria-label', '关闭菜单');
  menu.inert = false;
  menu.setAttribute('aria-hidden', 'false');
  $('#content').inert = true;
  $('a', menu)?.focus();
});
addEventListener('keydown', event => {
  if (!document.body.classList.contains('menu-open')) return;
  if (event.key === 'Escape') { event.preventDefault(); closeMenu(); }
  if (event.key === 'Tab') {
    const focusable = [...$$('a', menu), burger];
    const index = focusable.indexOf(document.activeElement);
    event.preventDefault();
    focusable[(index + (event.shiftKey ? -1 : 1) + focusable.length) % focusable.length].focus();
  }
});
addEventListener('resize', () => { if (innerWidth > 1080) closeMenu(false); });
$$('[data-target]').forEach(link => link.addEventListener('click', event => {
  const target = sections[Number(link.dataset.target)];
  if (!target) return;
  event.preventDefault();
  closeMenu(false);
  if (location.hash !== `#${target.id}`) history.pushState(null, '', `#${target.id}`);
  target.tabIndex = -1;
  target.focus({ preventScroll: true });
  target.scrollIntoView({ behavior: motion.matches ? 'auto' : 'smooth' });
}));

$$('[role="tablist"]').forEach(tablist => {
  const tabs = $$('[role="tab"]', tablist);
  function selectTab(selected) {
    tabs.forEach(tab => {
      const on = tab === selected;
      tab.classList.toggle('is-on', on);
      tab.setAttribute('aria-selected', String(on));
      tab.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(tab.getAttribute('aria-controls'));
      panel.hidden = !on;
      panel.classList.toggle('is-on', on);
    });
    measure();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectTab(tab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      tabs[next].focus();
      selectTab(tabs[next]);
    });
  });
  selectTab(tabs.find(tab => tab.classList.contains('is-on')) || tabs[0]);
});

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.cssText = 'position:fixed;opacity:0;left:0;top:0';
    document.body.appendChild(textarea);
    const previous = document.activeElement;
    textarea.select();
    let copied = false;
    try { copied = document.execCommand('copy'); } catch { /* Manual selection remains available. */ }
    textarea.remove();
    previous?.focus({ preventScroll: true });
    return copied;
  }
}
$$('.copy').forEach(button => {
  const original = button.textContent;
  let timer;
  button.addEventListener('click', async () => {
    const source = document.getElementById(`code-${button.dataset.copy}`);
    if (!source) return;
    const clone = source.cloneNode(true);
    clone.querySelectorAll('.p').forEach(prompt => prompt.remove());
    const copied = await copyText(clone.textContent.trim());
    clearTimeout(timer);
    button.textContent = copied ? '已复制' : '复制失败，请手动选择';
    button.classList.toggle('done', copied);
    $('#copyStatus').textContent = copied ? '已复制到剪贴板' : '复制失败，请手动选择命令文字';
    timer = setTimeout(() => { button.textContent = original; button.classList.remove('done'); }, 2000);
  });
});

/* ── 开场幕布 ──────────────────────────────────────────────────
   动画本体在 index.html 的内联脚本里：一道亮带先循环扫（等待期板子是活的），
   这里只管发信号让它改成「单向扫 + 锁定」，计数与进度条由它同步推进。
   好处是等待期和就绪后是同一条动画，不会有 CSS→JS 交接时的齐刷刷跳变。
   刻意不等 three.js：灯板在 demo-controller 里懒加载，幕布绝不阻塞可读内容。 */

function finishLoad() {
  document.body.classList.add('is-loaded');
  measure();
  // 字体就位会改变文字高度，锚点位置在加载后再校正一次
  if (hashEl) requestAnimationFrame(() => hashEl.scrollIntoView({ behavior: 'auto', block: 'start' }));
}

// 降级态（head 兜底已摘掉 .js）或「减少动态效果」时不挂幕布、不放动画：
// CSS 里 #preloader 在这两种情况下都是 display:none，直接进就绪态即可。
if (!booted || motion.matches) finishLoad();
else if (typeof window.__preloaderRun === 'function') window.__preloaderRun(finishLoad);
else finishLoad();   // 内联脚本没跑到（极端情况），别把幕布挂在那儿

/* ── 自定义光标 ────────────────────────────────────────────────
   细指针且未开启「减少动态效果」时才启用；灯芯紧跟、外环阻尼滞后。
   指针停稳后自动停帧，不常驻一个 rAF。 */

const dotEl = $('.c-dot');
const ringEl = $('.c-ring');
const cursor = { x: 0, y: 0, dx: 0, dy: 0, rx: 0, ry: 0, on: false, last: 0, frame: 0 };

if (dotEl && ringEl && matchMedia('(pointer: fine)').matches && !motion.matches) {
  const damp = (a, b, lambda, dt) => a + (b - a) * (1 - Math.exp(-lambda * dt));
  function cursorTick(now) {
    cursor.frame = 0;
    const dt = Math.min((now - cursor.last) / 1000, 0.05);
    cursor.last = now;
    cursor.dx = damp(cursor.dx, cursor.x, 30, dt);
    cursor.dy = damp(cursor.dy, cursor.y, 30, dt);
    cursor.rx = damp(cursor.rx, cursor.x, 13, dt);
    cursor.ry = damp(cursor.ry, cursor.y, 13, dt);
    dotEl.style.transform = `translate(${cursor.dx - 3}px, ${cursor.dy - 3}px)`;
    ringEl.style.transform = `translate(${cursor.rx}px, ${cursor.ry}px) translate(-50%, -50%)`;
    if (Math.abs(cursor.rx - cursor.x) > 0.2 || Math.abs(cursor.ry - cursor.y) > 0.2) {
      cursor.frame = requestAnimationFrame(cursorTick);
    }
  }
  addEventListener('pointermove', event => {
    cursor.x = event.clientX;
    cursor.y = event.clientY;
    if (!cursor.on) {
      cursor.on = true;
      cursor.dx = cursor.rx = cursor.x;
      cursor.dy = cursor.ry = cursor.y;
      document.body.classList.add('cursor-on');
    }
    if (!cursor.frame) {
      cursor.last = performance.now();
      cursor.frame = requestAnimationFrame(cursorTick);
    }
  }, { passive: true });
  document.addEventListener('mouseover', event => {
    document.body.dataset.cursor = event.target.closest('a, button, [data-hover]') ? 'hover' : '';
  });
}

initDemo();
measure();
