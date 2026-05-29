#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uPeaks;       // R=max, G=|min|, B=rms (UNSIGNED_BYTE)
uniform float uPlayPos;         // 0..1
uniform float uGamma;           // gamma correction exponent (default 0.4)
uniform vec3 uWaveColor;        // 単一色 (波形全体)

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

  // RMS 中央帯 (同色でアルファを少し上乗せして濃く見せる)
  float rmsBoost = step(-corrRms, y) * step(y, corrRms) * 0.35;

  // 再生済みは透明度を下げて dim (背景 washi にブレンド → 視覚的に「淡く」)
  float dim = mix(0.35, 1.0, step(uPlayPos, x));

  float alpha = envelope * (1.0 + rmsBoost) * dim;
  fragColor = vec4(uWaveColor, alpha);
}
