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
            page.wait_for_function("document.querySelector('#ledFallback i').style.getPropertyValue('--led-color') === 'rgb(0 0 128)'")
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
