/** GLSL for the story landscape. Written GLSL1-style; three.js adapts it for WebGL2. Colours are sRGB. */

const NOISE = /* glsl */ `
float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}
float vnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  float a = hash12(i);
  float b = hash12(i + vec2(1.0, 0.0));
  float c = hash12(i + vec2(0.0, 1.0));
  float d = hash12(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 4; i++) {
    v += a * vnoise(p);
    p = p * 2.03 + 17.1;
    a *= 0.5;
  }
  return v;
}
`;

const FOG = /* glsl */ `
vec3 applyFog(vec3 col, float dist) {
  float f = 1.0 - exp(-uFogDensity * dist);
  return mix(col, uFogColor, clamp(f, 0.0, 1.0));
}
bool radarSide() {
  return uSarMix > 0.001 && gl_FragCoord.x > uRadarX * uResolution.x;
}
`;

const SHARED_UNIFORMS = /* glsl */ `
uniform float uTime;
uniform float uDawn;
uniform float uRadarX;
uniform float uSarMix;
uniform vec2 uResolution;
uniform vec3 uFogColor;
uniform float uFogDensity;
`;

export const GROUND_VERT = /* glsl */ `
varying vec2 vWorld;
varying vec3 vWorldPos;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorld = wp.xz;
  vWorldPos = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
`;

export const GROUND_FRAG = /* glsl */ `
varying vec2 vWorld;
varying vec3 vWorldPos;
${SHARED_UNIFORMS}
uniform vec2 uPlot;
uniform float uPlotGlow;
uniform float uRing;
uniform float uFlood;
uniform vec4 uHaor[6];
uniform float uCoastZ;
${NOISE}
${FOG}

const float BLOCK = 0.12;
const float ANGLE = -0.19;
const vec3 MUSTARD = vec3(0.929, 0.718, 0.137);
const vec3 HUSK = vec3(0.937, 0.922, 0.867);
const vec3 BUND = vec3(0.047, 0.110, 0.082);
const vec3 HAOR_WATER = vec3(0.070, 0.180, 0.205);
const vec3 SEA = vec3(0.055, 0.150, 0.170);

vec2 fieldCoord(vec2 w) {
  float c = cos(ANGLE);
  float s = sin(ANGLE);
  vec2 q = vec2(c * w.x - s * w.y, s * w.x + c * w.y) / BLOCK;
  q.x += mod(floor(q.y), 2.0) * 0.31;
  return q;
}

// Each block is split into 2-5 long plots, vertically or horizontally.
float stripCount(vec2 cell) { return 2.0 + floor(hash12(cell) * 4.0); }
float stripAxis(vec2 q) {
  vec2 cell = floor(q);
  vec2 f = fract(q);
  return mix(f.y, f.x, step(0.45, hash12(cell + 7.13)));
}
float stripIndex(vec2 q) { return floor(stripAxis(q) * stripCount(floor(q))); }

vec3 greenFor(float h) {
  float k = floor(h * 6.0);
  if (k < 1.0) return vec3(0.090, 0.220, 0.157);
  if (k < 2.0) return vec3(0.106, 0.255, 0.188);
  if (k < 3.0) return vec3(0.125, 0.290, 0.208);
  if (k < 4.0) return vec3(0.078, 0.188, 0.133);
  if (k < 5.0) return vec3(0.141, 0.314, 0.224);
  return vec3(0.102, 0.235, 0.169);
}

void main() {
  vec2 q = fieldCoord(vWorld);
  vec2 cell = floor(q);
  vec2 f = fract(q);
  float n = stripCount(cell);
  float axis = stripAxis(q);
  float idx = floor(axis * n);
  float inStrip = fract(axis * n);
  float dStrip = min(inStrip, 1.0 - inStrip) / n;
  float dBlock = min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y));
  float dEdge = min(dStrip, dBlock);

  float h = hash12(cell * vec2(7.0, 13.0) + idx);
  float h2 = hash12(cell * vec2(3.1, 5.7) + idx * 1.9);
  vec3 plot = h < 0.07 ? vec3(0.435, 0.373, 0.133) * 0.82 : (h < 0.12 ? vec3(0.086, 0.204, 0.231) : greenFor(h2));

  // Fade plot detail to a regional tone once a block is only a few pixels wide.
  float px = length(fwidth(q));
  float detail = 1.0 - smoothstep(0.09, 0.32, px);
  vec3 region = mix(vec3(0.090, 0.215, 0.155), vec3(0.122, 0.280, 0.200), fbm(vWorld * 0.22));
  vec3 col = mix(region, plot, detail);
  float bund = 1.0 - smoothstep(0.035 - px, 0.035 + px, dEdge);
  col = mix(col, BUND, bund * 0.85 * detail);

  // Haor basins: water that spreads with the flood level.
  float haor = 0.0;
  for (int i = 0; i < 6; i++) {
    vec4 b = uHaor[i];
    if (b.z <= 0.0) continue;
    float d = length(vWorld - b.xy) / (b.z * (1.0 + uFlood * 1.1));
    d += (fbm(vWorld * 2.4 + float(i) * 3.7) - 0.5) * 0.5;
    haor = max(haor, 1.0 - smoothstep(0.86, 1.0, d));
  }
  col = mix(col, HAOR_WATER, haor);

  float coast = uCoastZ + (fbm(vec2(vWorld.x * 0.22, 3.7)) - 0.5) * 4.0;
  float sea = smoothstep(coast - 0.5, coast + 0.5, vWorld.y);
  col = mix(col, SEA, sea);

  // Rahim's plot, his neighbours inside the 5 km union ring, and the dashed ring itself.
  vec2 pq = fieldCoord(uPlot);
  float isPlot = step(length(cell - floor(pq)), 0.01) * step(abs(idx - stripIndex(pq)), 0.01);
  float fromPlot = length(vWorld - uPlot);
  float neighbour = step(hash12(cell * 3.1 + idx * 1.7), 0.05) * step(fromPlot, uRing) * (1.0 - isPlot);
  float outline = neighbour * (1.0 - smoothstep(0.06 - px, 0.06 + px, dEdge));
  col = mix(col, MUSTARD * 0.92, outline * uPlotGlow * detail);
  col = mix(col, MUSTARD, isPlot * uPlotGlow);
  // A soft halo so the eye finds his plot first.
  col += MUSTARD * exp(-pow(fromPlot / 0.085, 2.0)) * 0.28 * uPlotGlow;
  float ringAA = fwidth(fromPlot) * 1.3;
  float ring = 1.0 - smoothstep(ringAA * 0.5, ringAA * 1.5, abs(fromPlot - uRing));
  float dash = step(0.45, fract(atan(vWorld.y - uPlot.y, vWorld.x - uPlot.x) / 6.2831853 * 56.0));
  col = mix(col, HUSK, ring * dash * 0.42 * uPlotGlow);

  // Night to dawn.
  col *= mix(0.84, 1.08, uDawn);
  col += uDawn * vec3(0.040, 0.026, 0.0) * (0.5 + 0.5 * fbm(vWorld * 0.18));

  // Sentinel-1 style radar right of the divider: speckled land, black open water.
  if (radarSide()) {
    float grain = hash12(floor(vWorld * 140.0));
    float land = 0.34 + 0.16 * h2 + 0.24 * (grain - 0.5);
    float water = 0.03 + 0.05 * grain;
    float b = mix(land, water, max(haor, sea));
    col = mix(col, vec3(b * 0.95, b, b * 0.97), uSarMix);
  }

  // Beyond the delta, everything sinks into the night.
  float edge = smoothstep(34.0, 62.0, length(vWorld - vec2(1.5, 2.0)));
  col = mix(col, uFogColor, edge);
  gl_FragColor = vec4(applyFog(col, distance(cameraPosition, vWorldPos)), 1.0);
}
`;

