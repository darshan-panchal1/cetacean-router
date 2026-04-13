import { useState, useEffect, useRef, useCallback } from "react";

/* ─── Global styles ─────────────────────────────────────────────── */
const GLOBAL = `
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@300;400;500&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#080b10;--surface:#0d1117;--surface2:#111720;--surface3:#151d28;
  --border:#1a2332;--border2:#1f2d40;--border3:#243348;
  --ocean:#0a4f6e;--ocean-mid:#0e7fa8;--ocean-bright:#14b8e8;--ocean-dim:rgba(20,184,232,.1);--ocean-glow:rgba(20,184,232,.06);
  --whale:#22d3ee;--whale-dim:rgba(34,211,238,.08);
  --alert:#f97316;--alert-dim:rgba(249,115,22,.1);
  --safe:#22c55e;--safe-dim:rgba(34,197,94,.1);
  --warn:#eab308;--warn-dim:rgba(234,179,8,.1);
  --text:#d4e4f0;--text-muted:#4d6880;--text-dim:#243348;
  --sans:'Syne',sans-serif;--mono:'JetBrains Mono',monospace;--serif:'Instrument Serif',Georgia,serif;
  --r:6px;--r-lg:12px;--r-xl:18px;
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.6;min-height:100vh;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(ellipse 80% 60% at 50% -10%,rgba(10,79,110,.18) 0%,transparent 65%),
             radial-gradient(ellipse 40% 40% at 85% 90%,rgba(14,127,168,.06) 0%,transparent 50%);}
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border3);border-radius:2px}
textarea,input,select{font-family:var(--sans)}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes fadeUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes wave{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
@keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}
@keyframes beam{0%{opacity:0;transform:scaleX(0)}100%{opacity:1;transform:scaleX(1)}}
`;
if (!document.getElementById("cr-global")) {
  const s = document.createElement("style");
  s.id = "cr-global"; s.textContent = GLOBAL;
  document.head.appendChild(s);
}

/* ─── Config ─────────────────────────────────────────────────────── */
const RUNPOD_ENDPOINT_ID = import.meta.env.VITE_RUNPOD_ENDPOINT_ID;
const RUNPOD_API_KEY     = import.meta.env.VITE_RUNPOD_API_KEY;
const LOCAL_API_URL      = import.meta.env.VITE_LOCAL_API_URL || "http://localhost:8000";
const USE_RUNPOD         = Boolean(RUNPOD_ENDPOINT_ID && RUNPOD_API_KEY);
const RUNPOD_URL         = `https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync`;

/* ─── Preset routes ──────────────────────────────────────────────── */
const PRESETS = [
  { label: "CA → OR",        desc: "California to Oregon",    start: { latitude: 34.4208, longitude: -119.6982 }, end: { latitude: 45.5152, longitude: -122.6784 } },
  { label: "NY → Lisbon",    desc: "Transatlantic",           start: { latitude: 40.7128, longitude: -74.0060  }, end: { latitude: 38.7223, longitude: -9.1393   } },
  { label: "LA → Honolulu",  desc: "Pacific crossing",        start: { latitude: 33.7701, longitude: -118.1937 }, end: { latitude: 21.3099, longitude: -157.8581  } },
  { label: "Halifax → UK",   desc: "North Atlantic",          start: { latitude: 44.6488, longitude: -63.5752  }, end: { latitude: 50.9097, longitude: -1.4044   } },
];

/* ─── Agent pipeline nodes ───────────────────────────────────────── */
const AGENTS = [
  { id: "navigator", icon: "⊕", label: "Navigator",     sub: "Route calculation"  },
  { id: "biologist", icon: "◎", label: "Biologist",     sub: "OBIS cetacean data" },
  { id: "risk",      icon: "◈", label: "Risk Manager",  sub: "Decision synthesis" },
];

/* ─── Risk badge ─────────────────────────────────────────────────── */
function RiskBadge({ level }) {
  const cfg = {
    LOW:     { bg: "var(--safe-dim)",  border: "rgba(34,197,94,.25)",    color: "var(--safe)",         label: "Low Risk"     },
    MEDIUM:  { bg: "var(--warn-dim)",  border: "rgba(234,179,8,.25)",    color: "var(--warn)",         label: "Medium Risk"  },
    HIGH:    { bg: "var(--alert-dim)", border: "rgba(249,115,22,.3)",    color: "var(--alert)",        label: "High Risk"    },
    UNKNOWN: { bg: "var(--surface2)",  border: "var(--border2)",         color: "var(--text-muted)",   label: "Unknown"      },
  }[level?.toUpperCase()] || { bg: "var(--surface2)", border: "var(--border2)", color: "var(--text-muted)", label: level || "—" };

  return (
    <span style={{ fontFamily: "var(--mono)", fontSize: 11, fontWeight: 500, letterSpacing: ".06em",
                   textTransform: "uppercase", padding: "3px 10px", borderRadius: 20,
                   background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color }}>
      {cfg.label}
    </span>
  );
}

