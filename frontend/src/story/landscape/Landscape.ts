/**
 * The story's persistent world: one Three.js scene of the delta whose camera follows the reader's scroll.
 * Chapters (scroll progress P in [0, 7)): 0 hero, 1 cold storage, 2 road to Dhaka, 3 answer, 4 haor,
 * 5 agents, 6 dawn. Each chapter holds a still pose for its first 60% and travels to the next one after.
 * HTML labels (children of `labelsRoot` with data-lat/lon/alt/ch) are positioned here every frame.
 */

import * as THREE from "three";

import {
  COAST_LAT,
  FACILITIES,
  formatLatLon,
  HAOR_BASINS,
  PLACES,
  project,
  QUOTA_SHARES,
  RIVERS,
  ROUTE_TO_DHAKA,
  TIER_STOPS,
  UNIT_KM,
  unproject,
  type FacilitySeed,
  type LatLon,
} from "../geo";
import { CLOUD_FRAG, CLOUD_VERT, GROUND_FRAG, GROUND_VERT, RIBBON_VERT, ROAD_FRAG, WATER_FRAG } from "./shaders";

export const CHAPTER_COUNT = 7;

interface Pose {
  at: LatLon;
  dist: number;
  pitch: number;
  yaw: number;
}

export type RouteMode = "syndicate" | "pooled";

export interface LandscapeOptions {
  canvas: HTMLCanvasElement;
  labelsRoot: HTMLElement;
  reducedMotion: boolean;
  onPlace?: (text: string) => void;
}

const smoothstep = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const vec3Of = (p: LatLon, y = 0) => {
  const { x, z } = project(p);
  return new THREE.Vector3(x, y, z);
};

function mixPose(a: Pose, b: Pose, t: number): Pose {
  return {
    at: { lat: a.at.lat + (b.at.lat - a.at.lat) * t, lon: a.at.lon + (b.at.lon - a.at.lon) * t },
    dist: Math.exp(Math.log(a.dist) + (Math.log(b.dist) - Math.log(a.dist)) * t),
    pitch: a.pitch + (b.pitch - a.pitch) * t,
    yaw: a.yaw + (b.yaw - a.yaw) * t,
  };
}

/** The cold-storage still: centred on the district's stores, far enough back that all of them clear the text column. */
function coldPose(district: FacilitySeed["district"]): Pose {
  const points = FACILITIES.filter((f) => f.district === district).map((f) => project(f.at));
  const xs = points.map((p) => p.x);
  const zs = points.map((p) => p.z);
  const [x0, x1, z0, z1] = [Math.min(...xs), Math.max(...xs), Math.min(...zs), Math.max(...zs)];
  return { at: unproject((x0 + x1) / 2, (z0 + z1) / 2), dist: Math.max(4.6, 2.2 * (x1 - x0), 1.8 * (z1 - z0)), pitch: 48, yaw: 14 };
}

