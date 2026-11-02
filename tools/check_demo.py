#!/usr/bin/env python3
"""Run browser regression checks against a private temporary localhost server.

Install requirements-browser.txt and run `python -m playwright install chromium`.
Screenshots are written to .workbuddy/qa/ by default.
"""

import argparse
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
    page.locator('#demoForm button').click()
    expect(page.locator('#demoCommand')).to_have_attribute('aria-invalid', 'true')
    expect(page.locator('#code-demo')).to_have_text('python pc/led_cli.py color 0 0 255')
    page.get_by_role('button', name='显示爱心', exact=True).click()
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
            assert page.evaluate("document.activeElement.closest('#menu') !== null || document.activeElement.id === 'burger'")
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
    assert page.locator('[data-reveal]').evaluate_all("elements => elements.every(el => getComputedStyle(el).opacity === '1')")
    page.screenshot(path=str(output / 'no-javascript.png'))
    context.close()


def check_fallbacks(browser, url, output):
    for failure in ('slow-module', 'blocked-module', 'no-webgl', 'blocked-ui'):
        context = browser.new_context(viewport={'width': 1280, 'height': 1000}, reduced_motion='reduce')
        page = context.new_page()
        pending, errors = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        if failure == 'slow-module':
            page.route('**/assets/vendor/three.module.min.js', lambda route: pending.append(route))
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
            expect(page.locator('#demoRenderer')).to_have_text('2D 预览 · 浏览器模拟')
            # 蓝色满量 × 页面默认亮度（200）—— 别写死成某个数字，改默认值会漏
            blue = page.evaluate("""() => {
                const dflt = Number(document.getElementById('demoBrightness').defaultValue);
                return `rgb(0 0 ${Math.round(255 * dflt / 255)})`;
            }""")
            page.wait_for_function(
                "expected => document.querySelector('#ledFallback i').style.getPropertyValue('--led-color') === expected",
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
    page.get_by_role('button', name='显示爱心', exact=True).click()
    expect(page.locator('#code-demo')).to_contain_text('heart')
    page.emulate_media(reduced_motion='no-preference')
    expect(page.locator('#demoPause')).to_be_enabled()
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
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Populated manual overflows on narrow screens'
    page.evaluate('scrollTo(0, 0)')
    page.screenshot(path=str(output / 'generated-manual-mobile.png'))
    assert not errors, errors
    context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.workbuddy/qa')
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'docs')))
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
