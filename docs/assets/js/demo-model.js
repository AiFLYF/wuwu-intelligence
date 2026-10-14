/* Browser-only simulation. No hardware connection and no model/API calls. */
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const damp = (a, b, rate, dt) => a + (b - a) * (1 - Math.exp(-rate * dt));

function hsv(h, s, v) {
  h = ((h % 1) + 1) % 1;
  const i = Math.floor(h * 6), f = h * 6 - i;
  const p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  return [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][i % 6];
}

const HEART = ['.XX..XX.', 'XXXXXXXX', 'XXXXXXXX', 'XXXXXXXX', '.XXXXXX.', '..XXXX..', '...XX...', '........'];
export const PATTERNS = [
  { id: 'solid', name: 'SOLID COLOR', cn: '纯色', fn: () => [1, 0, 0] },
  { id: 'rainbow', name: 'RAINBOW WAVE', cn: '彩虹', fn: (x, y, t) => hsv(x / 7 * .62 + y / 7 * .12 + t * .14, .94, 1) },
  { id: 'chase', name: 'CHASE', cn: '追逐', fn: (x, y, t) => {
    const k = y * 8 + (y % 2 ? 7 - x : x), head = (t * 13) % 64;
    const d = Math.abs(k - head), b = Math.max(0, 1 - Math.min(d, 64 - d) / 7);
    return [b * .82, b * .93, b];
  } },
  { id: 'wave', name: 'WAVE', cn: '波浪', fn: (x, y, t) => {
    const b = .1 + .9 * Math.max(0, Math.sin(x * .95 - t * 2.6 + y * .35));
    return [b * .12, b * .72, b];
  } },
  { id: 'breathe', name: 'BREATHE', cn: '呼吸', fn: (x, y, t) => {
    const b = .12 + .88 * (.5 - .5 * Math.cos(t * 1.5));
    return [b, b * .7, b * .4];
  } },
  { id: 'heart', name: 'HEART', cn: '爱心', fn: (x, y, t) => {
    if (HEART[y][x] !== 'X') return [.02, .008, .012];
    const p = .58 + .42 * Math.sin(t * 3.1);
    return [p, p * .11, p * .2];
  } },
  { id: 'sparkle', name: 'SPARKLE', cn: '闪烁', fn: (x, y, t) => {
    const b = Math.pow(.5 + .5 * Math.sin(t * 1.7 + (y * 8 + x) * 2.399), 6);
    return [b, b * .88, b];
  } },
];

const COLORS = {
  红: [255, 0, 0], 绿: [0, 255, 0], 蓝: [0, 0, 255],
  白: [255, 255, 255], 暖白: [255, 180, 100],
  紫: [160, 64, 255], 黄: [255, 200, 0], 橙: [255, 100, 0],
};
const MODES = { 彩虹: 1, 彩虹灯: 1, 追逐: 2, 波浪: 3, 呼吸: 4, 呼吸灯: 4, 爱心: 5, 心形: 5, 闪烁: 6, 随机闪烁: 6 };

export function patternCommand(index) {
  const pattern = PATTERNS[index];
  if (!pattern) return null;
  if (index === 0) return colorCommand([255, 0, 0]);
  return { ok: true, pattern: index, payload: { cmd: pattern.id },
    command: `python pc/led_cli.py ${pattern.id}`, message: `已预览${pattern.cn}效果` };
}

function colorCommand(rgb) {
  return { ok: true, pattern: 0, color: rgb.map(n => n / 255),
    payload: { cmd: 'color', r: rgb[0], g: rgb[1], b: rgb[2] },
    command: `python pc/led_cli.py color ${rgb.join(' ')}`, message: `已预览 RGB(${rgb.join(', ')})` };
}

export function brightnessCommand(value) {
  if (!Number.isInteger(value) || value < 0 || value > 255) {
    return { ok: false, message: '亮度范围是 0–255，请重新输入。' };
  }
  return { ok: true, brightness: value, payload: { cmd: 'brightness', value },
    command: `python pc/led_cli.py brightness ${value}`, message: `预览亮度已设为 ${value} / 255` };
}

export function parseDemoCommand(input, currentBrightness = 128) {
  if (typeof input !== 'string' || input.length > 80) {
    return { ok: false, message: '请输入 80 字以内的示例指令。' };
  }
  let phrase = input.trim().replace(/\s+/g, '').replace(/[。！!？?]$/, '');
  if (!phrase) return { ok: false, message: '先输入一句指令，例如「灯板设成红色」。' };
  phrase = phrase.replace(/^(?:请)?(?:帮我)?(?:把)?(?:灯板|灯珠|矩阵|灯)?/, '');
  phrase = phrase.replace(/^(?:设置为|设置成|设为|设成|变成|变为|显示|来一个|来个|播放|开启|打开|跑一个|跑个)/, '');
  const colorName = phrase.replace(/色$/, '');
  if (Object.hasOwn(COLORS, colorName)) return colorCommand(COLORS[colorName]);
  if (['关灯', '关掉', '关闭', '熄灭'].includes(phrase)) return colorCommand([0, 0, 0]);
  if (Object.hasOwn(MODES, phrase)) return patternCommand(MODES[phrase]);
  if (['调暗', '调暗一点'].includes(phrase)) return brightnessCommand(Math.round(currentBrightness / 2));
  if (['调亮', '调亮一点'].includes(phrase)) return brightnessCommand(Math.min(255, currentBrightness + 64));
  const brightness = /^亮度(?:设为|设成|设置为|设置成)?(-?\d+)$/.exec(phrase);
  if (brightness) return brightnessCommand(Number(brightness[1]));
  const rgb = /^rgb[（(](\d+)[,，](\d+)[,，](\d+)[）)]$/i.exec(phrase);
  if (rgb) {
    const values = rgb.slice(1).map(Number);
    if (values.some(n => n > 255)) return { ok: false, message: 'RGB 每个分量都需要在 0–255 之间。' };
    return colorCommand(values);
  }
  return { ok: false, message: '这个演示只识别示例指令。试试「设成蓝色」「显示爱心」或「亮度 80」。' };
}

export function samplePixel(state, x, y, time) {
  const color = state.pattern === 0 ? state.color : PATTERNS[state.pattern].fn(x, y, time);
  return color.map(v => clamp(v * state.brightness / 255, 0, 1));
}