export const RIBBON_VERT = /* glsl */ `
varying vec2 vUv;
varying vec3 vWorldPos;
void main() {
  vUv = uv;
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorldPos = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
`;

export const WATER_FRAG = /* glsl */ `
varying vec2 vUv;
varying vec3 vWorldPos;
${SHARED_UNIFORMS}
uniform float uLength;
${FOG}
void main() {
  float edge = smoothstep(0.0, 0.2, vUv.y) * smoothstep(1.0, 0.8, vUv.y);
  float glint = pow(max(0.0, sin(vUv.x * uLength * 9.0 - uTime * 0.8 + vUv.y * 3.0)), 18.0) * 0.22;
  vec3 col = mix(vec3(0.071, 0.176, 0.200), vec3(0.106, 0.235, 0.262), uDawn) + glint * vec3(0.435, 0.659, 0.710);
  if (radarSide()) col = mix(col, vec3(0.03), uSarMix);
  gl_FragColor = vec4(applyFog(col, distance(cameraPosition, vWorldPos)), edge * 0.95);
}
`;

export const ROAD_FRAG = /* glsl */ `
varying vec2 vUv;
varying vec3 vWorldPos;
${SHARED_UNIFORMS}
uniform float uLength;
uniform float uProgress;
uniform float uMode;
uniform float uVisible;
${FOG}
void main() {
  float core = smoothstep(0.0, 0.35, vUv.y) * smoothstep(1.0, 0.65, vUv.y);
  float done = step(vUv.x, uProgress);
  float dash = step(0.5, fract(vUv.x * uLength * 2.5 - uTime * 0.7));
  vec3 base = vec3(0.30, 0.36, 0.33);
  vec3 lit = mix(vec3(0.949, 0.329, 0.357), vec3(0.929, 0.718, 0.137), uMode);
  vec3 col = mix(base, lit, done * mix(1.0, 0.65 + 0.35 * dash, uMode));
  float alpha = core * mix(0.45, 1.0, done) * uVisible;
  gl_FragColor = vec4(applyFog(col, distance(cameraPosition, vWorldPos)), alpha);
}
`;

export const CLOUD_VERT = /* glsl */ `
varying vec2 vWorld;
varying vec2 vUv;
varying vec3 vWorldPos;
void main() {
  vUv = uv;
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorld = wp.xz;
  vWorldPos = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
`;

export const CLOUD_FRAG = /* glsl */ `
varying vec2 vWorld;
varying vec2 vUv;
varying vec3 vWorldPos;
${SHARED_UNIFORMS}
uniform float uCloud;
${NOISE}
${FOG}
void main() {
  if (uCloud < 0.001) discard;
  float n = fbm(vWorld * 0.42 + vec2(uTime * 0.015, uTime * 0.006));
  float a = smoothstep(0.36, 0.72, n) * uCloud;
  a *= smoothstep(0.0, 0.18, vUv.x) * smoothstep(1.0, 0.82, vUv.x) * smoothstep(0.0, 0.18, vUv.y) * smoothstep(1.0, 0.82, vUv.y);
  if (radarSide()) a *= 1.0 - uSarMix;
  vec3 c = mix(vec3(0.40, 0.46, 0.45), vec3(0.64, 0.68, 0.66), n);
  gl_FragColor = vec4(applyFog(c, distance(cameraPosition, vWorldPos) * 0.6), a * 0.94);
}
`;
