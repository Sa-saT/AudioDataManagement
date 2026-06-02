#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uPeaks;       // R=max, G=|min|, B=rms (UNSIGNED_BYTE)
uniform float uPlayPos;         // 0..1
uniform float uGamma;           // gamma correction exponent (default 0.4)
uniform vec3 uWaveColor;        // 未再生側の色
uniform vec3 uPlayedColor;      // 再生済 (再生後) の色

// 波形を離散バーで描画する (images/53.png 相当の荒さ)
const float BAR_COUNT = 128.0;
const float BAR_GAP_RATIO = 0.22;   // バー幅の 22% を gap にする (= 78% 描画)

void main() {
  float x = vUv.x;
  float y = vUv.y * 2.0 - 1.0;          // -1..+1 中央 0

  // バー量子化: x をバー index に切り出して、各バーの中心位置でサンプリング
  float barIdx = floor(x * BAR_COUNT);
  float barCenter = (barIdx + 0.5) / BAR_COUNT;
  float frac = fract(x * BAR_COUNT);

  // バー幅マスク (gap 範囲を切り捨て)
  float barMask = step(BAR_GAP_RATIO * 0.5, frac) * step(frac, 1.0 - BAR_GAP_RATIO * 0.5);

  vec3 p = texture(uPeaks, vec2(barCenter, 0.5)).rgb;
  float pMax = p.r;
  float pMin = -p.g;                    // ストア時に |min| → 負へ戻す
  float pRms = p.b;

  // ガンマ補正 (小さい値を持ち上げる)
  float corrMax = pow(pMax, uGamma);
  float corrMin = -pow(-pMin, uGamma);
  float corrRms = pow(pRms, uGamma);

  // 包絡: y が [corrMin, corrMax] にあれば描画
  float envelope = step(corrMin, y) * step(y, corrMax);

  // RMS 中央帯 (アルファを少し上乗せして濃く見せる)
  float rmsBoost = step(-corrRms, y) * step(y, corrRms) * 0.35;

  // 再生位置で色切替: x < uPlayPos = 再生後 (played) / それ以降 = 未再生
  vec3 color = mix(uPlayedColor, uWaveColor, step(uPlayPos, x));

  float alpha = envelope * (1.0 + rmsBoost) * barMask;
  fragColor = vec4(color, alpha);
}
