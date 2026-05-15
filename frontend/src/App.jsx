import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  Cpu,
  Fan,
  Flame,
  Pause,
  Play,
  Server,
  ShieldCheck,
  Thermometer,
  Zap
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

const API_BASE = "http://localhost:5002";
const MAX_POINTS = 90;

const initialState = {
  temperature: 0,
  workload: 0,
  cooling: 0,
  mode: "AI",
  status: "SAFE",
  rack_status: "SAFE",
  control_phase: "Holding",
  smoothed_temperature: null,
  target_temperature: 25,
  deadband: 1,
  hold_steps_remaining: 0,
  hottest_rack: null,
  racks: []
};

const statusTone = {
  SAFE: {
    text: "text-emerald-200",
    border: "border-emerald-400/35",
    bg: "bg-emerald-400/12",
    fill: "#34d399"
  },
  WARNING: {
    text: "text-amber-200",
    border: "border-amber-400/40",
    bg: "bg-amber-400/14",
    fill: "#f59e0b"
  },
  CRITICAL: {
    text: "text-rose-200",
    border: "border-rose-400/45",
    bg: "bg-rose-400/16",
    fill: "#fb7185"
  }
};

const phaseTone = {
  Holding: "border-cyan-300/35 bg-cyan-300/10 text-cyan-100",
  Stabilizing: "border-lime-300/35 bg-lime-300/10 text-lime-100",
  Correcting: "border-amber-300/45 bg-amber-300/12 text-amber-100",
  Steady: "border-indigo-300/40 bg-indigo-300/12 text-indigo-100"
};