/** A flat strip along a curve; uv.x runs 0..1 along it, uv.y across it. */
function ribbon(points: THREE.Vector3[], width: number, samples: number): { geometry: THREE.BufferGeometry; curve: THREE.CatmullRomCurve3 } {
  const curve = new THREE.CatmullRomCurve3(points, false, "centripetal");
  const positions: number[] = [];
  const uvs: number[] = [];
  const index: number[] = [];
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const p = curve.getPointAt(t);
    const tangent = curve.getTangentAt(t);
    const nx = -tangent.z, nz = tangent.x;
    const len = Math.hypot(nx, nz) || 1;
    const hw = width / 2;
    positions.push(p.x + (nx / len) * hw, p.y, p.z + (nz / len) * hw, p.x - (nx / len) * hw, p.y, p.z - (nz / len) * hw);
    uvs.push(t, 0, t, 1);
    if (i < samples) {
      const a = i * 2;
      index.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(index);
  return { geometry, curve };
}

function glowTexture(): THREE.CanvasTexture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.25, "rgba(255,255,255,0.75)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

const NIGHT = new THREE.Color("#0e211a");
const DAWN = new THREE.Color("#22412f");
const RED = new THREE.Color("#f2545b");
const MUSTARD = new THREE.Color("#edb723");
const HUSK = new THREE.Color("#efebdd");

export class Landscape {
  static isSupported(): boolean {
    try {
      const canvas = document.createElement("canvas");
      return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
    } catch {
      return false;
    }
  }

  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.PerspectiveCamera(38, 1, 0.05, 400);
  private readonly canvas: HTMLCanvasElement;
  private readonly labelsRoot: HTMLElement;
  private readonly reduced: boolean;
  private readonly onPlace?: (text: string) => void;
  private readonly shared = {
    uTime: { value: 0 },
    uDawn: { value: 0 },
    uRadarX: { value: 0.62 },
    uSarMix: { value: 0 },
    uResolution: { value: new THREE.Vector2(1, 1) },
    // The custom shaders write sRGB directly, so the fog colour is passed as sRGB, not three.js linear.
    uFogColor: { value: new THREE.Vector3(0.055, 0.129, 0.102) },
    uFogDensity: { value: 0.1 },
  };
  private readonly ground: THREE.ShaderMaterial;
  private readonly road: THREE.ShaderMaterial;
  private readonly cloud: THREE.ShaderMaterial;
  private readonly route: THREE.CatmullRomCurve3;
  private readonly truck: THREE.Sprite;
  private readonly posts = new THREE.Group();
  private readonly blocks: THREE.InstancedMesh[] = [];
  private readonly blockMaterials: THREE.MeshStandardMaterial[] = [];
  private readonly poses: Pose[];
  private readonly resizeObserver: ResizeObserver;
  private readonly disposables: { dispose: () => void }[] = [];
  private labels: HTMLElement[] = [];
  private labelWidths: number[] = [];
  private targetP = 0;
  private smoothP = 0;
  private lastFrame = 0;
  private raf = 0;
  private lateralShift = 0;
  private routeMode: RouteMode = "syndicate";
  private tierFocus: number | null = null;
  private radarOn = false;
  private lastPlace = "";
  private lastPlaceAt = 0;
  private readonly fadeIn = { start: 0 };
  private readonly srgb = { r: 0, g: 0, b: 0 };

  constructor({ canvas, labelsRoot, reducedMotion, onPlace }: LandscapeOptions) {
    this.canvas = canvas;
    this.labelsRoot = labelsRoot;
    this.reduced = reducedMotion;
    this.onPlace = onPlace;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    this.renderer.setClearColor(NIGHT);

    this.poses = [
      { at: PLACES.rahimPlot, dist: 3.2, pitch: 52, yaw: -8 },
      coldPose("Rangpur"),
      { at: PLACES.mithapukur, dist: 9, pitch: 46, yaw: 20 },
      // The whole road, Mithapukur to Karwan Bazar; the target sits south of the midpoint because the near half of the view is shorter.
      { at: { lat: 24.5, lon: 89.82 }, dist: 33, pitch: 62, yaw: 8 },
      { at: PLACES.abdulFields, dist: 4.8, pitch: 54, yaw: -12 },
      { at: { lat: 24.35, lon: 90.2 }, dist: 50, pitch: 74, yaw: 0 },
      { at: PLACES.rahimPlot, dist: 5.6, pitch: 34, yaw: -24 },
    ];

    // Ground: the whole delta in one procedural shader.
    const plot = project(PLACES.rahimPlot);
    this.ground = new THREE.ShaderMaterial({
      vertexShader: GROUND_VERT,
      fragmentShader: GROUND_FRAG,
      uniforms: {
        ...this.shared,
        uPlot: { value: new THREE.Vector2(plot.x, plot.z) },
        uPlotGlow: { value: 1 },
        uRing: { value: 5 / UNIT_KM },
        uFlood: { value: 0 },
        uHaor: {
          value: Array.from({ length: 6 }, (_, i) => {
            const basin = HAOR_BASINS[i];
            if (!basin) return new THREE.Vector4(0, 0, 0, 0);
            const p = project(basin.at);
            return new THREE.Vector4(p.x, p.z, basin.radiusKm / UNIT_KM, 0);
          }),
        },
        uCoastZ: { value: project({ lat: COAST_LAT, lon: 90 }).z },
      },
    });
    const groundMesh = new THREE.Mesh(new THREE.PlaneGeometry(170, 170, 1, 1), this.ground);
    groundMesh.rotation.x = -Math.PI / 2;
    this.scene.add(groundMesh);
    this.track(groundMesh.geometry, this.ground);

    // Rivers.
    for (const river of RIVERS) {
      const { geometry, curve } = ribbon(river.points.map((p) => vec3Of(p, 0.002)), river.width, 220);
      const material = new THREE.ShaderMaterial({
        vertexShader: RIBBON_VERT,
        fragmentShader: WATER_FRAG,
        uniforms: { ...this.shared, uLength: { value: curve.getLength() } },
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
      });
      this.scene.add(new THREE.Mesh(geometry, material));
      this.track(geometry, material);
    }

    // The road to Dhaka, lit as the potatoes travel.
    const road = ribbon(ROUTE_TO_DHAKA.map((p) => vec3Of(p, 0.004)), 0.055, 400);
    this.route = road.curve;
    this.road = new THREE.ShaderMaterial({
      vertexShader: RIBBON_VERT,
      fragmentShader: ROAD_FRAG,
      uniforms: {
        ...this.shared,
        uLength: { value: road.curve.getLength() },
        uProgress: { value: 0 },
        uMode: { value: 0 },
        uVisible: { value: 0 },
      },
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    this.scene.add(new THREE.Mesh(road.geometry, this.road));
    this.track(road.geometry, this.road);

    const glow = glowTexture();
    this.truck = new THREE.Sprite(new THREE.SpriteMaterial({
      map: glow, color: RED, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    }));
    this.truck.scale.setScalar(0.34);
    this.scene.add(this.truck);
    this.track(glow, this.truck.material);

    this.scene.add(this.posts);

    // Cold stores: three stacked layers per facility (traders, owners, farmers' share of the quota).
    const layers: [number, THREE.Color][] = [
      [QUOTA_SHARES.traders, new THREE.Color("#6b7f72")],
      [QUOTA_SHARES.owners, new THREE.Color("#4f8b99")],
      [QUOTA_SHARES.farmers, MUSTARD.clone()],
    ];
    const box = new THREE.BoxGeometry(1, 1, 1);
    box.translate(0, 0.5, 0);
    this.track(box);
    let base = new Array(FACILITIES.length).fill(0) as number[];
    for (const [share, color] of layers) {
      const material = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.25, roughness: 0.85, transparent: true, opacity: 0 });
      const mesh = new THREE.InstancedMesh(box, material, FACILITIES.length);
      const matrix = new THREE.Matrix4();
      base = FACILITIES.map((f: FacilitySeed, i) => {
        const height = (f.capacityMt / 12000) * 0.42 * share;
        const p = project(f.at);
        matrix.compose(new THREE.Vector3(p.x, base[i], p.z), new THREE.Quaternion(), new THREE.Vector3(0.075, height, 0.075));
        mesh.setMatrixAt(i, matrix);
        return base[i] + height;
      });
      this.scene.add(mesh);
      this.blocks.push(mesh);
      this.blockMaterials.push(material);
      this.track(material);
    }
    const hemi = new THREE.HemisphereLight("#9fb8ad", "#0e211a", 1.1);
    const sun = new THREE.DirectionalLight("#efebdd", 1.3);
    sun.position.set(4, 10, 3);
    this.scene.add(hemi, sun);

    // Monsoon cloud over the haor; the radar divider cuts through it.
    const haorCentre = project({ lat: 25.05, lon: 91.2 });
    this.cloud = new THREE.ShaderMaterial({
      vertexShader: CLOUD_VERT,
      fragmentShader: CLOUD_FRAG,
      uniforms: { ...this.shared, uCloud: { value: 0 } },
      transparent: true,
      depthWrite: false,
    });
    const cloudMesh = new THREE.Mesh(new THREE.PlaneGeometry(18, 12), this.cloud);
    cloudMesh.rotation.x = -Math.PI / 2;
    cloudMesh.position.set(haorCentre.x, 0.6, haorCentre.z);
    this.scene.add(cloudMesh);
    this.track(cloudMesh.geometry, this.cloud);

    this.setLadder(36.18, [40.78, 51.16, 59.2, 65.66, 77.67]);
    this.refreshLabels();
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas.parentElement ?? canvas);
    this.resize();
    this.fadeIn.start = performance.now();
    this.raf = requestAnimationFrame(this.frame);
  }

  private track(...items: { dispose: () => void }[]) {
    this.disposables.push(...items);
  }

  /** Scroll progress in chapters, e.g. 2.4 = 40% through the road chapter. */
  setProgress(p: number): void {
    this.targetP = Math.min(CHAPTER_COUNT - 0.001, Math.max(0, p));
  }

  setRouteMode(mode: RouteMode): void {
    this.routeMode = mode;
  }

  setTierFocus(index: number | null): void {
    this.tierFocus = index;
  }

  /** Radar divider, as a fraction of the canvas width (0 = all radar, 1 = all optical). */
  setRadar(x: number, on = true): void {
    this.shared.uRadarX.value = clamp01(x);
    this.radarOn = on;
  }

  setFlood(level: number): void {
    this.ground.uniforms.uFlood.value = clamp01(level);
  }

  /** Move the cold-storage still to a district's facilities. */
  setColdDistrict(district: FacilitySeed["district"]): void {
    this.poses[1] = coldPose(district);
  }

  /** Hero subject: another farmer's place, or Rahim's plot when `null`. */
  setHeroPlace(at: LatLon | null): void {
    const target = at ?? PLACES.rahimPlot;
    this.poses[0] = { ...this.poses[0], at: target };
    const p = project(target);
    (this.ground.uniforms.uPlot.value as THREE.Vector2).set(p.x, p.z);
  }

  /** Price posts along the road: farm gate, then each trader's selling price (Tk/kg). */
  setLadder(grower: number, sells: number[]): void {
    for (const child of [...this.posts.children]) {
      this.posts.remove(child);
      const mesh = child as THREE.Mesh;
      mesh.geometry.dispose();
      (mesh.material as THREE.Material).dispose();
    }
    const scale = 0.012;
    const stops: { at: THREE.Vector3; price: number; tone: THREE.Color }[] = [
      { at: this.route.getPointAt(0), price: grower, tone: HUSK },
      ...TIER_STOPS.map((stop, i) => ({
        at: typeof stop.at === "number" ? this.route.getPointAt(stop.at) : vec3Of(stop.at),
        price: sells[i] ?? grower,
        tone: RED,
      })),
    ];
    stops.forEach((stop, i) => {
      const height = stop.price * scale;
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, height, 8), new THREE.MeshBasicMaterial({ color: stop.tone, transparent: true }));
      stem.position.set(stop.at.x, height / 2, stop.at.z);
      stem.userData = { index: i - 1 };
      const cap = new THREE.Mesh(new THREE.SphereGeometry(0.036, 16, 12), new THREE.MeshBasicMaterial({ color: stop.tone, transparent: true }));
      cap.position.set(stop.at.x, height, stop.at.z);
      cap.userData = { index: i - 1, cap: true };
      this.posts.add(stem, cap);
    });
  }

  /** Re-read the HTML labels after React re-renders them. */
  refreshLabels(): void {
    this.labels = Array.from(this.labelsRoot.querySelectorAll<HTMLElement>("[data-lat]"));
    this.labelWidths = this.labels.map((el) => (el.firstElementChild as HTMLElement | null)?.offsetWidth ?? 0);
  }

  private resize(): void {
    const parent = this.canvas.parentElement ?? this.canvas;
    const width = Math.max(1, parent.clientWidth);
    const height = Math.max(1, parent.clientHeight);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.getDrawingBufferSize(this.shared.uResolution.value);
    this.lateralShift = width >= 900 && width / height > 1.2 ? 0.4 : 0;
  }

  private chapterWeight(p: number, chapters: number[]): number {
    return Math.max(...chapters.map((c) => smoothstep(c - 0.45, c - 0.05, p) * (1 - smoothstep(c + 0.75, c + 1.0, p))));
  }

  private poseAt(p: number): Pose {
    const k = Math.min(CHAPTER_COUNT - 1, Math.floor(p));
    const f = p - k;
    // In the road chapter the camera follows the truck; arriving there it starts at the farm gate.
    const a = k === 2 ? { ...this.poses[2], at: this.routeLatLon(this.roadT(p)) } : this.poses[k];
    if (k >= CHAPTER_COUNT - 1) return a;
    const b = k + 1 === 2 ? { ...this.poses[2], at: this.routeLatLon(0) } : this.poses[k + 1];
    return mixPose(a, b, smoothstep(0.6, 1, f));
  }

  private roadT(p: number): number {
    if (p < 2) return 0;
    if (p >= 3) return 1;
    return clamp01((p - 2) / 0.62);
  }

  /** A point along the road to Dhaka, 0 at the farm gate and 1 at Karwan Bazar. */
  routeLatLon(t: number): LatLon {
    const point = this.route.getPointAt(clamp01(t));
    return unproject(point.x, point.z);
  }

  private placeCamera(pose: Pose): void {
    const subject = project(pose.at);
    const pitch = THREE.MathUtils.degToRad(pose.pitch);
    const yaw = THREE.MathUtils.degToRad(pose.yaw);
    const halfWidth = pose.dist * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)) * this.camera.aspect;
    const right = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
    const look = new THREE.Vector3(subject.x, 0, subject.z).addScaledVector(right, -this.lateralShift * halfWidth);
    this.camera.position.set(
      look.x + pose.dist * Math.cos(pitch) * Math.sin(yaw),
      pose.dist * Math.sin(pitch),
      look.z + pose.dist * Math.cos(pitch) * Math.cos(yaw),
    );
    this.camera.lookAt(look);
    this.shared.uFogDensity.value = 0.55 / pose.dist;
  }

  private apply(p: number): void {
    const pose = this.poseAt(p);
    this.placeCamera(pose);

    const dawn = smoothstep(4.6, 6.3, p);
    this.shared.uDawn.value = dawn;
    const fog = NIGHT.clone().lerp(DAWN, dawn);
    fog.getRGB(this.srgb, THREE.SRGBColorSpace);
    this.shared.uFogColor.value.set(this.srgb.r, this.srgb.g, this.srgb.b);
    this.renderer.setClearColor(fog);

    this.ground.uniforms.uPlotGlow.value = this.chapterWeight(p, [0, 3, 6]);
    const pooled = this.routeMode === "pooled";
    const roadT = this.roadT(p);
    this.road.uniforms.uVisible.value = smoothstep(1.4, 1.9, p) * (1 - smoothstep(3.75, 4.2, p));
    this.road.uniforms.uProgress.value = roadT;
    this.road.uniforms.uMode.value = pooled ? 1 : 0;

    const truckWeight = smoothstep(1.7, 2.0, p) * (1 - smoothstep(3.75, 4.1, p));
    this.truck.position.copy(this.route.getPointAt(roadT)).setY(0.09);
    const truckMaterial = this.truck.material as THREE.SpriteMaterial;
    truckMaterial.opacity = truckWeight;
    truckMaterial.color.copy(pooled ? MUSTARD : RED);

    const postWeight = smoothstep(1.6, 2.0, p) * (1 - smoothstep(3.75, 4.1, p));
    for (const child of this.posts.children) {
      const mesh = child as THREE.Mesh;
      const index = mesh.userData.index as number;
      const focused = this.tierFocus === null || this.tierFocus === index || index < 0;
      const material = mesh.material as THREE.MeshBasicMaterial;
      material.opacity = postWeight * (pooled ? 0.22 : focused ? 1 : 0.3);
      mesh.visible = material.opacity > 0.01;
      if (mesh.userData.cap) mesh.scale.setScalar(this.tierFocus === index && !pooled ? 1.6 : 1);
    }

    // Cold stores belong to chapter 1: they arrive after the hero and leave before the road, where they would read as price posts.
    const coldWeight = this.chapterWeight(p, [1]);
    const blockWeight = smoothstep(0.55, 0.95, p) * (1 - smoothstep(1.6, 2.0, p));
    this.blockMaterials.forEach((m) => {
      m.emissiveIntensity = 0.2 + coldWeight * 0.55;
      m.opacity = blockWeight;
    });
    this.blocks.forEach((b) => {
      b.visible = blockWeight > 0.01;
    });

    const haorWeight = smoothstep(3.55, 3.95, p) * (1 - smoothstep(4.65, 4.95, p));
    this.cloud.uniforms.uCloud.value = haorWeight;
    this.shared.uSarMix.value = this.radarOn ? haorWeight : 0;

    this.positionLabels(Math.min(CHAPTER_COUNT - 1, Math.floor(p + 0.2)));
    this.reportPlace(pose.at);
  }

  private positionLabels(active: number): void {
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;
    const v = new THREE.Vector3();
    // Keep labels clear of the chapter rail (shown from 1024 px) or the screen edge, and lift any that land on another.
    const edge = width >= 1024 ? 72 : 16;
    const placed: { x0: number; x1: number; y0: number; y1: number }[] = [];
    this.labels.forEach((el, i) => {
      const chapters = (el.dataset.ch ?? "").split(" ").map(Number);
      const show = chapters.includes(active);
      if (el.dataset.follow === "truck") v.copy(this.truck.position).setY(0.16);
      else v.copy(vec3Of({ lat: Number(el.dataset.lat), lon: Number(el.dataset.lon) }, Number(el.dataset.alt ?? 0)));
      v.project(this.camera);
      const inView = v.z < 1 && Math.abs(v.x) < 1.05 && Math.abs(v.y) < 1.05;
      const x = (v.x * 0.5 + 0.5) * width;
      let y = (-v.y * 0.5 + 0.5) * height;
      const w = this.labelWidths[i] ?? 0;
      const side = x + w > width - edge ? "left" : "right";
      let visible = show && inView;
      if (visible) {
        const x0 = side === "left" ? x - w : x;
        for (let pass = 0; pass < 4; pass++) {
          const hit = placed.find((r) => x0 < r.x1 && x0 + w > r.x0 && y - 11 < r.y1 && y + 11 > r.y0);
          if (!hit) break;
          // A phone has no room to stack labels: the later one in the list gives way.
          if (width < 640) {
            visible = false;
            break;
          }
          y = hit.y0 - 12;
        }
        if (visible) placed.push({ x0, x1: x0 + w, y0: y - 11, y1: y + 11 });
      }
      el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
      el.dataset.visible = visible ? "true" : "false";
      if (el.dataset.side !== side) el.dataset.side = side;
    });
  }

  private reportPlace(at: LatLon): void {
    if (!this.onPlace) return;
    const now = performance.now();
    if (now - this.lastPlaceAt < 150) return;
    const text = formatLatLon(at);
    if (text !== this.lastPlace) {
      this.lastPlace = text;
      this.onPlace(text);
    }
    this.lastPlaceAt = now;
  }

  private frame = (now: number): void => {
    this.raf = requestAnimationFrame(this.frame);
    if (document.hidden) return;
    const dt = Math.min(0.05, (now - (this.lastFrame || now)) / 1000);
    this.lastFrame = now;
    if (this.reduced) {
      // Stills only: jump to the chapter being read, no drift.
      this.smoothP = Math.min(CHAPTER_COUNT - 1, Math.floor(this.targetP + 0.2)) + 0.3;
    } else {
      this.shared.uTime.value += dt;
      this.smoothP += (this.targetP - this.smoothP) * (1 - Math.exp(-dt * 5));
    }
    this.apply(this.smoothP);
    this.canvas.style.opacity = this.reduced ? "1" : String(smoothstep(0, 1600, now - this.fadeIn.start));
    this.renderer.render(this.scene, this.camera);
  };

  dispose(): void {
    cancelAnimationFrame(this.raf);
    this.resizeObserver.disconnect();
    for (const child of [...this.posts.children]) {
      const mesh = child as THREE.Mesh;
      mesh.geometry.dispose();
      (mesh.material as THREE.Material).dispose();
    }
    this.disposables.forEach((d) => d.dispose());
    this.blocks.forEach((b) => b.dispose());
    this.renderer.dispose();
  }
}
