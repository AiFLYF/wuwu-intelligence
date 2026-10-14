import test from 'node:test';
import assert from 'node:assert/strict';
import { PATTERNS, parseDemoCommand, samplePixel } from '../docs/assets/js/demo-model.js';

test('natural-language examples resolve to a command and matching pixel values', () => {
  const result = parseDemoCommand('请帮我把灯板设成蓝色');
  assert.equal(result.command, 'python pc/led_cli.py color 0 0 255');
  assert.deepEqual(result.payload, { cmd: 'color', r: 0, g: 0, b: 255 });
  assert.deepEqual(samplePixel({ ...result, brightness: 255 }, 0, 0, 0), [0, 0, 1]);
});

test('switching off produces black pixels, including at full brightness', () => {
  const result = parseDemoCommand('关灯');
  assert.equal(result.ok, true);
  assert.deepEqual(samplePixel({ ...result, brightness: 255 }, 7, 7, 1), [0, 0, 0]);
});

test('brightness is bounded, and relative commands use the actual preview state', () => {
  assert.equal(parseDemoCommand('调暗一点', 100).brightness, 50);
  assert.equal(parseDemoCommand('调亮一点', 240).brightness, 255);
  assert.equal(parseDemoCommand('亮度 0').brightness, 0);
  assert.equal(parseDemoCommand('亮度 256').ok, false);
  assert.equal(parseDemoCommand('亮度 -1').ok, false);
});

test('RGB syntax accepts valid components and rejects overflow', () => {
  assert.deepEqual(parseDemoCommand('RGB(12, 34, 56)').payload, { cmd: 'color', r: 12, g: 34, b: 56 });
  assert.equal(parseDemoCommand('rgb(0,0,999)').ok, false);
});

test('unsupported, negative, and prototype-like phrases do not trigger a command', () => {
  for (const phrase of ['', '不要设成红色', '开门', '__proto__', 'constructor', '<img src=x onerror=alert(1)>', 'x'.repeat(81)]) {
    assert.equal(parseDemoCommand(phrase).ok, false, phrase);
  }
});

test('each effect yields finite displayable values for every pixel', () => {
  for (let pattern = 0; pattern < PATTERNS.length; pattern++) {
    for (const time of [0, .5, 8, 100]) {
      for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) {
        const rgb = samplePixel({ pattern, color: [1, 0, 0], brightness: 128 }, x, y, time);
        assert.equal(rgb.length, 3);
        assert.ok(rgb.every(value => Number.isFinite(value) && value >= 0 && value <= 1));
      }
    }
  }
});