function App() {
  const [state, setState] = useState(initialState);
  const [view, setView] = useState("simple");
  const [running, setRunning] = useState(true);
  const [series, setSeries] = useState([]);
  const [logs, setLogs] = useState([]);
  const [currentAction, setCurrentAction] = useState(0);
  const [selectedRackId, setSelectedRackId] = useState(null);
  const tickRef = useRef(0);

  const selectedRack = useMemo(() => {
    if (!state.racks.length) return null;
    return (
      state.racks.find((rack) => rack.id === selectedRackId) ||
      state.hottest_rack ||
      state.racks[0]
    );
  }, [selectedRackId, state.hottest_rack, state.racks]);

  const pushLog = useCallback((message, level = "info") => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((items) =>
      [{ id: `${Date.now()}-${Math.random()}`, timestamp, message, level }, ...items].slice(
        0,
        18
      )
    );
  }, []);

  const recordPoint = useCallback((nextState, action, safeAction) => {
    tickRef.current += 1;
    setSeries((points) =>
      [
        ...points,
        {
          tick: tickRef.current,
          time: new Date().toLocaleTimeString([], {
            minute: "2-digit",
            second: "2-digit"
          }),
          avgTemp: nextState.temperature,
          rawHottest: nextState.hottest_rack?.temperature ?? nextState.temperature,
          smoothed: nextState.smoothed_temperature ?? nextState.temperature,
          cooling: nextState.cooling,
          workload: nextState.workload,
          action,
          safeAction
        }
      ].slice(-MAX_POINTS)
    );
  }, []);

  const fetchState = useCallback(async () => {
    const response = await fetch(`${API_BASE}/state`);
    const nextState = await response.json();
    setState(nextState);
    setSelectedRackId((id) => id || nextState.hottest_rack?.id || null);
    recordPoint(nextState, currentAction, currentAction);
  }, [currentAction, recordPoint]);

  const runStep = useCallback(async () => {
    const response = await fetch(`${API_BASE}/step`, { method: "POST" });
    const result = await response.json();
    setState(result.state);
    setCurrentAction(result.safe_action);
    setSelectedRackId((id) => id || result.state.hottest_rack?.id || null);
    recordPoint(result.state, result.action, result.safe_action);

    if (result.action !== result.safe_action) {
      pushLog(
        `Safety trigger: ${actionLabel(result.action)} adjusted to ${actionLabel(result.safe_action)}`,
        "warn"
      );
      return;
    }

    const rack = result.state.hottest_rack;
    if (result.state.rack_status === "CRITICAL") {
      pushLog(`${rack.id} critical at ${rack.temperature.toFixed(2)} C`, "critical");
      return;
    }

    pushLog(result.decision || `${result.state.control_phase}: ${actionLabel(result.safe_action)}`);
  }, [pushLog, recordPoint]);

  const setMode = async (mode) => {
    const response = await fetch(`${API_BASE}/mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode })
    });
    const nextState = await response.json();
    setState(nextState);
    setCurrentAction(0);
    pushLog(`Control mode switched to ${mode}`);
  };

  useEffect(() => {
    fetchState().catch(() => pushLog("V3 API unavailable on port 5002", "critical"));
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const task = running ? runStep : fetchState;
      task().catch(() => pushLog("Control loop request failed", "critical"));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [fetchState, pushLog, runStep, running]);

  return (
    <main className="min-h-screen bg-[#081014] px-4 py-5 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-5">
        {view === "simple" ? (
          <SimpleView
            state={state}
            running={running}
            logs={logs}
            onDetails={() => setView("detailed")}
          />
        ) : (
          <DetailedView
            state={state}
            running={running}
            currentAction={currentAction}
            selectedRack={selectedRack}
            selectedRackId={selectedRack?.id}
            series={series}
            logs={logs}
            onBack={() => setView("simple")}
            onMode={setMode}
            onToggle={() => {
              setRunning((value) => !value);
              pushLog(running ? "Simulation stopped" : "Simulation started");
            }}
            onSelectRack={setSelectedRackId}
          />
        )}
      </div>
    </main>
  );
}

function SimpleView({ state, running, logs, onDetails }) {
  return (
    <section className="grid min-h-[calc(100vh-2.5rem)] place-items-center">
      <MotionStyles />
      <div className="w-full max-w-5xl">
        <InteractiveCard className="relative overflow-hidden rounded-md border border-slate-700/80 bg-[#0d171d] p-6 shadow-2xl shadow-black/35 sm:p-8">
          <SystemActivityBar running={running} />
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-200">
                AI Cooling Command Center
              </p>
              <h1 className="mt-3 text-3xl font-semibold text-white sm:text-5xl">
                Data Center Cooling Overview
              </h1>
            </div>
            <div className="flex flex-wrap gap-3">
              <PhasePill phase={state.control_phase} />
              <StatusPill status={state.rack_status || state.status} />
            </div>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <OverviewMetric icon={Thermometer} label="Current Temperature">
              <AnimatedValue value={state.temperature} decimals={2} suffix=" C" />
            </OverviewMetric>
            <OverviewMetric icon={Fan} label="Cooling Level">
              <AnimatedValue value={state.cooling} decimals={1} suffix="%" />
            </OverviewMetric>
            <OverviewMetric icon={ShieldCheck} label="System Status" value={state.rack_status || state.status} />
            <OverviewMetric icon={Activity} label="Mode" value={state.mode} />
          </div>

          <MiniActivityLog logs={logs} />

          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-slate-400">
              Loop {running ? "live" : "paused"} | Target {state.target_temperature?.toFixed?.(1) ?? "25.0"} C | Deadband +/-{state.deadband?.toFixed?.(1) ?? "1.0"} C
            </div>
            <motion.button
              onClick={onDetails}
              whileHover={{ scale: 1.025, boxShadow: "0 18px 42px rgba(103, 232, 249, 0.16)" }}
              whileTap={{ scale: 0.985 }}
              transition={{ type: "spring", stiffness: 360, damping: 26 }}
              className="inline-flex items-center justify-center gap-2 rounded-md bg-white px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100"
            >
              <BarChart3 className="h-4 w-4" />
              View Detailed Analytics
            </motion.button>
          </div>
        </InteractiveCard>
      </div>
    </section>
  );
}

function DetailedView({
  state,
  running,
  currentAction,
  selectedRack,
  selectedRackId,
  series,
  logs,
  onBack,
  onMode,
  onToggle,
  onSelectRack
}) {
  return (
    <>
      <Header state={state} running={running} onBack={onBack} />

      <section className="grid gap-5 xl:grid-cols-[360px_1fr_390px]">
        <ControlColumn
          state={state}
          running={running}
          currentAction={currentAction}
          selectedRack={selectedRack}
          onMode={onMode}
          onToggle={onToggle}
        />

        <section className="grid gap-5">
          <RackWall
            racks={state.racks}
            selectedRackId={selectedRackId}
            hottestRackId={state.hottest_rack?.id}
            onSelect={onSelectRack}
          />
          <TrendDeck series={series} />
        </section>

        <section className="grid gap-5">
          <RackInspector rack={selectedRack} hottestRack={state.hottest_rack} />
          <LoadChart racks={state.racks} />
          <LogsPanel logs={logs} />
        </section>
      </section>
    </>
  );
}

function Header({ state, running, onBack }) {
  return (
    <header className="relative overflow-hidden rounded-md border border-slate-700/70 bg-[#0d171d] p-4 shadow-2xl shadow-black/25">
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-cyan-300 via-lime-300 to-rose-300" />
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="flex h-10 w-10 items-center justify-center rounded-md border border-slate-700 bg-[#081014] text-slate-300 transition hover:text-white"
            title="Back"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="relative flex h-12 w-12 items-center justify-center rounded-md border border-cyan-300/35 bg-cyan-300/10">
            <Server className="h-6 w-6 text-cyan-200" />
            <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-lime-300 shadow-[0_0_16px_#bef264]" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-200">
              Detailed Analytics
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-white sm:text-3xl">
              AI Cooling Command Center
            </h1>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <HeaderPill label="Loop" value={running ? "Live" : "Paused"} tone={running ? "lime" : "slate"} />
          <HeaderPill label="Mode" value={state.mode} tone="cyan" />
          <PhasePill phase={state.control_phase} />
          <StatusPill status={state.rack_status || state.status} />
        </div>
      </div>
    </header>
  );
}

function ControlColumn({ state, running, currentAction, selectedRack, onMode, onToggle }) {
  return (
    <aside className="grid gap-5">
      <Panel>
        <PanelTitle icon={Fan} title="Cooling Control" />
        <div className="mt-4 grid grid-cols-2 gap-2 rounded-md border border-slate-700 bg-[#081014] p-1">
          {["AI", "BASELINE"].map((mode) => (
            <button
              key={mode}
              className={`rounded px-3 py-2 text-sm font-semibold transition ${
                state.mode === mode
                  ? "bg-cyan-300 text-slate-950 shadow-[0_0_22px_rgba(103,232,249,0.28)]"
                  : "text-slate-400 hover:text-white"
              }`}
              onClick={() => onMode(mode)}
            >
              {mode}
            </button>
          ))}
        </div>

        <button
          onClick={onToggle}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-md bg-white px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-lime-100"
        >
          {running ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          {running ? "Stop Simulation" : "Start Simulation"}
        </button>

        <Airflow currentAction={currentAction} cooling={state.cooling} />
      </Panel>

      <div className="grid gap-3">
        <Metric icon={Thermometer} label="Avg Rack Temp" value={`${state.temperature.toFixed(2)} C`} />
        <Metric icon={Thermometer} label="Smoothed Temp" value={`${(state.smoothed_temperature ?? state.temperature).toFixed(2)} C`} />
        <Metric icon={Flame} label="Hottest Rack" value={state.hottest_rack ? `${state.hottest_rack.id} - ${state.hottest_rack.temperature.toFixed(2)} C` : "Waiting"} />
        <Metric icon={Zap} label="Cooling Level" value={`${state.cooling.toFixed(1)}%`} />
      </div>

      <Panel>
        <PanelTitle icon={ShieldCheck} title="Stability Guard" />
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <Readout label="Target" value={`${state.target_temperature?.toFixed?.(1) ?? "25.0"} C`} />
          <Readout label="Deadband" value={`+/-${state.deadband?.toFixed?.(1) ?? "1.0"} C`} />
          <Readout label="Phase" value={state.control_phase} />
          <Readout label="Hold" value={`${state.hold_steps_remaining ?? 0} cycles`} />
        </div>
      </Panel>

      {selectedRack && (
        <Panel>
          <PanelTitle icon={Server} title="Selected Rack" />
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <Readout label="Rack" value={selectedRack.id} />
            <Readout label="Status" value={selectedRack.status} tone={selectedRack.status} />
            <Readout label="Load" value={`${selectedRack.load.toFixed(1)}%`} />
            <Readout label="Temp" value={`${selectedRack.temperature.toFixed(2)} C`} />
          </div>
        </Panel>
      )}
    </aside>
  );
}

function RackWall({ racks, selectedRackId, hottestRackId, onSelect }) {
  const grouped = useMemo(() => {
    return ["A", "B", "C"].map((row) => racks.filter((rack) => rack.row === row));
  }, [racks]);

  return (
    <Panel className="min-h-[520px]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <PanelTitle icon={Server} title="Rack Thermal Wall" />
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Legend color="#34d399" label="Safe" />
          <Legend color="#f59e0b" label="Warm" />
          <Legend color="#fb7185" label="Hot" />
        </div>
      </div>

      <div className="mt-5 grid gap-4">
        {grouped.map((row, rowIndex) => (
          <div key={rowIndex} className="grid grid-cols-[34px_1fr] items-center gap-3">
            <div className="text-center text-sm font-semibold text-slate-400">Row {["A", "B", "C"][rowIndex]}</div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {row.map((rack) => (
                <RackTile
                  key={rack.id}
                  rack={rack}
                  selected={rack.id === selectedRackId}
                  hottest={rack.id === hottestRackId}
                  onClick={() => onSelect(rack.id)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function RackTile({ rack, selected, hottest, onClick }) {
  const heat = Math.min(1, Math.max(0, (rack.temperature - 22) / 7));
  const borderColor =
    rack.status === "CRITICAL"
      ? "border-rose-300"
      : rack.status === "WARNING"
        ? "border-amber-300"
        : "border-emerald-300/55";
  const heatColor =
    rack.status === "CRITICAL"
      ? "rgba(251,113,133,"
      : rack.status === "WARNING"
        ? "rgba(245,158,11,"
        : "rgba(52,211,153,";

  return (
    <button
      onClick={onClick}
      className={`rack-tile group relative min-h-[128px] overflow-hidden rounded-md border bg-[#0a1318] p-3 text-left transition ${
        selected ? "scale-[1.02] border-cyan-200 shadow-[0_0_28px_rgba(103,232,249,0.18)]" : borderColor
      }`}
    >
      <div
        className="absolute inset-x-0 bottom-0 transition-all duration-500"
        style={{
          height: `${Math.round(18 + heat * 78)}%`,
          background: `${heatColor}${0.18 + heat * 0.36})`
        }}
      />
      <div className="absolute inset-x-2 top-9 grid gap-1">
        {Array.from({ length: 5 }).map((_, index) => (
          <span key={index} className="h-1 rounded-full bg-slate-700/70" />
        ))}
      </div>
      <div className="relative z-10 flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-white">{rack.id}</div>
          <div className="mt-1 text-xs text-slate-400">{rack.status}</div>
        </div>
        {hottest && <Flame className="h-4 w-4 text-rose-300" />}
      </div>
      <div className="relative z-10 mt-12 grid gap-1 text-xs">
        <div className="flex justify-between text-slate-300">
          <span>Temp</span>
          <strong>{rack.temperature.toFixed(1)} C</strong>
        </div>
        <div className="flex justify-between text-slate-300">
          <span>Load</span>
          <strong>{rack.load.toFixed(0)}%</strong>
        </div>
      </div>
    </button>
  );
}

function RackInspector({ rack, hottestRack }) {
  if (!rack) {
    return (
      <Panel>
        <PanelTitle icon={Thermometer} title="Rack Inspector" />
        <p className="mt-4 text-sm text-slate-400">Waiting for rack telemetry</p>
      </Panel>
    );
  }

  const tone = statusTone[rack.status] || statusTone.SAFE;

  return (
    <Panel>
      <div className="flex items-start justify-between gap-3">
        <PanelTitle icon={Thermometer} title="Rack Inspector" />
        <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${tone.bg} ${tone.border} ${tone.text}`}>
          {rack.status}
        </span>
      </div>
      <div className="mt-5 flex items-center justify-between gap-4">
        <div>
          <div className="text-4xl font-semibold text-white">{rack.id}</div>
          <p className="mt-1 text-sm text-slate-400">
            {hottestRack?.id === rack.id ? "Current hottest rack" : "Selected rack telemetry"}
          </p>
        </div>
        <div className="temperature-dial" style={{ "--dial": `${Math.min(100, (rack.temperature / 28) * 100)}%` }}>
          <span>{rack.temperature.toFixed(1)}</span>
          <small>C</small>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3">
        <Readout label="Load" value={`${rack.load.toFixed(1)}%`} />
        <Readout label="Cooling" value={`${rack.cooling_share.toFixed(1)}%`} />
        <Readout label="Position" value={`${rack.row}-${rack.position}`} />
      </div>
    </Panel>
  );
}

