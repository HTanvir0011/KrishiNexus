import { CloudRain, Droplets, Gauge, PlugZap, RotateCcw, Thermometer, Warehouse, Wind, Zap } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { api, ApiError } from "../api/client";
import { cn, pct } from "../lib/format";
import { getState, pushAlert, refreshQuota, refreshTelemetry, setState, useAppState } from "../state/store";
import { Badge, Button, Panel, Spinner } from "./ui";

const BAYS = 10;
const LEVELS = 4;
const ROWS = 3;
const TOTAL = BAYS * LEVELS * ROWS;
const SHARES = { trader: 0.45, owner: 0.3232, farmer: 0.2268 };
const NATIONAL_ROT_BASELINE = 9.0;

type SlotKind = "trader" | "owner" | "farmerBooked" | "farmerOpen";

// Same encoding as the story's quota chart: traders slate, plant owners sky, farmers mustard (open = full strength).
const COLORS: Record<SlotKind, number> = {
  trader: 0x5f7468,
  owner: 0x3d6f7b,
  farmerBooked: 0x5f5920,
  farmerOpen: 0xedb723,
};

/** Assign rack slots front-row-first so the smallholder (mustard) share faces the viewer. */
function slotKinds(openShareOfFarmer: number): SlotKind[] {
  const farmer = Math.round(TOTAL * SHARES.farmer);
  const owner = Math.round(TOTAL * SHARES.owner);
  const open = Math.round(farmer * openShareOfFarmer);
  const kinds: SlotKind[] = [
    ...Array<SlotKind>(open).fill("farmerOpen"),
    ...Array<SlotKind>(farmer - open).fill("farmerBooked"),
    ...Array<SlotKind>(owner).fill("owner"),
  ];
  while (kinds.length < TOTAL) kinds.push("trader");
  return kinds;
}

