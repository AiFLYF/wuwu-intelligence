#!/usr/bin/env python3
"""Run browser regression checks against a private temporary localhost server.

Install requirements-browser.txt and run `python -m playwright install chromium`.
Screenshots are written to .workbuddy/qa/ by default.
"""

import argparse
from datetime import datetime
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from threading import Thread

from playwright.sync_api import expect, sync_playwright
from check_workflow import command_text, example_device, generate_manual

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, _request, _client_address):
        # 浏览器中止 keep-alive 连接（跳到下一页、context 关闭）会让服务端在
        # sendall 时收到 ConnectionAbortedError/ConnectionResetError。这是正常
        # 行为，不是检查结果；默认 handle_error 会把整段堆栈打进 CI 日志。
        if sys.exc_info()[0] not in (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            super().handle_error(_request, _client_address)


def ready(page, url):
    page.goto(url, wait_until='domcontentloaded')
    expect(page.locator('#ledDots button')).to_have_count(7)
    # 开幕布灯阵必须是 64 颗。曾手写 64 个 <i> 漏了 3 个，最后一行右侧 3 颗
    # 在 DOM 里不存在，进度到 100% 也点不亮，而且不报任何错。
    expect(page.locator('#preGrid i')).to_have_count(64)


def check_desktop(browser, url, output):
    context = browser.new_context(viewport={'width': 1440, 'height': 1080})
    page = context.new_page()
    errors, requests = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    ready(page, url)
    assert not any('/flow.js' in request for request in requests), 'Below-fold 3D must load lazily'
    page.get_by_role('button', name='设成蓝色', exact=True).click()
    expect(page.locator('#code-demo')).to_have_text('python pc/led_cli.py color 0 0 255')
    expect(page.locator('#demoAuto')).to_have_attribute('aria-pressed', 'false')
    page.locator('#demoCommand').fill('开门')
    page.locator('#demoForm button[type="submit"]').click()
    expect(page.locator('#demoCommand')).to_have_attribute('aria-invalid', 'true')
    expect(page.locator('#code-demo')).to_have_text('python pc/led_cli.py color 0 0 255')
    # 非法指令的完整反馈链：输入框抖动、给出可点的修正建议
    assert page.evaluate("document.getElementById('demoCommand').classList.contains('shake')")
    expect(page.locator('#demoSuggest')).to_be_visible()
    page.get_by_role('button', name='填入并预览：显示爱心').click()
    expect(page.locator('#code-demo')).to_have_text('python pc/led_cli.py heart')
    expect(page.locator('#demoSuggest')).to_be_hidden()
    # 模拟回环指示：成功命令给出「会发出」的字节数，且始终标注模拟
    expect(page.locator('#demoLinkText')).to_contain_text('TX ')
    assert '模拟' in page.locator('#demoLinkText').text_content()
    # 「/」从任意处聚焦指令输入，Esc 退出（焦点不丢到 body 之外）
    page.keyboard.press('/')
    expect(page.locator('#demoCommand')).to_be_focused()
    page.keyboard.press('Escape')
    assert page.evaluate("document.activeElement.id") != 'demoCommand'
    page.get_by_role('button', name='显示爱心', exact=True).click()
    # 结果一键导出：文件名固定，内容必须是当前命令 + 模拟标注，不能是别的快照
    with page.expect_download() as download_info:
        page.locator('#demoExport').click()
    download = download_info.value
    assert download.suggested_filename == 'wuwu-demo-result.json'
    snapshot = json.loads(Path(download.path()).read_text(encoding='utf-8'))
    assert snapshot['simulated'] is True, snapshot
    assert snapshot['command'] == 'python pc/led_cli.py heart', snapshot
    # 导出件必须能独立复现：ISO 时间戳 + 三步最小步骤，且步骤带上当前命令
    assert snapshot['timestamp'].endswith('Z'), snapshot
    assert datetime.fromisoformat(snapshot['timestamp'].replace('Z', '+00:00')).year >= 2024, snapshot
    assert isinstance(snapshot['steps'], list) and len(snapshot['steps']) == 3, snapshot
    assert 'python pc/led_cli.py heart' in snapshot['steps'][0], snapshot
    # 环境快照：复现时必须能看出 UA / 视口 / 渲染后端
    env = snapshot['environment']
    assert env['userAgent'].startswith('Mozilla/'), snapshot
    assert env['viewport']['width'] > 0 and env['viewport']['height'] > 0, snapshot
    assert env['webgl'] in {'webgl2', 'webgl', '2d'}, snapshot
    assert isinstance(env['reducedMotion'], bool), snapshot
    page.locator('#demoPause').click()
    expect(page.locator('#demoPause')).to_have_text('继续动画')
    page.locator('#demoBrightness').focus()
    page.keyboard.press('Home')
    expect(page.locator('#brightnessValue')).to_have_text('0 / 255')
    page.keyboard.press('End')
    expect(page.locator('#brightnessValue')).to_have_text('255 / 255')
    # Give CSS entrance transitions time to settle before capturing the artifact.
    page.wait_for_timeout(1200)
    page.screenshot(path=str(output / 'desktop.png'))

    page.locator('.site-nav a[href="#install"]').click()
    expect(page).to_have_url(url + '#install')
    page.locator('#tab-manual').focus()
    page.keyboard.press('End')
    expect(page.locator('#tab-verify')).to_be_focused()
    expect(page.locator('#panel-verify')).to_be_visible()
    expect(page.locator('#panel-manual')).to_be_hidden()
    page.keyboard.press('Home')
    expect(page.locator('#tab-manual')).to_be_focused()
    # Stub the clipboard to avoid changing the user's operating-system clipboard.
    page.evaluate("""() => Object.defineProperty(navigator, 'clipboard', {
        configurable: true, value: {writeText: async value => {window.testClipboard = value;}}
    })""")
    copy = page.locator('#panel-manual .copy')
    copy.click()
    expect(copy).to_have_text('已复制')
    assert page.evaluate('window.testClipboard') == 'npx skills add AiFLYF/wuwu-intelligence --skill wuwu-intelligence'
    page.evaluate("""() => {
        navigator.clipboard.writeText = async () => {throw new Error('denied');};
        document.execCommand = () => false;
    }""")
    copy.click()
    expect(copy).to_contain_text('复制失败')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors, errors
    context.close()


def check_mobile(browser, url, output):
    for width in (320, 390, 768):
        context = browser.new_context(viewport={'width': width, 'height': 844},
                                      has_touch=True, reduced_motion='reduce')
        page = context.new_page()
        ready(page, url)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        page.locator('#burger').click()
        expect(page.locator('#menu')).to_have_attribute('aria-hidden', 'false')
        for _ in range(9):
            page.keyboard.press('Tab')
            assert page.evaluate("document.activeElement.closest('#menu') !== null"
                                 " || document.activeElement.id === 'burger'")
        page.keyboard.press('Escape')
        expect(page.locator('#burger')).to_be_focused()
        assert not page.locator('#content').evaluate('(element) => element.inert')
        if width == 390:
            page.screenshot(path=str(output / 'mobile.png'))
            page.locator('.hero-visual').screenshot(path=str(output / 'mobile-demo.png'))
        page.locator('#burger').click()
        page.locator('#menu a[href="#install"]').click()
        expect(page).to_have_url(url + '#install')
        expect(page.locator('#menu')).to_have_attribute('aria-hidden', 'true')
        context.close()


def check_preloader(browser, url):
    """幕布收尾必须按「墙钟」有界，不能按帧累加。

    它曾经是 `head += N/RUN_MS * dt`，而 dt 被夹在 50ms；只要有一帧间隔超过
    50ms（3D 灯板初始化就会造成这种长任务，实测出现过 700ms+ 的单帧），
    这一帧就只推进 50ms，1.15s 的收尾被一路拖长 —— 1920 视口下实测
    is-loaded 出现在 5.1s，还卡在 99% 一两秒，观感像卡死。

    这里做**确定性故障注入**：在 run 阶段故意阻塞主线程 900ms，模拟那种长任务。
    按墙钟推进 → 收尾仍是 ~1.15s；按帧累加 → 变成 ~2.0s。差别是确定的，
    不受机器负载影响（靠采样渲染帧是分辨不出来的：主线程一忙，帧本来就稀疏）。

    用属性描述符包住 __preloaderRun，是为了拿到精确时间戳，同时注入阻塞。"""
    context = browser.new_context(viewport={'width': 1920, 'height': 1080})
    page = context.new_page()
    page.add_init_script("""window.__pre = {start: null, done: null};
        (() => {
          let real;
          Object.defineProperty(window, '__preloaderRun', {
            configurable: true,
            get: () => real,
            set(fn) {
              real = onDone => {
                window.__pre.start = performance.now();
                fn(() => { window.__pre.done = performance.now(); if (onDone) onDone(); });
                const until = performance.now() + 900;   // 模拟 3D 初始化那种长任务
                while (performance.now() < until) { /* block the main thread */ }
              };
            }
          });
        })();""")
    ready(page, url)
    page.wait_for_function('() => window.__pre.done !== null', timeout=20000)
    span = page.evaluate('() => window.__pre.done - window.__pre.start')
    assert span < 1500, f'幕布收尾耗时 {span:.0f}ms，疑似按帧累加而不是按墙钟（应约 1150ms）'
    expect(page.locator('#preloader')).to_have_css('visibility', 'hidden')
    context.close()


def check_hero_alignment(browser, url):
    """首屏文案要和「灯板」对齐，不是和「灯板 + 下方控件」那一整块对齐。

    网格是 align-items:center，而右列比灯板高约 528px（下方还有 hud、说明和
    整排控件），所以文案天然会比灯板中心低约 237px —— 1440×810 实测文案中心
    562 / 灯板中心 408，观感是文案沉在下面、底部只剩 24px。CSS 里用
    translateY(-237px) 补回来，这个值是 (右列高 − 灯板高)/2 − 顶线高 推出来的，
    下方控件一改高度就会失效，所以在这里量差值守住它。"""
    for width, height in ((1280, 800), (1440, 810), (1920, 1080)):
        context = browser.new_context(viewport={'width': width, 'height': height})
        page = context.new_page()
        ready(page, url)
        delta = page.evaluate("""() => {
            const centre = el => { const r = el.getBoundingClientRect();
                return (r.top + r.bottom) / 2; };
            return centre(document.querySelector('.hero-copy'))
                 - centre(document.querySelector('.led-stage'));
        }""")
        assert abs(delta) < 30, f'{width}px 首屏文案与灯板未对齐：中心相差 {delta:.0f}px'
        context.close()


def check_touch_and_narrow(browser, url):
    """小屏：可点区域不能过小；320px 下页头不能顶出视口。

    这两条都会被 body 上的 `overflow-x: clip` 掩盖 —— 元素被裁掉了，
    而 scrollWidth 仍等于 innerWidth，所以只断言横向溢出是查不出来的：
    320px 时汉堡按钮右边缘在 328px，被切掉一截，菜单就难点到了。

    用 reduced_motion='reduce' 和 check_mobile 保持一致：这里量的是尺寸和位置，
    与动效无关；少开一个持续跑 rAF + WebGL 的上下文，浏览器收尾也稳一些。"""
    for width in (320, 390):
        context = browser.new_context(viewport={'width': width, 'height': 844},
                                      has_touch=True, reduced_motion='reduce')
        page = context.new_page()
        ready(page, url)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        outside = page.evaluate("""() => [...document.querySelector('.site-head').children]
            .filter(el => getComputedStyle(el).display !== 'none')
            .map(el => ({cls: el.className, right: Math.round(el.getBoundingClientRect().right)}))
            .filter(item => item.right > innerWidth)""")
        assert not outside, f'{width}px 页头溢出：{outside}'
        small = page.evaluate("""() => {
            const bad = [];
            document.querySelectorAll('a, button, input[type=range], summary').forEach(el => {
                const style = getComputedStyle(el);
                // 正文里的行内链接按 WCAG 2.5.8 的 inline 例外放行
                if (style.display === 'inline' || style.visibility === 'hidden') return;
                if (el.closest('pre')) return;
                const r = el.getBoundingClientRect();
                if (!r.width || !r.height) return;
                if (Math.min(r.width, r.height) < 30) bad.push({
                    text: (el.textContent || el.id || '').trim().slice(0, 18),
                    w: Math.round(r.width), h: Math.round(r.height)});
            });
            return bad;
        }""")
        assert not small, f'{width}px 可点区域过小：{small}'
        context.close()


def check_static(browser, url, output):
    context = browser.new_context(java_script_enabled=False, viewport={'width': 390, 'height': 844})
    page = context.new_page()
    page.goto(url, wait_until='load')
    expect(page.locator('#ledFallback')).to_be_visible()
    for panel in ('manual', 'agent', 'verify'):
        expect(page.locator(f'#panel-{panel}')).to_be_visible()
    revealed = page.locator('[data-reveal]').evaluate_all(
        "elements => elements.every(el => getComputedStyle(el).opacity === '1')")
    assert revealed
    page.screenshot(path=str(output / 'no-javascript.png'))
    context.close()


def check_fallbacks(browser, url, output):
    for failure in ('slow-module', 'blocked-module', 'no-webgl', 'blocked-ui'):
        context = browser.new_context(viewport={'width': 1280, 'height': 1000}, reduced_motion='reduce')
        page = context.new_page()
        pending, errors = [], []
        # Playwright 按处理器参数个数决定传 (route) 还是 (route, request)，
        # 所以挂起的收集器必须保持单参数；循环变量用工厂函数按值绑进来（B023）。
        def make_hold_route(bucket):
            def hold(item):
                bucket.append(item)
            return hold
        page.on('pageerror', lambda error, errors=errors: errors.append(str(error)))
        if failure == 'slow-module':
            page.route('**/assets/vendor/three.module.min.js', make_hold_route(pending))
        if failure == 'blocked-module':
            page.route('**/assets/vendor/three.module.min.js', lambda route: route.abort())
        if failure == 'blocked-ui':
            page.route('**/assets/js/app.js', lambda route: route.abort())
        if failure == 'no-webgl':
            page.add_init_script("""const original = HTMLCanvasElement.prototype.getContext;
                HTMLCanvasElement.prototype.getContext = function(kind, ...args) {
                    return kind.includes('webgl') ? null : original.call(this, kind, ...args);
                };""")
        page.goto(url, wait_until='domcontentloaded')
        expect(page.locator('#ledFallback')).to_be_visible()
        if failure == 'blocked-ui':
            expect(page.locator('#panel-agent')).to_be_visible()
        else:
            expect(page.locator('#ledDots button')).to_have_count(7)
            page.get_by_role('button', name='设成蓝色', exact=True).click()
            expect(page.locator('#code-demo')).to_have_text('python pc/led_cli.py color 0 0 255')
            # slow-module 是「3D 还在路上」，标注应保持加载中；其余三种失败回退到 2D
            expected_renderer = ('3D 加载中 · 2D 预览' if failure == 'slow-module'
                                 else '2D 预览 · 浏览器模拟')
            expect(page.locator('#demoRenderer')).to_have_text(expected_renderer)
            # 蓝色满量 × 页面默认亮度（200）—— 别写死成某个数字，改默认值会漏
            blue = page.evaluate("""() => {
                const dflt = Number(document.getElementById('demoBrightness').defaultValue);
                return `rgb(0 0 ${Math.round(255 * dflt / 255)})`;
            }""")
            page.wait_for_function(
                "expected => document.querySelector('#ledFallback i')"
                ".style.getPropertyValue('--led-color') === expected",
                arg=blue)
        if failure == 'blocked-module':
            page.locator('.hero-visual').screenshot(path=str(output / 'fallback.png'))
        assert not errors, (failure, errors)
        for route in pending:
            route.abort()
        context.close()


def check_reduced_motion(browser, url):
    context = browser.new_context(reduced_motion='reduce', viewport={'width': 1280, 'height': 1000})
    page = context.new_page()
    page.add_init_script("""window.testFrameCount = 0;
        const request = window.requestAnimationFrame;
        window.requestAnimationFrame = callback => request.call(window, time => {
            window.testFrameCount++; callback(time);
        });""")
    ready(page, url)
    page.wait_for_load_state('networkidle')
    expect(page.locator('#demoPause')).to_be_disabled()
    before = page.evaluate('window.testFrameCount')
    page.wait_for_timeout(500)
    assert page.evaluate('window.testFrameCount') - before <= 2, 'Reduced motion must not render continuously'
    # 减少动态效果时，非法指令只给状态文字，不挂抖动动画 class
    page.locator('#demoCommand').fill('开门')
    page.locator('#demoForm button[type="submit"]').click()
    expect(page.locator('#demoCommand')).to_have_attribute('aria-invalid', 'true')
    assert not page.evaluate("document.getElementById('demoCommand').classList.contains('shake')"), \
        'Reduced motion must not play the shake animation'
    page.get_by_role('button', name='显示爱心', exact=True).click()
    expect(page.locator('#code-demo')).to_contain_text('heart')
    page.emulate_media(reduced_motion='no-preference')
    expect(page.locator('#demoPause')).to_be_enabled()
    context.close()


def check_contrast(browser, url):
    """正文/辅助文字对比度必须过 WCAG AA（4.5:1），章节强调色过非文本 3:1。

    颜色令牌注释里写着「约 5.8:1」「约 4.7:1」——那是设计时的静态推算，
    改色板、改底色时没人会重算。这里在真实渲染里逐元素量：
    文本色取计算样式，背景沿祖先链向上合成（半透明层叠到 html 底色上）。
    站点只有深色主题（color-scheme: dark），所以只查这一套。"""
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    page = context.new_page()
    ready(page, url)
    results = page.evaluate("""() => {
        const parse = text => {
            const m = text.match(/rgba?\\(([^)]+)\\)/);
            if (!m) return null;
            const parts = m[1].split(/[\\s,/]+/).filter(Boolean).map(parseFloat);
            return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
        };
        const lum = ({ r, g, b }) => {
            const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
        };
        // 把半透明背景逐层叠到 html 底色上，取有效背景亮度
        const bgOf = el => {
            let r = 6, g = 6, b = 8;   // html 的 --bg #060608
            const chain = [];
            for (let e = el; e; e = e.parentElement) chain.push(e);
            for (const e of chain.reverse()) {
                const c = parse(getComputedStyle(e).backgroundColor);
                if (c && c.a > 0) {
                    r = c.r * c.a + r * (1 - c.a);
                    g = c.g * c.a + g * (1 - c.a);
                    b = c.b * c.a + b * (1 - c.a);
                }
            }
            return lum({ r, g, b });
        };
        const ratio = (fg, bg) => (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
        const bad = [];
        const selectors = ['.hero-sub', '.lede', '.pcard p', '.wf-card p', '.wf-card h4',
                           '.cmp-a', '.cmp-b', '.code-bar', '.demo-note', '.demo-status',
                           '.panel-notes li', '.reg-list span', '.demo-suggest', '.kbd',
                           '.menu-nav a span', '.site-foot', '.flow-cap', '.reg-note'];
        for (const selector of selectors) {
            const el = document.querySelector(selector);
            if (!el) { bad.push(`${selector}: 元素不存在`); continue; }
            const fg = lum(parse(getComputedStyle(el).color));
            const value = ratio(fg, bgOf(el));
            if (value < 4.5) bad.push(`${selector}: ${value.toFixed(2)}:1`);
        }
        // 禁用按钮按「文字色 × 透明度」合成后再算；只改 opacity 也会被这里抓到
        const pause = document.querySelector('#demoPause');
        const pauseStyle = getComputedStyle(pause);
        const alpha = parseFloat(pauseStyle.opacity);
        const pauseBg = bgOf(pause);
        const pauseFg = lum(parse(pauseStyle.color)) * alpha + pauseBg * (1 - alpha);
        const pauseRatio = ratio(pauseFg, pauseBg);
        if (pauseRatio < 4.5) bad.push(`#demoPause disabled: ${pauseRatio.toFixed(2)}:1`);
        // 五个章节强调色会轮流成为焦点框颜色（:focus-visible outline），按非文本 3:1 查
        document.querySelectorAll('[data-acc]').forEach(section => {
            const hex = section.dataset.acc;
            const fg = lum({ r: parseInt(hex.slice(1, 3), 16), g: parseInt(hex.slice(3, 5), 16),
                             b: parseInt(hex.slice(5, 7), 16) });
            const value = ratio(fg, bgOf(section.querySelector('.sec-head') || section));
            if (value < 3) bad.push(`accent ${hex}: ${value.toFixed(2)}:1`);
        });
        return bad;
    }""")
    assert not results, f'对比度不足：{results}'
    context.close()


def check_manual_template(browser, url, output):
    context = browser.new_context(viewport={'width': 800, 'height': 900}, device_scale_factor=2)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("""window.testCanvasResizes = 0;
        const width = Object.getOwnPropertyDescriptor(HTMLCanvasElement.prototype, 'width');
        Object.defineProperty(HTMLCanvasElement.prototype, 'width', {
            ...width, set(value) {window.testCanvasResizes++; width.set.call(this, value);}
        });""")
    project = (output / 'manual-fixture/long project directory/设备 项目').resolve()
    manual = generate_manual(ROOT / 'skills/wuwu-intelligence', project, example_device(project, 8765), 8765)
    template = manual.read_text(encoding='utf-8')
    page.route('**/manual-fixture.html', lambda route: route.fulfill(body=template, content_type='text/html'))
    page.route('https://unpkg.com/three@0.160.0/build/three.module.js',
               lambda route: route.fulfill(path=str(ROOT / 'docs/assets/vendor/three.module.min.js'),
                                          content_type='text/javascript'))
    page.goto(url + 'manual-fixture.html', wait_until='networkidle')
    expect(page.locator('#hero-3d')).to_have_class('on')
    before = page.evaluate('window.testCanvasResizes')
    page.wait_for_timeout(500)
    assert page.evaluate('window.testCanvasResizes') == before, 'High-DPR rendering must not resize every frame'
    page.evaluate("""() => Object.defineProperty(navigator, 'clipboard', {
        configurable: true, value: {writeText: async value => {window.testClipboard = value;}}
    })""")
    page.locator('[data-copy]').first.click()
    expect(page.locator('[data-copy]').first).to_have_text('已复制')
    expected = command_text([sys.executable, 'cli.py', '--port', '8765', '--timeout', '8', 'status'])
    assert page.evaluate('window.testClipboard') == expected
    assert '{{' not in page.locator('body').inner_text()
    page.emulate_media(reduced_motion='reduce')
    for width in (320, 390):
        page.set_viewport_size({'width': width, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), \
            'Populated manual overflows on narrow screens'
    page.evaluate('scrollTo(0, 0)')
    page.screenshot(path=str(output / 'generated-manual-mobile.png'))
    assert not errors, errors
    context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.workbuddy/qa')
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=True)
    server = QuietServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'docs')))
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{server.server_port}/'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for name, check in (('desktop', check_desktop), ('mobile', check_mobile),
                                ('static', check_static), ('fallbacks', check_fallbacks)):
                check(browser, url, options.output)
                print(f'PASS {name}', flush=True)
            check_reduced_motion(browser, url)
            print('PASS reduced motion', flush=True)
            check_preloader(browser, url)
            print('PASS preloader timing', flush=True)
            check_hero_alignment(browser, url)
            print('PASS hero alignment', flush=True)
            check_touch_and_narrow(browser, url)
            print('PASS touch targets / narrow header', flush=True)
            check_contrast(browser, url)
            print('PASS contrast', flush=True)
            check_manual_template(browser, url, options.output)
            print('PASS manual template', flush=True)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
    print(f'Screenshots: {options.output}')


if __name__ == '__main__':
    main()