/* ─── Metric card ────────────────────────────────────────────────── */
function Metric({ label, value, unit, sub }) {
  return (
    <div style={{ background: "var(--surface2)", border: "1px solid var(--border2)",
                  borderRadius: "var(--r-lg)", padding: "18px 20px" }}>
      <div style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: ".1em",
                    textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 10 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
        <span style={{ fontFamily: "var(--serif)", fontSize: 28, fontWeight: 400,
                       fontStyle: "italic", color: "var(--ocean-bright)", lineHeight: 1 }}>{value}</span>
        {unit && <span style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text-muted)" }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)", marginTop: 5 }}>{sub}</div>}
    </div>
  );
}

/* ─── Route map SVG ──────────────────────────────────────────────── */
function RouteMap({ routes, selected }) {
  if (!routes?.length) return null;

  const W = 760, H = 200, PAD = 28;
  const allWp = routes.flatMap(r => r.waypoints || []);
  if (!allWp.length) return null;

  const lats = allWp.map(w => w[0]), lons = allWp.map(w => w[1]);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLon = Math.min(...lons), maxLon = Math.max(...lons);
  const latR = maxLat - minLat || 1, lonR = maxLon - minLon || 1;

  const proj = (lat, lon) => [
    PAD + (lon - minLon) / lonR * (W - 2 * PAD),
    PAD + (maxLat - lat) / latR * (H - 2 * PAD),
  ];

  const routeColor = { direct: "#0e7fa8", detour: "var(--whale)", reduced_speed: "var(--warn)" };
  const selectedName = selected?.route_name;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }}>
      <defs>
        <filter id="glow"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      {/* Grid lines */}
      {[0.25, 0.5, 0.75].map(f => (
        <line key={f} x1={PAD + f * (W - 2*PAD)} y1={PAD} x2={PAD + f * (W - 2*PAD)} y2={H - PAD}
              stroke="var(--border)" strokeWidth="1" strokeDasharray="3,6" />
      ))}
      {/* Routes */}
      {routes.map((r, ri) => {
        const wps = r.waypoints || [];
        if (wps.length < 2) return null;
        const pts = wps.map(w => proj(w[0], w[1]));
        const d = "M" + pts.map(p => p.join(",")).join("L");
        const isSelected = r.route_name === selectedName;
        const col = isSelected ? "var(--ocean-bright)" : (routeColor[r.route_type] || "var(--text-muted)");
        return (
          <g key={ri}>
            {isSelected && <path d={d} stroke={col} strokeWidth="6" fill="none" opacity=".12" filter="url(#glow)" />}
            <path d={d} stroke={col} strokeWidth={isSelected ? 2 : 1.5} fill="none"
                  strokeDasharray={isSelected ? "none" : "6,4"} opacity={isSelected ? 1 : 0.45} />
            {pts.map((p, i) => (
              <circle key={i} cx={p[0]} cy={p[1]} r={i === 0 || i === pts.length - 1 ? (isSelected ? 5 : 4) : 3}
                      fill={col} opacity={isSelected ? 1 : 0.5}
                      stroke={isSelected ? "var(--bg)" : "none"} strokeWidth="1.5" />
            ))}
          </g>
        );
      })}
      {/* Legend */}
      {[["Selected", "var(--ocean-bright)", false], ["Detour", "var(--whale)", true], ["Reduced spd", "var(--warn)", true]].map(([l, c, d], i) => (
        <g key={i} transform={`translate(${W - 130},${10 + i * 18})`}>
          <line x1="0" y1="7" x2="18" y2="7" stroke={c} strokeWidth="1.5" strokeDasharray={d ? "4,3" : "none"} />
          <text x="24" y="11" fontSize="10" fontFamily="var(--mono)" fill="var(--text-muted)">{l}</text>
        </g>
      ))}
    </svg>
  );
}