export function ColdStorage3DTwin({ className }: { className?: string }) {
  const mountRef = useRef<HTMLDivElement>(null);
  const telemetry = useAppState((s) => s.telemetry);
  const quota = useAppState((s) => s.quota);
  const alarm = useAppState((s) => s.chamberAlarm);
  const pulse = useAppState((s) => s.reservationPulse);
  const focus = useAppState((s) => s.focusChamber);
  const flood = useAppState((s) => s.floodReport);
  const [busy, setBusy] = useState<"power" | "flood" | "reset" | null>(null);

  const facility = useMemo(() => quota?.facilities.find((f) => f.facility_id === focus.facilityId) ?? quota?.facilities[0], [quota, focus]);
  const openShare = facility && facility.farmer_quota_mt > 0 ? facility.open_smallholder_quota_mt / facility.farmer_quota_mt : 0.33;
  const sceneApi = useRef<{ setAlarm: (on: boolean) => void; pulse: () => void; setKinds: (kinds: SlotKind[]) => void } | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x0a1913, 14, 30);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.set(9.5, 7, 11);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.6;
    controls.maxPolarAngle = Math.PI / 2.05;
    controls.minDistance = 7;
    controls.maxDistance = 22;
    controls.target.set(0, 1.4, 0);

    scene.add(new THREE.HemisphereLight(0xcfe3e8, 0x0e211a, 0.9));
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(6, 10, 6);
    scene.add(key);
    const chamberLight = new THREE.PointLight(0x8bbcc7, 18, 18);
    chamberLight.position.set(0, 4.6, 0);
    scene.add(chamberLight);

    const floor = new THREE.GridHelper(16, 32, 0x21443a, 0x17352a);
    scene.add(floor);
    const walls = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(13, 5, 8)),
      new THREE.LineBasicMaterial({ color: 0x2f5648 }),
    );
    walls.position.y = 2.5;
    scene.add(walls);

    const cube = new THREE.BoxGeometry(0.9, 0.8, 0.9);
    const shelf = new THREE.BoxGeometry(BAYS * 1.1, 0.06, 1.1);
    const shelfMat = new THREE.MeshStandardMaterial({ color: 0x44584d, metalness: 0.6, roughness: 0.5 });
    const meshes: THREE.Mesh<THREE.BoxGeometry, THREE.MeshStandardMaterial>[] = [];
    let index = 0;
    for (let row = 0; row < ROWS; row++) {
      for (let level = 0; level < LEVELS; level++) {
        const plank = new THREE.Mesh(shelf, shelfMat);
        plank.position.set(0, level * 1.05 + 0.03, 2.2 - row * 2.2);
        scene.add(plank);
        for (let bay = 0; bay < BAYS; bay++) {
          const mat = new THREE.MeshStandardMaterial({ color: COLORS.trader, roughness: 0.55, metalness: 0.1 });
          const mesh = new THREE.Mesh(cube, mat);
          mesh.position.set(-((BAYS - 1) * 1.1) / 2 + bay * 1.1, level * 1.05 + 0.48, 2.2 - row * 2.2);
          mesh.userData.index = index++;
          scene.add(mesh);
          meshes.push(mesh);
        }
      }
    }

    let kinds: SlotKind[] = slotKinds(0.33);
    const applyKinds = (next: SlotKind[]) => {
      kinds = next;
      meshes.forEach((mesh, i) => {
        const kind = kinds[i];
        mesh.material.color.setHex(COLORS[kind]);
        mesh.material.emissive.setHex(kind === "farmerOpen" ? 0xb5840b : 0x000000);
        mesh.material.emissiveIntensity = kind === "farmerOpen" ? 0.55 : 0;
      });
    };
    applyKinds(kinds);

    let alarmOn = false;
    let pulseUntil = 0;
    const resize = () => {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      renderer.setSize(width, height, false);
      renderer.domElement.style.width = "100%";
      renderer.domElement.style.height = "100%";
      camera.aspect = width / Math.max(1, height);
      camera.updateProjectionMatrix();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(mount);

    const start = performance.now();
    let raf = 0;
    const tick = () => {
      const t = (performance.now() - start) / 1000;
      controls.update();
      chamberLight.color.setHex(alarmOn ? 0xf42a41 : 0x8bbcc7);
      chamberLight.intensity = alarmOn ? 14 + 10 * Math.abs(Math.sin(t * 4)) : 18;
      const pulsing = performance.now() < pulseUntil;
      meshes.forEach((mesh, i) => {
        if (kinds[i] !== "farmerOpen") return;
        const wave = pulsing ? 0.5 + 0.5 * Math.sin(t * 9 + i * 0.4) : 0.5 + 0.15 * Math.sin(t * 2 + i * 0.3);
        mesh.material.emissiveIntensity = 0.3 + wave * (pulsing ? 1.4 : 0.5);
        mesh.scale.setScalar(pulsing ? 1 + 0.08 * wave : 1);
      });
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();

    sceneApi.current = {
      setAlarm: (on) => { alarmOn = on; },
      pulse: () => { pulseUntil = performance.now() + 2_500; },
      setKinds: applyKinds,
    };

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      controls.dispose();
      meshes.forEach((m) => m.material.dispose());
      cube.dispose();
      shelf.dispose();
      shelfMat.dispose();
      walls.geometry.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      sceneApi.current = null;
    };
  }, []);

  useEffect(() => sceneApi.current?.setKinds(slotKinds(openShare)), [openShare]);
  useEffect(() => sceneApi.current?.setAlarm(alarm), [alarm]);
  useEffect(() => {
    if (pulse > 0) sceneApi.current?.pulse();
  }, [pulse]);

  const simulatePowerCut = async () => {
    setBusy("power");
    try {
      const before = getState().quota?.facilities.find((f) => f.power_status !== "OUTAGE" && f.facility_id !== focus.facilityId);
      const response = await api.simulatePowerCut(focus.facilityId);
      await Promise.all([refreshTelemetry(), refreshQuota()]);
      pushAlert("danger", "Chamber power cut injected", `${response.message} coldchain-iot-mcp now routes smallholder slots to ${before?.name ?? "the next open facility"}.`);
    } catch (error) {
      pushAlert("danger", "Power-cut simulation failed", error instanceof ApiError ? error.message : "Backend unreachable");
    } finally {
      setBusy(null);
    }
  };

  const simulateFlood = async () => {
    setBusy("flood");
    try {
      const injected = await api.simulateFlashFlood("Tahirpur");
      const report = await api.sarFloodCheck();
      setState({ floodReport: report });
      const red = report.voice_alerts.filter((a) => a.alert_level === "RED");
      pushAlert("warn", "Sentinel-1 SAR flash-flood alert", `${injected.message} ${red.length} haor upazilas RED; ${report.early_harvest_dispatches.length} early-harvest truck dispatches; ${report.voice_alerts.reduce((s, a) => s + a.recipients, 0).toLocaleString()} farmers queued for Bangla voice calls.`);
      void api.voiceInteract({ preset_id: "sunamganj_haor_flood", offline_mode: getState().offlineMode }).then((r) => setState({ lastVoice: r.data }));
    } catch (error) {
      pushAlert("danger", "Flood simulation failed", error instanceof ApiError ? error.message : "Backend unreachable");
    } finally {
      setBusy(null);
    }
  };

  const reset = async () => {
    setBusy("reset");
    try {
      await api.clearAnomalies();
      setState({ floodReport: null });
      await Promise.all([refreshTelemetry(), refreshQuota()]);
      pushAlert("success", "Anomalies cleared", "Chamber and haor back to live conditions.");
    } catch (error) {
      pushAlert("danger", "Reset failed", error instanceof ApiError ? error.message : "Backend unreachable");
    } finally {
      setBusy(null);
    }
  };

  const power = telemetry?.power_source;
  return (
    <Panel
      className={className}
      icon={<Warehouse className="size-4 text-emerald-400" />}
      title={`3D Cold-Storage Digital Twin · ${telemetry?.facility_name ?? focus.facilityId} / ${focus.chamberId}`}
      actions={<Badge tone={alarm ? "red" : "emerald"}>{alarm ? "ALARM" : "NOMINAL"}</Badge>}
      bodyClassName="flex flex-col gap-2 p-0"
    >
      <div className="relative h-[300px] min-h-[240px] flex-1 overflow-hidden rounded-t-none">
        <div ref={mountRef} className="absolute inset-0 cursor-grab active:cursor-grabbing" aria-label="Rotatable 3D cold storage racks" />
        <div className={cn("pointer-events-none absolute inset-0 transition-colors", alarm && "bg-red-500/10")} />
        <div className="pointer-events-none absolute left-2 top-2 grid grid-cols-2 gap-1.5 text-[11px] sm:grid-cols-3">
          <TelemetryChip icon={<Thermometer className="size-3" />} label="Temp" alert={(telemetry?.temperature_c ?? 9.5) > 10}
            value={telemetry ? `${telemetry.temperature_f.toFixed(1)}°F / ${telemetry.temperature_c.toFixed(1)}°C` : "…"} />
          <TelemetryChip icon={<Droplets className="size-3" />} label="RH" alert={(telemetry?.relative_humidity_pct ?? 93) > 95}
            value={telemetry ? pct(telemetry.relative_humidity_pct) : "…"} />
          <TelemetryChip icon={<Wind className="size-3" />} label="CO₂" alert={(telemetry?.co2_ppm ?? 0) > 3000}
            value={telemetry ? `${telemetry.co2_ppm.toFixed(0)} ppm` : "…"} />
          <TelemetryChip icon={<PlugZap className="size-3" />} label="Power" alert={power === "OUTAGE"}
            value={power === "DIESEL_GENERATOR" ? "Diesel backup" : power === "OUTAGE" ? "OUTAGE" : power === "GRID" ? "Grid" : "…"} />
          <TelemetryChip icon={<Gauge className="size-3" />} label="Rot risk" alert={(telemetry?.rot_risk_pct ?? 0) > 5}
            value={telemetry ? `${pct(telemetry.rot_risk_pct)} vs ${NATIONAL_ROT_BASELINE}% baseline` : "…"} />
        </div>
        <div className="pointer-events-none absolute bottom-2 left-2 flex flex-wrap gap-1.5 text-[10px]">
          <Legend color="bg-slate-600" label="Trader hoarded 45.0%" />
          <Legend color="bg-sky-600" label="Plant owner 32.32%" />
          <Legend color="bg-mustard-400" label={`Smallholder 22.68% · ${facility ? `${facility.open_smallholder_quota_mt.toFixed(0)} t open` : "open quota"}`} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 border-t border-ink-700 px-3 py-2">
        <Button variant="danger" onClick={simulatePowerCut} disabled={busy !== null}>
          {busy === "power" ? <Spinner /> : <Zap className="size-3.5" />} Simulate Chamber Power Cut / Humidity Spike
        </Button>
        <Button variant="amber" onClick={simulateFlood} disabled={busy !== null}>
          {busy === "flood" ? <Spinner /> : <CloudRain className="size-3.5" />} Simulate Sunamganj Haor 72h Flash Flood
        </Button>
        <Button onClick={reset} disabled={busy !== null}>
          {busy === "reset" ? <Spinner /> : <RotateCcw className="size-3.5" />} Clear
        </Button>
        {flood && (
          <span className="text-[11px] text-amber-200">
            Haor: {flood.rows.filter((r) => r.alert_level === "RED").length} RED · {flood.early_harvest_dispatches.length} harvest dispatches
          </span>
        )}
      </div>
    </Panel>
  );
}

function TelemetryChip({ icon, label, value, alert }: { icon: ReactNode; label: string; value: string; alert: boolean }) {
  return (
    <div className={cn("rounded-md px-2 py-1 backdrop-blur-sm ring-1",
      alert ? "bg-red-950/70 text-red-200 ring-red-500/50" : "bg-black/50 text-slate-200 ring-white/10")}>
      <div className="flex items-center gap-1 label text-[11px] text-slate-400">{icon}{label}</div>
      <div className="font-mono font-semibold">{value}</div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1 rounded bg-black/50 px-1.5 py-0.5 text-slate-200 backdrop-blur-sm">
      <span className={cn("size-2.5 rounded-sm", color)} /> {label}
    </span>
  );
}
