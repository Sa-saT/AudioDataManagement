#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uPeaks;         // R=max, G=|min|, B=rms (UNSIGNED_BYTE)
uniform float uPlayPos;           // 0..1
uniform float uHoverPos;          // 0..1 or -1 (none)
uniform float uTime;              // seconds (for pulse)
uniform float uGamma;             // gamma correction exponent (default 0.4)
uniform vec3 uWaveColor;          // 未再生側 (washi)
uniform vec3 uProgressColor;      // 再生済側 (turquoise)
uniform vec3 uRmsColor;           // 中央 RMS 帯
uniform vec3 uHoverGlow;          // ホバー時の発光色

void main() {
  float x = vUv.x;
  float y = vUv.y * 2.0 - 1.0;          // -1..+1 中央 0

  vec3 p = texture(uPeaks, vec2(x, 0.5)).rgb;
  float pMax = p.r;
  float pMin = -p.g;                    // ストア時に |min| → 負へ戻す
  float pRms = p.b;

  // ガンマ補正 (小さい値を持ち上げる)
  float corrMax = pow(pMax, uGamma);
  float corrMin = -pow(-pMin, uGamma);
  float corrRms = pow(pRms, uGamma);

  // 包絡: y が [corrMin, corrMax] にあれば描画
  float envelope = step(corrMin, y) * step(y, corrMax);

  // RMS 中央帯
  float rmsBand = step(-corrRms, y) * step(y, corrRms);

  // 再生位置で色グラデ切替
  vec3 baseColor = mix(uProgressColor, uWaveColor,
                       smoothstep(uPlayPos - 0.002, uPlayPos + 0.002, x));
  vec3 color = mix(baseColor, uRmsColor, rmsBand * 0.7);

  // ホバーグロー (パルス、6.2832 = 2π = 1Hz)
  if (uHoverPos >= 0.0) {
    float d = abs(x - uHoverPos);
    float pulse = (1.0 - smoothstep(0.0, 0.06, d))
                * (0.6 + 0.4 * sin(uTime * 6.2832));
    color += uHoverGlow * pulse * 0.4;
  }

  // 再生位置の細い縦カーソル (白フラッシュ)
  float cursor = 1.0 - smoothstep(0.0, 0.0015, abs(x - uPlayPos));
  color = mix(color, vec3(1.0), cursor * 0.6);

  fragColor = vec4(color * envelope, envelope);
}