/* ─── Agent node ─────────────────────────────────────────────────── */
function AgentNode({ agent, state = "idle" }) {
  const active = state === "active";
  const done   = state === "done";
  const err    = state === "error";
  const color  = active || done ? "var(--ocean-bright)" : err ? "var(--alert)" : "var(--text-muted)";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 100, gap: 10 }}>
      <div style={{ width: 48, height: 48, borderRadius: 12, position: "relative",
                    background: active ? "var(--ocean-dim)" : done ? "rgba(20,184,232,.06)" : err ? "var(--alert-dim)" : "var(--surface2)",
                    border: `1px solid ${active ? "rgba(20,184,232,.5)" : done ? "rgba(20,184,232,.25)" : err ? "rgba(249,115,22,.3)" : "var(--border2)"}`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 20, color, transition: "all .3s",
                    boxShadow: active ? "0 0 24px rgba(20,184,232,.2)" : "none",
                    animation: active ? "wave 1.4s ease-in-out infinite" : "none" }}>
        {agent.icon}
        {done && (
          <div style={{ position: "absolute", top: -4, right: -4, width: 14, height: 14,
                        borderRadius: "50%", background: "var(--safe)", border: "2px solid var(--bg)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 8, color: "var(--bg)", fontWeight: 700 }}>✓</div>
        )}
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 12, fontWeight: 600, color, letterSpacing: ".03em", transition: "color .3s" }}>{agent.label}</div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>{agent.sub}</div>
      </div>
    </div>
  );
}

function Connector({ lit }) {
  return (
    <div style={{ flex: 1, height: 1, background: lit ? "var(--ocean-bright)" : "var(--border2)",
                  transition: "background .4s", position: "relative", maxWidth: 60, alignSelf: "center",
                  marginBottom: 24 }}>
      <div style={{ position: "absolute", right: -5, top: -4,
                    border: "5px solid transparent",
                    borderLeft: `7px solid ${lit ? "var(--ocean-bright)" : "var(--border2)"}`,
                    transition: "border-left-color .4s" }} />
    </div>
  );
}

/* ─── Log line ───────────────────────────────────────────────────── */
function LogLine({ time, agent, msg }) {
  const cols = { Navigator: "var(--ocean-bright)", Biologist: "var(--safe)", "Risk Manager": "var(--whale)",
                 System: "var(--text-muted)", Error: "var(--alert)" };
  return (
    <div style={{ display: "flex", gap: 10, padding: "5px 0",
                  borderBottom: "1px solid var(--border)", alignItems: "baseline" }}>
      <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)", minWidth: 56, flexShrink: 0 }}>{time}</span>
      <span style={{ fontFamily: "var(--mono)", fontSize: 10, fontWeight: 500, color: cols[agent] || "var(--text-muted)",
                     minWidth: 88, flexShrink: 0 }}>{agent}</span>
      <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5 }}>{msg}</span>
    </div>
  );
}

