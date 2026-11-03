// ESP32-S3 + WS2812B-64 最小固件骨架：整板纯色 / 亮度 / 熄灭 / 状态查询。
// 协议：TCP 8888，单行 JSON 一问一答。结构遵循 skills/wuwu-intelligence/references/protocol-template.md。
// 注意：本骨架尚未在真实硬件上验证，首次使用先按 examples/esp32-led-matrix/README.md 的说明核对。

#include <WiFi.h>
#include <FastLED.h>
#include <ArduinoJson.h>

// ── 用户配置区 ──────────────────────────────────────────────
// WiFi 凭据属于本地配置；正式项目请挪进被 .gitignore 排除的 config.h。
#define WIFI_SSID   "你的WiFi"
#define WIFI_PASS   "你的密码"
#define LED_PIN     38            // 避开 strapping/USB/Flash 引脚，38 对 ESP32-S3 是安全选择
#define NUM_LEDS    64
#define TCP_PORT    8888

CRGB leds[NUM_LEDS];
WiFiServer server(TCP_PORT);
WiFiClient client;

uint8_t brightnessValue = 200;
unsigned long lastReconnect = 0;

void sendResponse(const char* error) {
  // 一条指令恰好一个响应：所有分支都汇到这里，避免双发/漏发。
  JsonDocument doc;
  doc["ok"] = (error == nullptr);
  if (error) doc["error"] = error;
  serializeJson(doc, client);
  client.write('\n');
}

const char* cmdColor(JsonDocument& doc) {
  fill_solid(leds, NUM_LEDS, CRGB(doc["r"] | 0, doc["g"] | 0, doc["b"] | 0));
  FastLED.show();
  return nullptr;
}

const char* cmdBrightness(JsonDocument& doc) {
  int value = doc["value"] | brightnessValue;
  if (value < 0 || value > 255) return "brightness 需要 0-255";
  brightnessValue = value;
  FastLED.setBrightness(brightnessValue);
  FastLED.show();
  return nullptr;
}

const char* cmdOff(JsonDocument& /*unused*/) {
  FastLED.clear(true);
  return nullptr;
}

void processLine(const String& line) {
  JsonDocument doc;
  if (deserializeJson(doc, line)) { sendResponse("E_JSON"); return; }
  const char* cmd = doc["cmd"] | "";
  const char* error = nullptr;
  if (strcmp(cmd, "color") == 0) error = cmdColor(doc);
  else if (strcmp(cmd, "brightness") == 0) error = cmdBrightness(doc);
  else if (strcmp(cmd, "off") == 0) error = cmdOff(doc);
  else if (strcmp(cmd, "status") == 0) {
    JsonDocument payload;
    payload["ok"] = true;
    payload["brightness"] = brightnessValue;
    payload["ip"] = WiFi.localIP().toString();
    payload["rssi"] = WiFi.RSSI();
    serializeJson(payload, client);
    client.write('\n');
    return;
  } else {
    error = "E_CMD";
  }
  sendResponse(error);
}

void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  // 每 12s 强制 disconnect->begin 重连；只调 reconnect 在手机热点休眠时救不回来。
  if (millis() - lastReconnect < 12000) return;
  lastReconnect = millis();
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void handleClients() {
  if (!client || !client.connected()) {
    if (client) client.stop();
    client = server.available();
    return;
  }
  static String buffer;
  while (client.available()) {
    char c = (char)client.read();
    if (c == '\n') { processLine(buffer); buffer = ""; }
    else if (buffer.length() < 1024) buffer += c;   // 行缓冲上限，防粘包撑爆内存
  }
}

void setup() {
  Serial.begin(115200);
  FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(brightnessValue);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  // 首连 8 轮 × 10s：热点的 beacon/DHCP 慢很常见，急着重试只会更慢。
  for (int round = 0; round < 8 && WiFi.status() != WL_CONNECTED; round++) {
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) delay(250);
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("IP: "); Serial.println(WiFi.localIP());
    server.begin();
    Serial.println("TCP server started");
  } else {
    Serial.println("WiFi 首连失败，loop 会继续每 12s 重试");
  }
}

void loop() {
  ensureWiFi();
  if (WiFi.status() == WL_CONNECTED) handleClients();
  delay(1);
}
