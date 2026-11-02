import { PATTERNS, parseDemoCommand, patternCommand, brightnessCommand, samplePixel } from './demo-model.js';

export function initDemo() {
  const $ = selector => document.querySelector(selector);
  const canvas = $('#led');
  if (!canvas) return;
  const stage = canvas.parentElement;
  const fallbackDots = [...document.querySelectorAll('#ledFallback i')];
  const flowCanvas = $('#flow');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const state = { pattern: 0, color: [1, 0, 0], brightness: 200, playing: true, autoplay: true };
  let ledPanel = null, flow = null, flowLoading = false;
  let ledVisible = true, flowVisible = false;
  let elapsed = 0, held = 0, last = performance.now(), frameId = 0, dirty = true, lastFallback = 0;
  const buttons = [];

  /* ── 反馈小组件：class 重触发动画 + 模拟收发指示 + 错误建议 ──
     reduced-motion 下不挂动画 class（CSS 全局也会压成 0.01ms，双保险），
     但文字内容照常更新 —— 信息不缺席，只是不动。 */

  function replayClass(el, cls) {
    if (motion.matches) return;
    el.classList.remove(cls);
    void el.offsetWidth;               // 强制回流，让同名 class 重新触发动画
    el.classList.add(cls);
  }

  /* 文字变化才播微入场；同文重设（如同步滑杆）不闪 */
  function swapText(el, text) {
    if (el.textContent === text) return;
    el.textContent = text;
    replayClass(el, 'swap');
  }

  const linkBox = $('#demoLink');
  const linkText = $('#demoLinkText');
  function pingLink(result) {
    if (!linkBox) return;
    // 「会发出」的字节数取自真实 payload 序列化，不是编的；全程标注模拟
    const bytes = new TextEncoder().encode(JSON.stringify(result.payload)).length;
    linkText.textContent = `TX ${bytes}B → RX ok · 模拟`;
    replayClass(linkBox, 'ping');
  }

  const suggest = $('#demoSuggest');
  function showSuggestions(show) {
    if (!suggest) return;
    if (!show) { suggest.hidden = true; return; }
    suggest.textContent = '';
    const label = document.createElement('span');
    label.textContent = '试试：';
    suggest.appendChild(label);
    ['设成蓝色', '显示爱心', '亮度120'].forEach(text => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = text;
      // 与上方示例指令的可访问名区分开，避免同名按钮歧义
      button.setAttribute('aria-label', `填入并预览：${text}`);
      button.addEventListener('click', () => {
        $('#demoCommand').value = text;
        applyCommand(parseDemoCommand(text, state.brightness));
      });
      suggest.appendChild(button);
    });
    suggest.hidden = false;
  }

  /* 快捷键：「/」从页面任意处聚焦指令输入（GitHub 风格），输入框里 Esc 退出。
     不抢输入控件、组合键和移动菜单打开时的按键。 */
  document.addEventListener('keydown', event => {
    if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
    if (document.body.classList.contains('menu-open')) return;
    const target = event.target;
    if (target && target.closest('input, textarea, select, [contenteditable]')) return;
    const input = $('#demoCommand');
    event.preventDefault();
    input.focus();
    input.select();
  });
  $('#demoCommand').addEventListener('keydown', event => {
    if (event.key === 'Escape') event.target.blur();
  });

  function requestFrame() {
    if (!frameId && !document.hidden) frameId = requestAnimationFrame(frame);
  }
  function invalidate() { dirty = true; requestFrame(); }

  function syncState() {
    const reduced = motion.matches;
    document.body.classList.toggle('motion-paused', !state.playing || reduced);
    swapText($('#ledPattern'), `${PATTERNS[state.pattern].cn} / ${PATTERNS[state.pattern].name}`);
    buttons.forEach((button, index) => {
      button.classList.toggle('on', index === state.pattern);
      button.setAttribute('aria-pressed', String(index === state.pattern));
    });
    $('#demoBrightness').value = String(state.brightness);
    $('#brightnessValue').textContent = `${state.brightness} / 255`;
    $('#demoPause').textContent = reduced ? '已减少动态效果' : state.playing ? '暂停动画' : '继续动画';
    $('#demoPause').disabled = reduced;
    $('#demoPause').setAttribute('aria-pressed', String(!state.playing));
    $('#demoAuto').setAttribute('aria-pressed', String(state.autoplay));
    $('#demoAuto').disabled = reduced;
    if (ledPanel) {
      ledPanel.setPattern(state.pattern);
      ledPanel.setColor(state.color);
      ledPanel.setBrightness(state.brightness);
      ledPanel.setPlaying(state.playing);
      ledPanel.setReducedMotion(reduced);
    }
    flow?.setReducedMotion(reduced || !state.playing);
    invalidate();
  }

  function applyCommand(result, manual = true) {
    const input = $('#demoCommand');
    const status = $('#demoStatus');
    input.setAttribute('aria-invalid', String(!result.ok));
    if (!result.ok) {
      swapText(status, result.message);
      status.classList.add('is-error');
      replayClass(input, 'shake');
      showSuggestions(true);
      return;
    }
    status.classList.remove('is-error');
    showSuggestions(false);
    if (manual) {
      state.autoplay = false;
      swapText(status, `${result.message}。仅作用于此页面。`);
      pingLink(result);
    }
    for (const key of ['pattern', 'color', 'brightness']) {
      if (result[key] !== undefined) state[key] = result[key];
    }
    held = 0;
    $('#code-demo').textContent = result.command;
    $('#demoPayload').textContent = JSON.stringify(result.payload, null, 2);
    syncState();
  }

  PATTERNS.forEach((pattern, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = pattern.cn;
    button.setAttribute('aria-label', `预览${pattern.cn}效果`);
    button.addEventListener('click', () => applyCommand(patternCommand(index)));
    buttons.push(button);
    $('#ledDots').appendChild(button);
  });
  const next = () => applyCommand(patternCommand((state.pattern + 1) % PATTERNS.length));
  canvas.addEventListener('click', next);
  $('#ledNext').addEventListener('click', next);
  $('#demoForm').addEventListener('submit', event => {
    event.preventDefault();
    applyCommand(parseDemoCommand($('#demoCommand').value, state.brightness));
  });
  document.querySelectorAll('[data-demo-command]').forEach(button => {
    button.addEventListener('click', () => {
      $('#demoCommand').value = button.dataset.demoCommand;
      applyCommand(parseDemoCommand(button.dataset.demoCommand, state.brightness));
    });
  });
  $('#demoBrightness').addEventListener('input', event => applyCommand(brightnessCommand(Number(event.target.value))));
  $('#demoPause').addEventListener('click', () => { state.playing = !state.playing; syncState(); });
  $('#demoAuto').addEventListener('click', () => { state.autoplay = !state.autoplay; held = 0; syncState(); });
  motion.addEventListener('change', syncState);

  function renderFallback(time) {
    fallbackDots.forEach((dot, i) => {
      const rgb = samplePixel(state, i % 8, Math.floor(i / 8), time).map(v => Math.round(v * 255));
      dot.style.setProperty('--led-color', `rgb(${rgb.join(' ')})`);
    });
  }

  function frame(now) {
    frameId = 0;
    if (document.hidden) return;
    const dt = Math.max(.001, Math.min((now - last) / 1000, .05));
    last = now;
    const animate = state.playing && !motion.matches;
    if (animate && ledVisible) {
      elapsed += dt;
      held += dt;
      if (state.autoplay && held >= 3.4) applyCommand(patternCommand((state.pattern + 1) % PATTERNS.length), false);
    }
    if (ledVisible) {
      if (ledPanel) ledPanel.update(dt);
      else if (dirty || now - lastFallback >= 33) {
        renderFallback(motion.matches ? .6 : elapsed);
        lastFallback = now;
      }
    }
    if (flowVisible && flow) flow.update(dt);
    dirty = false;
    if (animate && (ledVisible || (flowVisible && flow))) requestFrame();
  }

  async function loadLed() {
    try {
      const { initLedPanel } = await import('./led-panel.js');
      ledPanel = initLedPanel(canvas);
      if (ledPanel) {
        stage.classList.add('has-webgl');
        $('#demoRenderer').textContent = '3D 预览 · 浏览器模拟';
        ledPanel.setActive(ledVisible);
        syncState();
      }
    } catch {
      // The fully working DOM preview remains available if a module cannot load.
    }
  }

  async function loadFlow() {
    if (flowLoading || !flowCanvas) return;
    flowLoading = true;
    try {
      const { initFlow } = await import('./flow.js');
      flow = initFlow(flowCanvas, $('#flowLabels'));
      if (flow) {
        flowCanvas.parentElement.classList.add('has-webgl');
        flow.setActive(flowVisible);
        flow.setReducedMotion(motion.matches || !state.playing);
        invalidate();
      }
    } catch {
      // A semantic HTML signal flow is always present underneath the canvas.
    }
  }

  let visibility;
  if ('IntersectionObserver' in window) {
    visibility = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.target === canvas) {
          ledVisible = entry.isIntersecting;
          ledPanel?.setActive(ledVisible);
        }
        if (entry.target === flowCanvas) {
          flowVisible = entry.isIntersecting;
          flow?.setActive(flowVisible);
          if (flowVisible) loadFlow();
        }
      });
      invalidate();
    }, { threshold: .01 });
    visibility.observe(canvas);
    if (flowCanvas) visibility.observe(flowCanvas);
  } else {
    flowVisible = true;
    loadFlow();
  }

  canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault();
    ledPanel?.dispose();
    ledPanel = null;
    stage.classList.remove('has-webgl');
    $('#demoRenderer').textContent = '2D 预览 · 浏览器模拟';
    invalidate();
  });
  flowCanvas?.addEventListener('webglcontextlost', event => {
    event.preventDefault();
    flow?.dispose();
    flow = null;
    flowCanvas.parentElement.classList.remove('has-webgl');
  });
  document.addEventListener('visibilitychange', () => {
    document.body.classList.toggle('page-hidden', document.hidden);
    if (document.hidden) { cancelAnimationFrame(frameId); frameId = 0; }
    else { last = performance.now(); invalidate(); }
  });
  const resize = () => { ledPanel?.resize(); flow?.resize(); invalidate(); };
  addEventListener('resize', resize);
  document.fonts?.ready.then(resize);
  addEventListener('pagehide', event => {
    cancelAnimationFrame(frameId);
    frameId = 0;
    if (!event.persisted) { visibility?.disconnect(); ledPanel?.dispose(); flow?.dispose(); }
  });
  addEventListener('pageshow', () => { last = performance.now(); invalidate(); });

  applyCommand(patternCommand(0), false);
  if ('requestIdleCallback' in window) requestIdleCallback(loadLed, { timeout: 1000 });
  else setTimeout(loadLed, 0);
}