/* ─── Main App ───────────────────────────────────────────────────── */
export default function App() {
  const [startLat, setStartLat] = useState("34.4208");
  const [startLon, setStartLon] = useState("-119.6982");
  const [endLat,   setEndLat]   = useState("45.5152");
  const [endLon,   setEndLon]   = useState("-122.6784");
  const [maxIter,  setMaxIter]  = useState(3);

  const [loading,    setLoading]    = useState(false);
  const [agentState, setAgentState] = useState({});
  const [status,     setStatus]     = useState({ type: "idle", msg: "Ready — select a preset or enter coordinates." });
  const [logs,       setLogs]       = useState([]);
  const [result,     setResult]     = useState(null);
  const [error,      setError]      = useState(null);
  const [apiHealth,  setApiHealth]  = useState(null);

  const resultsRef = useRef(null);
  const logRef     = useRef(null);
  const timers     = useRef([]);

  /* ─── Health check ─ */
  const checkHealth = useCallback(async () => {
    try {
      if (USE_RUNPOD) {
        const r = await fetch(`https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/health`, {
          headers: { Authorization: `Bearer ${RUNPOD_API_KEY}` },
          signal: AbortSignal.timeout(4000),
        });
        setApiHealth(r.ok);
      } else {
        const r = await fetch(`${LOCAL_API_URL}/health`, { signal: AbortSignal.timeout(3000) });
        setApiHealth(r.ok);
      }
    } catch { setApiHealth(false); }
  }, []);

  useEffect(() => {
    checkHealth();
    const id = setInterval(checkHealth, 20000);
    return () => clearInterval(id);
  }, [checkHealth]);

  /* ─── Helpers ─ */
  const addLog = useCallback((agent, msg) => {
    const time = new Date().toLocaleTimeString("en", { hour12: false });
    setLogs(prev => [...prev.slice(-80), { time, agent, msg }]);
    setTimeout(() => logRef.current?.scrollTo({ top: 9999, behavior: "smooth" }), 30);
  }, []);

  const setPreset = (p) => {
    setStartLat(String(p.start.latitude)); setStartLon(String(p.start.longitude));
    setEndLat(String(p.end.latitude));     setEndLon(String(p.end.longitude));
    setResult(null); setError(null); setLogs([]);
  };

  /* ─── Animation sequence during call ─ */
  const ANIM_STEPS = [
    { delay: 0,    agent: "navigator", msg: "Navigator: Calculating route options…" },
    { delay: 1400, agent: "biologist", msg: "Biologist: Querying OBIS cetacean database…" },
    { delay: 3200, agent: "risk",      msg: "Risk Manager: Evaluating composite scores…" },
  ];

  /* ─── Run optimisation ─ */
  const run = async () => {
    const sLat = parseFloat(startLat), sLon = parseFloat(startLon);
    const eLat = parseFloat(endLat),   eLon = parseFloat(endLon);
    if ([sLat, sLon, eLat, eLon].some(isNaN)) {
      setStatus({ type: "err", msg: "Invalid coordinates — check all four fields." });
      return;
    }

    setLoading(true); setResult(null); setError(null);
    setLogs([]); setAgentState({});
    setStatus({ type: "active", msg: "Initiating 3-agent pipeline…" });
    timers.current.forEach(clearTimeout);

    // Animate agent pipeline
    ANIM_STEPS.forEach(({ delay, agent, msg }) => {
      const t = setTimeout(() => {
        const idx = AGENTS.findIndex(a => a.id === agent);
        setAgentState(AGENTS.reduce((acc, a, i) => ({
          ...acc, [a.id]: i < idx ? "done" : i === idx ? "active" : acc[a.id] || "idle",
        }), {}));
        addLog(["Navigator","Biologist","Risk Manager"][idx], msg.split(": ")[1]);
      }, delay);
      timers.current.push(t);
    });

    try {
      let data;
      if (USE_RUNPOD) {
        // ── RunPod Serverless ──────────────────────────────────────
        addLog("System", `RunPod endpoint: ${RUNPOD_ENDPOINT_ID}`);
        const res = await fetch(RUNPOD_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${RUNPOD_API_KEY}` },
          body: JSON.stringify({
            input: {
              start: { latitude: sLat, longitude: sLon },
              end:   { latitude: eLat, longitude: eLon },
              max_iterations: maxIter,
            },
          }),
        });
        if (!res.ok) throw new Error(`RunPod HTTP ${res.status}: ${res.statusText}`);
        const rpData = await res.json();
        if (rpData.status !== "COMPLETED") throw new Error(`Job ${rpData.status}: ${rpData.error || "unknown"}`);
        data = rpData.output;
        addLog("System", `RunPod job ${rpData.id?.slice(0,8)}… completed in ${rpData.executionTime}ms`);
      } else {
        // ── Local FastAPI ──────────────────────────────────────────
        addLog("System", `API: ${LOCAL_API_URL}/optimize-route`);
        const res = await fetch(`${LOCAL_API_URL}/optimize-route`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            start: { latitude: sLat, longitude: sLon },
            end:   { latitude: eLat, longitude: eLon },
            max_iterations: maxIter,
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        data = await res.json();
      }

      // All agents done
      setAgentState(AGENTS.reduce((a, ag) => ({ ...a, [ag.id]: "done" }), {}));

      const risk = data.risk_assessment || data.risk_assessments?.[data.risk_assessments.length - 1] || {};
      const route = data.selected_route || {};
      const meta  = data.metadata || {};

      addLog("Risk Manager", `Selected: ${route.route_name} (${risk.risk_level} risk)`);
      addLog("System", `${data.approved ? "✓ Approved" : "✗ Not approved"} · ${data.iterations ?? meta.iterations ?? 1} iteration(s) · ${(data.all_routes_considered || []).length} routes evaluated`);

      setStatus({
        type: "ok",
        msg: `Optimisation complete · ${route.route_name} · ${risk.risk_level} risk · ${data.elapsed_seconds ? data.elapsed_seconds + "s" : ""}`,
      });
      setResult({ ...data, _risk: risk, _route: route });
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 150);

    } catch (err) {
      setAgentState(AGENTS.reduce((a, ag) => ({ ...a, [ag.id]: "error" }), {}));
      setStatus({ type: "err", msg: `Error: ${err.message}` });
      setError(err.message);
      addLog("Error", err.message);
    } finally {
      timers.current.forEach(clearTimeout);
      setLoading(false);
    }
  };

  /* ─── Input style ─ */
  const inp = {
    width: "100%", background: "var(--surface2)", border: "1px solid var(--border2)",
    borderRadius: "var(--r)", padding: "10px 14px", color: "var(--text)",
    fontSize: 14, fontFamily: "var(--mono)", outline: "none",
    transition: "border-color .2s",
  };

  const dotColor = { idle: "var(--text-dim)", active: "var(--ocean-bright)", ok: "var(--safe)", err: "var(--alert)" }[status.type];

  return (
    <div style={{ position: "relative", zIndex: 1, minHeight: "100vh" }}>

      {/* ── Header ─────────────────────────────────────────────────── */}
      <header style={{ position: "sticky", top: 0, zIndex: 100,
                       background: "rgba(8,11,16,.85)", backdropFilter: "blur(24px)",
                       borderBottom: "1px solid var(--border)", padding: "0 24px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto", height: 60,
                      display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 34, height: 34, borderRadius: 9,
                          background: "var(--ocean-dim)", border: "1px solid rgba(20,184,232,.2)",
                          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>
              🐋
            </div>
            <div>
              <div style={{ fontFamily: "var(--sans)", fontSize: 15, fontWeight: 700,
                            letterSpacing: ".02em", color: "var(--text)" }}>
                Cetacean Router
              </div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)",
                            letterSpacing: ".12em", textTransform: "uppercase" }}>
                AI-Powered Maritime Routing
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            {/* API status */}
            <div style={{ display: "flex", alignItems: "center", gap: 6,
                          fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-muted)" }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%",
                            background: apiHealth === null ? "var(--text-dim)" : apiHealth ? "var(--safe)" : "var(--alert)",
                            boxShadow: apiHealth ? "0 0 8px rgba(34,197,94,.5)" : "none", transition: "all .3s" }} />
              {USE_RUNPOD ? "RunPod Serverless" : "API"}
            </div>
            {/* OBIS badge */}
            <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-muted)",
                          padding: "3px 10px", borderRadius: 20, background: "var(--surface2)",
                          border: "1px solid var(--border2)" }}>
              OBIS · Live
            </div>
          </div>
        </div>
      </header>

      <div style={{ maxWidth: 960, margin: "0 auto", padding: "0 24px" }}>

        {/* ── Hero ───────────────────────────────────────────────────── */}
        <section style={{ padding: "68px 0 52px", textAlign: "center" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 22,
                        fontFamily: "var(--mono)", fontSize: 11, letterSpacing: ".14em",
                        textTransform: "uppercase", color: "var(--ocean-bright)",
                        padding: "5px 14px", borderRadius: 20,
                        background: "var(--ocean-dim)", border: "1px solid rgba(20,184,232,.2)" }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%",
                          background: "var(--ocean-bright)", animation: "pulse 2s ease-in-out infinite" }} />
            Multi-Agent Route Optimisation
          </div>
          <h1 style={{ fontFamily: "var(--serif)", fontSize: "clamp(38px,5vw,62px)",
                       fontWeight: 400, lineHeight: 1.05, letterSpacing: "-.01em", marginBottom: 20 }}>
            Ship smarter.<br />
            <em style={{ fontStyle: "italic", color: "var(--ocean-bright)" }}>Protect the ocean.</em>
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: 14, fontWeight: 400,
                      maxWidth: 480, margin: "0 auto", lineHeight: 1.75 }}>
            A 3-agent LangGraph system — Navigator, Marine Biologist, Risk Manager — uses
            live OBIS cetacean sighting data to find shipping routes that balance
            delivery efficiency with marine conservation.
          </p>
        </section>

        {/* ── Agent pipeline ─────────────────────────────────────────── */}
        <div style={{ marginBottom: 36, background: "var(--surface)", border: "1px solid var(--border)",
                      borderRadius: "var(--r-xl)", padding: "28px 32px" }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: ".12em",
                        textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 24 }}>
            Agent Pipeline
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 0 }}>
            {AGENTS.map((agent, i) => (
              <div key={agent.id} style={{ display: "flex", alignItems: "center", flex: i < AGENTS.length - 1 ? "1 1 auto" : "none" }}>
                <AgentNode agent={agent} state={agentState[agent.id]} />
                {i < AGENTS.length - 1 && (
                  <Connector lit={agentState[agent.id] === "done" || agentState[AGENTS[i+1]?.id] === "active"} />
                )}
              </div>
            ))}
          </div>
          {/* Status bar */}
          <div style={{ marginTop: 24, padding: "10px 16px",
                        background: "var(--surface2)", borderRadius: "var(--r)",
                        display: "flex", alignItems: "center", gap: 8,
                        fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-muted)" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                          background: dotColor, transition: "background .3s",
                          animation: status.type === "active" ? "pulse .8s ease-in-out infinite" : "none" }} />
            <span style={{ color: status.type === "err" ? "var(--alert)" : status.type === "ok" ? "var(--safe)" : "var(--text-muted)" }}>
              {status.msg}
            </span>
          </div>
        </div>

        {/* ── Input form ─────────────────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
          {/* Origin */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)",
                        borderRadius: "var(--r-xl)", padding: "22px 24px" }}>
            <div style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: ".12em",
                          textTransform: "uppercase", color: "var(--ocean-bright)", marginBottom: 16 }}>
              Origin
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
              <div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)", marginBottom: 6 }}>Latitude</div>
                <input style={inp} value={startLat} onChange={e => setStartLat(e.target.value)} placeholder="34.42" />
              </div>
              <div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)", marginBottom: 6 }}>Longitude</div>
                <input style={inp} value={startLon} onChange={e => setStartLon(e.target.value)} placeholder="-119.70" />
              </div>
            </div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)", marginBottom: 8 }}>Quick presets</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {PRESETS.map(p => (
                <button key={p.label} onClick={() => setPreset(p)}
                  style={{ fontFamily: "var(--mono)", fontSize: 10, padding: "4px 10px", borderRadius: 20,
                           background: "transparent", border: "1px solid var(--border2)",
                           color: "var(--text-muted)", cursor: "pointer", transition: "all .15s", letterSpacing: ".02em" }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(20,184,232,.4)"; e.currentTarget.style.color = "var(--ocean-bright)"; e.currentTarget.style.background = "var(--ocean-dim)"; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border2)"; e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.background = "transparent"; }}
                >{p.label}</button>
              ))}
            </div>
          </div>

          {/* Destination */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)",
                        borderRadius: "var(--r-xl)", padding: "22px 24px" }}>
            <div style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: ".12em",
                          textTransform: "uppercase", color: "var(--ocean-bright)", marginBottom: 16 }}>
              Destination
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
              <div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)", marginBottom: 6 }}>Latitude</div>
                <input style={inp} value={endLat} onChange={e => setEndLat(e.target.value)} placeholder="45.52" />
              </div>
              <div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)", marginBottom: 6 }}>Longitude</div>
                <input style={inp} value={endLon} onChange={e => setEndLon(e.target.value)} placeholder="-122.68" />
              </div>
            </div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-muted)", marginBottom: 8 }}>Max iterations</div>
            <div style={{ display: "flex", gap: 6 }}>
              {[1,2,3,4,5].map(n => (
                <button key={n} onClick={() => setMaxIter(n)}
                  style={{ width: 36, height: 36, borderRadius: "var(--r)", fontFamily: "var(--mono)", fontSize: 13,
                           background: maxIter === n ? "var(--ocean-dim)" : "transparent",
                           border: `1px solid ${maxIter === n ? "rgba(20,184,232,.4)" : "var(--border2)"}`,
                           color: maxIter === n ? "var(--ocean-bright)" : "var(--text-muted)",
                           cursor: "pointer", transition: "all .15s" }}>
                  {n}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Run button */}
        <div style={{ marginBottom: 32, display: "flex", justifyContent: "center" }}>
          <button onClick={run} disabled={loading}
            style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 36px",
                     background: loading ? "var(--surface2)" : "var(--ocean-bright)",
                     border: `1px solid ${loading ? "var(--border2)" : "var(--ocean-bright)"}`,
                     borderRadius: "var(--r-lg)", color: loading ? "var(--text-muted)" : "#050810",
                     fontFamily: "var(--sans)", fontSize: 14, fontWeight: 700, letterSpacing: ".04em",
                     cursor: loading ? "not-allowed" : "pointer", transition: "all .2s" }}
            onMouseEnter={e => { if (!loading) { e.currentTarget.style.background = "#38d6f5"; e.currentTarget.style.boxShadow = "0 0 32px rgba(20,184,232,.35)"; e.currentTarget.style.transform = "translateY(-2px)"; }}}
            onMouseLeave={e => { e.currentTarget.style.background = loading ? "var(--surface2)" : "var(--ocean-bright)"; e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.transform = "none"; }}
          >
            {loading
              ? <div style={{ width: 16, height: 16, border: "2px solid var(--border3)", borderTopColor: "var(--ocean-bright)", borderRadius: "50%", animation: "spin .7s linear infinite" }} />
              : <span style={{ fontSize: 18 }}>⊕</span>}
            <span>{loading ? "Running pipeline…" : "Optimise Route"}</span>
            {!loading && <span style={{ opacity: .6 }}>→</span>}
          </button>
        </div>

        {/* ── Results ────────────────────────────────────────────────── */}
        {(result || error) && (
          <div ref={resultsRef} style={{ animation: "fadeUp .4s ease forwards", marginBottom: 60 }}>

            {error ? (
              <div style={{ background: "var(--alert-dim)", border: "1px solid rgba(249,115,22,.3)",
                            borderRadius: "var(--r-xl)", padding: "24px 28px" }}>
                <div style={{ fontFamily: "var(--serif)", fontSize: 20, color: "var(--alert)", marginBottom: 10, fontStyle: "italic" }}>
                  Pipeline Error
                </div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text-muted)",
                              lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                  {error}{"\n\nVerify: VITE_RUNPOD_ENDPOINT_ID, VITE_RUNPOD_API_KEY (RunPod)\nor VITE_LOCAL_API_URL (local FastAPI)"}
                </div>
              </div>
            ) : result && (() => {
              const route = result._route || {};
              const risk  = result._risk  || {};
              const allRoutes = result.all_routes_considered || [];
              const iters = result.iterations ?? result.metadata?.iterations ?? 1;

              return (
                <>
                  {/* Section heading */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                                marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
                    <div style={{ fontFamily: "var(--serif)", fontSize: 24, fontStyle: "italic",
                                  color: "var(--text)" }}>
                      Routing Decision
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <RiskBadge level={risk.risk_level} />
                      <span style={{ fontFamily: "var(--mono)", fontSize: 11, padding: "3px 10px",
                                     borderRadius: 20, background: result.approved ? "var(--safe-dim)" : "var(--alert-dim)",
                                     border: result.approved ? "1px solid rgba(34,197,94,.25)" : "1px solid rgba(249,115,22,.3)",
                                     color: result.approved ? "var(--safe)" : "var(--alert)" }}>
                        {result.approved ? "✓ Approved" : "✗ Rejected"}
                      </span>
                      <span style={{ fontFamily: "var(--mono)", fontSize: 11, padding: "3px 10px",
                                     borderRadius: 20, background: "var(--surface2)", border: "1px solid var(--border2)",
                                     color: "var(--text-muted)" }}>
                        {iters} iter · {allRoutes.length} routes
                        {result.elapsed_seconds ? ` · ${result.elapsed_seconds}s` : ""}
                      </span>
                    </div>
                  </div>

                  {/* Metrics */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 16 }}>
                    <Metric label="Distance"  value={route.distance_nm}   unit="nm"   sub="Nautical miles" />
                    <Metric label="ETA"        value={route.eta_hours}     unit="h"    sub={`${(route.eta_hours/24).toFixed(1)} days`} />
                    <Metric label="Speed"      value={route.speed_knots}   unit="kn"   sub={route.route_type} />
                    <Metric label="Sightings"  value={risk.sighting_count ?? "—"}       sub={`${(risk.species_list||[]).length} species`} />
                  </div>

                  {/* Map */}
                  <div style={{ background: "var(--surface)", border: "1px solid var(--border)",
                                borderRadius: "var(--r-xl)", overflow: "hidden", marginBottom: 16 }}>
                    <div style={{ padding: "10px 20px", borderBottom: "1px solid var(--border)",
                                  background: "var(--surface2)", fontFamily: "var(--mono)",
                                  fontSize: 10, letterSpacing: ".1em", textTransform: "uppercase",
                                  color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 8 }}>
                      <span>◈</span> Route Visualisation
                    </div>
                    <div style={{ padding: "16px 20px" }}>
                      <RouteMap routes={allRoutes} selected={route} />
                    </div>
                  </div>

                  {/* Rationale + AI analysis */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
                    {[
                      { icon: "◎", title: "Decision Rationale", body: result.decision_rationale },
                      { icon: "⊕", title: "AI Strategic Analysis", body: result.llm_analysis },
                    ].map(({ icon, title, body }) => (
                      <div key={title} style={{ background: "var(--surface)", border: "1px solid var(--border)",
                                                borderRadius: "var(--r-xl)", overflow: "hidden" }}>
                        <div style={{ padding: "10px 18px", borderBottom: "1px solid var(--border)",
                                      background: "var(--surface2)", fontFamily: "var(--mono)",
                                      fontSize: 10, letterSpacing: ".1em", textTransform: "uppercase",
                                      color: "var(--text-muted)", display: "flex", gap: 8 }}>
                          {icon} {title}
                        </div>
                        <div style={{ padding: "18px 20px", fontSize: 13, color: "var(--text-muted)",
                                      lineHeight: 1.75 }}>
                          {body || "—"}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Species list */}
                  {(risk.species_list || []).length > 0 && (
                    <div style={{ background: "var(--surface)", border: "1px solid var(--border)",
                                  borderRadius: "var(--r-xl)", overflow: "hidden", marginBottom: 16 }}>
                      <div style={{ padding: "10px 18px", borderBottom: "1px solid var(--border)",
                                    background: "var(--surface2)", fontFamily: "var(--mono)",
                                    fontSize: 10, letterSpacing: ".1em", textTransform: "uppercase",
                                    color: "var(--text-muted)" }}>
                        ◎ Cetacean Species Detected
                      </div>
                      <div style={{ padding: "16px 20px", display: "flex", flexWrap: "wrap", gap: 8 }}>
                        {risk.species_list.map(s => (
                          <span key={s} style={{ fontFamily: "var(--mono)", fontSize: 11, padding: "4px 12px",
                                                  borderRadius: 20, background: "var(--whale-dim)",
                                                  border: "1px solid rgba(34,211,238,.15)", color: "var(--whale)",
                                                  fontStyle: "italic" }}>
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* All routes table */}
                  {allRoutes.length > 1 && (
                    <div style={{ background: "var(--surface)", border: "1px solid var(--border)",
                                  borderRadius: "var(--r-xl)", overflow: "hidden", marginBottom: 16 }}>
                      <div style={{ padding: "10px 18px", borderBottom: "1px solid var(--border)",
                                    background: "var(--surface2)", fontFamily: "var(--mono)",
                                    fontSize: 10, letterSpacing: ".1em", textTransform: "uppercase",
                                    color: "var(--text-muted)" }}>
                        ⊕ All Routes Evaluated
                      </div>
                      <div style={{ overflowX: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse" }}>
                          <thead>
                            <tr style={{ borderBottom: "1px solid var(--border2)" }}>
                              {["Route","Type","Distance","ETA","Speed","Selected"].map(h => (
                                <th key={h} style={{ padding: "10px 16px", textAlign: "left", fontFamily: "var(--mono)",
                                                     fontSize: 10, letterSpacing: ".08em", textTransform: "uppercase",
                                                     color: "var(--text-muted)", fontWeight: 400 }}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {allRoutes.map((r, i) => {
                              const isSel = r.route_name === route.route_name;
                              return (
                                <tr key={i} style={{ borderBottom: "1px solid var(--border)",
                                                     background: isSel ? "var(--ocean-dim)" : "transparent" }}>
                                  <td style={{ padding: "10px 16px", fontFamily: "var(--mono)", fontSize: 12,
                                               color: isSel ? "var(--ocean-bright)" : "var(--text)", fontWeight: isSel ? 500 : 400 }}>
                                    {r.route_name}
                                  </td>
                                  <td style={{ padding: "10px 16px", fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-muted)" }}>{r.route_type}</td>
                                  <td style={{ padding: "10px 16px", fontFamily: "var(--mono)", fontSize: 12, color: "var(--text)" }}>{r.distance_nm} nm</td>
                                  <td style={{ padding: "10px 16px", fontFamily: "var(--mono)", fontSize: 12, color: "var(--text)" }}>{r.eta_hours} h</td>
                                  <td style={{ padding: "10px 16px", fontFamily: "var(--mono)", fontSize: 12, color: "var(--text)" }}>{r.speed_knots} kn</td>
                                  <td style={{ padding: "10px 16px" }}>
                                    {isSel && <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--ocean-bright)", background: "var(--ocean-dim)", padding: "2px 8px", borderRadius: 10, border: "1px solid rgba(20,184,232,.3)" }}>Selected</span>}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              );
            })()}

            {/* Agent log */}
            {logs.length > 0 && (
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)",
                            borderRadius: "var(--r-xl)", overflow: "hidden", marginBottom: 16 }}>
                <div style={{ padding: "10px 18px", borderBottom: "1px solid var(--border)",
                              background: "var(--surface2)", fontFamily: "var(--mono)",
                              fontSize: 10, letterSpacing: ".1em", textTransform: "uppercase",
                              color: "var(--text-muted)" }}>
                  ◎ Agent Log
                </div>
                <div ref={logRef} style={{ padding: "14px 18px", maxHeight: 180, overflowY: "auto" }}>
                  {logs.map((l, i) => <LogLine key={i} {...l} />)}
                </div>
              </div>
            )}

            {/* Disclaimer */}
            <p style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-dim)",
                        borderLeft: "2px solid var(--border2)", paddingLeft: 12, lineHeight: 1.6 }}>
              ⚠ Route recommendations are advisory only. Always consult official maritime navigation charts,
              current IMO guidelines, and regional whale strike mitigation programmes before voyage planning.
            </p>
          </div>
        )}
      </div>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <footer style={{ borderTop: "1px solid var(--border)", padding: "24px 0",
                       textAlign: "center", fontFamily: "var(--mono)", fontSize: 11,
                       color: "var(--text-dim)", letterSpacing: ".05em" }}>
        <div style={{ maxWidth: 960, margin: "0 auto", padding: "0 24px" }}>
          Cetacean-Aware Logistics Router &nbsp;·&nbsp; LangGraph · Groq · OBIS · RunPod
          &nbsp;·&nbsp; For research and conservation use
        </div>
      </footer>
    </div>
  );
}