function TrendDeck({ series }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Panel className="h-[310px]">
        <PanelTitle icon={Thermometer} title="Temperature vs Time" />
        <ResponsiveContainer width="100%" height="86%">
          <LineChart data={series}>
            <CartesianGrid stroke="#22313a" strokeDasharray="3 3" />
            <XAxis dataKey="time" stroke="#91a4ad" tick={{ fontSize: 11 }} minTickGap={20} />
            <YAxis stroke="#91a4ad" tick={{ fontSize: 11 }} domain={[20, 30]} />
            <Tooltip content={<ChartTooltip />} />
            <Line type="monotone" dataKey="rawHottest" name="Raw hottest" stroke="#fb7185" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="smoothed" name="Smoothed" stroke="#bef264" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="avgTemp" name="Average" stroke="#67e8f9" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <Panel className="h-[310px]">
        <PanelTitle icon={Fan} title="Cooling vs Time" />
        <ResponsiveContainer width="100%" height="86%">
          <AreaChart data={series}>
            <CartesianGrid stroke="#22313a" strokeDasharray="3 3" />
            <XAxis dataKey="time" stroke="#91a4ad" tick={{ fontSize: 11 }} minTickGap={20} />
            <YAxis stroke="#91a4ad" tick={{ fontSize: 11 }} domain={[30, 100]} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="cooling" name="Cooling" stroke="#bef264" fill="#bef264" fillOpacity={0.18} strokeWidth={2} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  );
}

