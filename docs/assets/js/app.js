/* Navigation and progressive enhancement. UI never waits for WebGL. */
import { initDemo } from './demo-controller.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const motion = matchMedia('(prefers-reduced-motion: reduce)');

document.documentElement.classList.add('js');
document.body.classList.add('is-loaded');

const clock = $('#clock');
const timeFormat = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
function tickClock() {
  if (clock && !document.hidden) clock.textContent = timeFormat.format(new Date());
}
tickClock();
setInterval(tickClock, 1000);

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

initDemo();
measure();