function LoadChart({ racks }) {
  const data = useMemo(() => [...racks].sort((a, b) => b.load - a.load).slice(0, 8), [racks]);

  return (
    <Panel className="h-[260px]">
      <PanelTitle icon={Cpu} title="Rack Load Leaders" />
      <ResponsiveContainer width="100%" height="84%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 12 }}>
          <CartesianGrid stroke="#22313a" strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" stroke="#91a4ad" tick={{ fontSize: 11 }} domain={[0, 100]} />
          <YAxis type="category" dataKey="id" stroke="#91a4ad" tick={{ fontSize: 11 }} width={42} />
          <Tooltip content={<ChartTooltip />} />
          <Bar dataKey="load" radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {data.map((rack) => (
              <Cell key={rack.id} fill={(statusTone[rack.status] || statusTone.SAFE).fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Panel>
  );
}

function LogsPanel({ logs }) {
  return (
    <Panel className="min-h-[260px]">
      <div className="flex items-center justify-between">
        <PanelTitle icon={AlertTriangle} title="System Logs" />
        <span className="text-xs text-slate-500">{logs.length} events</span>
      </div>
      <div className="mt-4 max-h-[205px] overflow-y-auto rounded-md border border-slate-700 bg-[#081014]">
        {logs.length === 0 ? (
          <p className="px-4 py-6 text-sm text-slate-400">Waiting for control decisions</p>
        ) : (
          logs.map((log) => (
            <div key={log.id} className="grid grid-cols-[86px_1fr] border-b border-slate-800 px-3 py-3 last:border-0">
              <span className="text-xs text-slate-500">{log.timestamp}</span>
              <span
                className={`text-sm ${
                  log.level === "critical"
                    ? "text-rose-200"
                    : log.level === "warn"
                      ? "text-amber-200"
                      : "text-slate-200"
                }`}
              >
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>
    </Panel>
  );
}

function Airflow({ currentAction, cooling }) {
  return (
    <div className="mt-5 overflow-hidden rounded-md border border-slate-700 bg-[#081014] p-4">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-400">Cooling path</span>
        <strong className="text-cyan-100">{actionLabel(currentAction)}</strong>
      </div>
      <div className="airflow mt-4" style={{ "--speed": currentAction > 0 ? "1.1s" : "2.4s" }}>
        {Array.from({ length: 6 }).map((_, index) => (
          <span key={index} />
        ))}
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full bg-lime-300 transition-all duration-500" style={{ width: `${cooling}%` }} />
      </div>
    </div>
  );
}

function OverviewMetric({ icon: Icon, label, value, children }) {
  return (
    <InteractiveCard className="rounded-md border border-slate-700 bg-[#081014] p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-slate-400">{label}</p>
        <Icon className="h-5 w-5 text-cyan-200" />
      </div>
      <p className="mt-4 text-3xl font-semibold text-white">{children || value}</p>
    </InteractiveCard>
  );
}

function Metric({ icon: Icon, label, value }) {
  return (
    <Panel>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-400">{label}</p>
          <p className="mt-2 text-xl font-semibold text-white">{value}</p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-700 bg-[#081014]">
          <Icon className="h-4 w-4 text-cyan-200" />
        </div>
      </div>
    </Panel>
  );
}

function Panel({ children, className = "" }) {
  return <section className={`rounded-md border border-slate-700/80 bg-[#0d171d] p-4 shadow-xl shadow-black/20 ${className}`}>{children}</section>;
}

function PanelTitle({ icon: Icon, title }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-4 w-4 text-cyan-200" />
      <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-300">{title}</h2>
    </div>
  );
}

function HeaderPill({ label, value, tone }) {
  const colors = {
    lime: "border-lime-300/35 bg-lime-300/10 text-lime-100",
    cyan: "border-cyan-300/35 bg-cyan-300/10 text-cyan-100",
    slate: "border-slate-600 bg-slate-700/30 text-slate-200"
  };

  return (
    <div className={`flex items-center gap-3 rounded-md border px-3 py-2 ${colors[tone]}`}>
      <span className="text-xs text-slate-400">{label}</span>
      <strong className="text-sm">{value}</strong>
    </div>
  );
}

function StatusPill({ status }) {
  const tone = statusTone[status] || statusTone.SAFE;
  return (
    <div className={`flex items-center gap-2 rounded-md border px-3 py-2 ${tone.bg} ${tone.border} ${tone.text}`}>
      <span className={`status-pulse h-2 w-2 rounded-full bg-current shadow-[0_0_14px_currentColor] status-${String(status).toLowerCase()}`} />
      <strong className="text-sm">{status}</strong>
    </div>
  );
}

function PhasePill({ phase }) {
  return (
    <div className={`flex items-center gap-2 rounded-md border px-3 py-2 ${phaseTone[phase] || phaseTone.Holding}`}>
      <span className="h-2 w-2 rounded-full bg-current shadow-[0_0_14px_currentColor]" />
      <strong className="text-sm">{phase || "Holding"}</strong>
    </div>
  );
}

function Readout({ label, value, tone }) {
  const color = tone ? (statusTone[tone]?.text || "text-white") : "text-white";
  return (
    <div className="rounded-md border border-slate-700 bg-[#081014] p-3">
      <div className="text-xs uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className={`mt-1 text-sm font-semibold ${color}`}>{value}</div>
    </div>
  );
}

function Legend({ color, label }) {
  return (
    <span className="flex items-center gap-1">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-slate-700 bg-[#081014] px-3 py-2 text-xs shadow-xl">
      <div className="mb-1 text-slate-400">{label}</div>
      {payload.map((item) => (
        <div key={item.name} className="flex min-w-[150px] justify-between gap-4">
          <span style={{ color: item.color || item.fill }}>{item.name}</span>
          <strong className="text-white">{Number(item.value).toFixed(2)}</strong>
        </div>
      ))}
    </div>
  );
}

function actionLabel(action) {
  if (action > 0) return `Increase +${Number(action).toFixed(1)}`;
  if (action < 0) return `Reduce ${Number(action).toFixed(1)}`;
  return "Hold";
}

function AnimatedValue({ value, decimals, suffix }) {
  const motionValue = useMotionValue(value || 0);
  const displayValue = useTransform(motionValue, (latest) => `${latest.toFixed(decimals)}${suffix}`);

  useEffect(() => {
    const controls = animate(motionValue, value || 0, {
      duration: 0.7,
      ease: [0.22, 1, 0.36, 1]
    });
    return controls.stop;
  }, [motionValue, value]);

  return <motion.span>{displayValue}</motion.span>;
}

function InteractiveCard({ children, className = "" }) {
  const handleMouseMove = (event) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--cursor-x", `${event.clientX - bounds.left}px`);
    event.currentTarget.style.setProperty("--cursor-y", `${event.clientY - bounds.top}px`);
  };

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      whileHover={{
        scale: 1.025,
        boxShadow: "0 20px 48px rgba(0, 0, 0, 0.34), 0 0 30px rgba(103, 232, 249, 0.08)"
      }}
      transition={{ type: "spring", stiffness: 320, damping: 28 }}
      className={`interactive-card ${className}`}
    >
      <div className="cursor-light" />
      <div className="relative z-10">{children}</div>
    </motion.div>
  );
}

function SystemActivityBar({ running }) {
  return (
    <div className="absolute inset-x-0 top-0 h-1 overflow-hidden bg-slate-800">
      <motion.div
        className="h-full w-1/2 bg-gradient-to-r from-transparent via-cyan-300 to-transparent"
        animate={running ? { x: ["-100%", "220%"] } : { x: "-100%" }}
        transition={{ duration: 2.8, repeat: Infinity, ease: "linear" }}
      />
    </div>
  );
}

function MiniActivityLog({ logs }) {
  const latestLogs = logs.slice(0, 3);

  return (
    <div className="mt-6">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.14em] text-slate-400">
          <AlertTriangle className="h-4 w-4 text-cyan-200" />
          Mini Activity Log
        </div>
        <span className="text-xs text-slate-500">last 3 events</span>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        {latestLogs.length === 0 ? (
          <InteractiveCard className="rounded-md border border-slate-700 bg-[#081014] p-4 lg:col-span-3">
            <p className="text-sm text-slate-400">Waiting for stabilization events</p>
          </InteractiveCard>
        ) : (
          latestLogs.map((log) => (
            <InteractiveCard key={log.id} className="rounded-md border border-slate-700 bg-[#081014] p-4">
              <div className="text-xs text-slate-500">{log.timestamp}</div>
              <div
                className={`mt-2 text-sm ${
                  log.level === "critical"
                    ? "text-rose-200"
                    : log.level === "warn"
                      ? "text-amber-200"
                      : "text-slate-200"
                }`}
              >
                {log.message}
              </div>
            </InteractiveCard>
          ))
        )}
      </div>
    </div>
  );
}

function MotionStyles() {
  return (
    <style>{`
      .interactive-card {
        position: relative;
        transform-origin: center;
        will-change: transform, box-shadow;
      }

      .cursor-light {
        pointer-events: none;
        position: absolute;
        inset: 0;
        z-index: 0;
        opacity: 0;
        transition: opacity 180ms ease;
        background: radial-gradient(
          240px circle at var(--cursor-x, 50%) var(--cursor-y, 50%),
          rgba(103, 232, 249, 0.12),
          transparent 42%
        );
      }

      .interactive-card:hover .cursor-light {
        opacity: 1;
      }

      .status-pulse {
        animation-name: statusPulse;
        animation-timing-function: ease-in-out;
        animation-iteration-count: infinite;
      }

      .status-safe {
        animation-duration: 3.2s;
      }

      .status-warning {
        animation-duration: 1.8s;
      }

      .status-critical {
        animation-duration: 0.9s;
      }

      @keyframes statusPulse {
        0%, 100% {
          opacity: 0.72;
          box-shadow: 0 0 10px currentColor;
        }
        50% {
          opacity: 1;
          box-shadow: 0 0 22px currentColor;
        }
      }
    `}</style>
  );
}

export default App;
