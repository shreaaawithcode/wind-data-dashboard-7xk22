import { useEffect, useMemo, useState } from "react";
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "./api.js";

const fmt = (v, d = 0) => (v == null ? "–" : Number(v).toLocaleString("en-GB", { maximumFractionDigits: d }));
const londonTime = (iso) =>
  new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
const londonStamp = (iso) =>
  new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/London" });

function Kpi({ label, value, unit, hint }) {
  return (
    <div className="kpi" title={hint}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}<span className="kpi-unit">{unit}</span></div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  );
}

function Card({ title, sub, children }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {sub && <p className="sub">{sub}</p>}
      {children}
    </section>
  );
}

export default function App() {
  const [cfg, setCfg] = useState(null);
  const [cutoff, setCutoff] = useState("09:00");
  const [date, setDate] = useState("");
  const [day, setDay] = useState(null);
  const [met, setMet] = useState(null);
  const [hor, setHor] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.config().then((c) => { setCfg(c); setCutoff(c.default_cutoff); setDate(c.first_delivery); }).catch((e) => setErr(e.message));
    api.horizon().then((h) => setHor(h.buckets)).catch((e) => setErr(e.message));
  }, []);

  useEffect(() => {
    if (!cfg) return;
    api.metrics(cutoff).then(setMet).catch((e) => setErr(e.message));
  }, [cfg, cutoff]);

  useEffect(() => {
    if (!cfg || !date) return;
    setDay(null);
    api.forecast(date, cutoff).then(setDay).catch((e) => setErr(e.message));
  }, [cfg, date, cutoff]);

  const series = useMemo(
    () => (day?.points ?? []).map((p) => ({
      ...p, time: londonTime(p.t),
      band: p.lower != null && p.upper != null ? [p.lower, p.upper] : null,
    })),
    [day],
  );

  if (err) return <div className="page"><div className="banner warn">Could not load data: {err}</div></div>;
  if (!cfg) return <div className="page">Loading…</div>;

  const o = met?.overall;
  const s = day?.summary;

  return (
    <div className="page">
      <header>
        <div>
          <h1>Wind Forecast Desk</h1>
          <p className="lede">
            GB national wind generation: what the day-ahead buyer could see at decision time, and how far off it has been.
          </p>
        </div>
        <div className="controls">
          <label>Delivery day
            <input type="date" min={cfg.first_delivery} max={cfg.last_delivery} value={date}
              onChange={(e) => e.target.value && setDate(e.target.value)} />
          </label>
          <label>Decision cutoff (D-1, London)
            <input type="time" value={cutoff} onChange={(e) => e.target.value && setCutoff(e.target.value)} />
          </label>
        </div>
      </header>

      {cfg.data_source === "synthetic" && (
        <div className="banner warn">Synthetic demo data – not real Elexon figures.</div>
      )}

      <Card
        title={`Forecast available for ${date}`}
        sub={day?.latest_publish
          ? `Decision at ${cutoff} on the previous day. Latest forecast used was published ${londonStamp(day.latest_publish)}. Shaded band = range the actual fell in 90% of the time over January.`
          : "Loading…"}
      >
        <div className="kpis">
          <Kpi label="Forecast wind energy" value={fmt(day?.forecast_mwh)} unit=" MWh" hint="Sum of forecast MW × 0.5 h" />
          <Kpi label="Day MAE" value={fmt(s?.mae)} unit=" MW" hint="Mean absolute error that day" />
          <Kpi label="Day bias" value={fmt(s?.bias)} unit=" MW" hint="Forecast − actual; + means over-forecast" />
          <Kpi label="Peak forecast" value={fmt(Math.max(0, ...series.map((p) => p.forecast ?? 0)))} unit=" MW" />
        </div>
        <ResponsiveContainer width="100%" height={340}>
          <ComposedChart data={series} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
            <XAxis dataKey="time" interval={5} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} width={56} unit=" MW" />
            <Tooltip formatter={(v) => (Array.isArray(v) ? `${fmt(v[0])}–${fmt(v[1])} MW` : `${fmt(v)} MW`)} />
            <Legend />
            <Area dataKey="band" name="90% range" stroke="none" fill="var(--band)" fillOpacity={0.5} isAnimationActive={false} />
            <Line dataKey="forecast" name="Forecast (at cutoff)" stroke="var(--forecast)" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line dataKey="actual" name="Actual" stroke="var(--actual)" strokeWidth={2} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      <Card title="How accurate has it been?" sub={`January 2026 decisions, cutoff ${cutoff}. Error = forecast − actual.`}>
        <div className="kpis">
          <Kpi label="MAE" value={fmt(o?.mae)} unit=" MW" hint="Typical miss size" />
          <Kpi label="RMSE" value={fmt(o?.rmse)} unit=" MW" hint="Penalises big misses" />
          <Kpi label="Bias" value={fmt(o?.bias)} unit=" MW" hint="+ over-forecast, − under-forecast" />
          <Kpi label="P95 abs error" value={fmt(o?.p95_ae)} unit=" MW" hint="1 in 20 half-hours is worse" />
          <Kpi label="Normalised MAE" value={fmt(o?.nmae_pct, 1)} unit=" %" hint="MAE ÷ mean actual output" />
          <Kpi label="Over-forecast" value={fmt(o?.pct_over_forecast, 0)} unit=" % of time" hint="Share of half-hours with a shortfall risk" />
        </div>
        <p className="note">
          Planning rule of thumb: plan against forecast − {fmt(o?.err_p95)} MW to be covered in about 95% of half-hours
          (the actual is below forecast by more than that only 5% of the time).
        </p>
      </Card>

      <div className="grid2">
        <Card title="Error by delivery day" sub="MAE and RMSE (MW)">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={(met?.by_day ?? []).map((d) => ({ ...d, day: d.key.slice(5) }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} interval={2} />
              <YAxis tick={{ fontSize: 11 }} width={48} />
              <Tooltip formatter={(v) => `${fmt(v)} MW`} />
              <Legend />
              <Bar dataKey="mae" name="MAE" fill="var(--forecast)" isAnimationActive={false} />
              <Bar dataKey="rmse" name="RMSE" fill="var(--actual)" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Error by hour of day" sub="London time; is a certain part of the day harder?">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={met?.by_hour ?? []}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="key" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} width={48} />
              <Tooltip formatter={(v) => `${fmt(v)} MW`} />
              <Legend />
              <Bar dataKey="mae" name="MAE" fill="var(--forecast)" isAnimationActive={false} />
              <Bar dataKey="bias" name="Bias" fill="var(--actual)" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="Error vs. forecast age" sub="All January forecasts grouped by how long before the target they were published. Fresher forecasts are more accurate – and that is why the cutoff time matters.">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={hor ?? []}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
            <XAxis dataKey="key" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={48} />
            <Tooltip formatter={(v) => `${fmt(v)} MW`} />
            <Legend />
            <Line dataKey="mae" name="MAE" stroke="var(--forecast)" strokeWidth={2} isAnimationActive={false} />
            <Line dataKey="rmse" name="RMSE" stroke="var(--actual)" strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <footer>
        Source: Elexon BMRS (FUELHH wind actuals, WINDFOR forecasts) · {fmt(cfg.n_actuals)} actual and {fmt(cfg.n_forecasts)} forecast records · data: {cfg.data_source}
      </footer>
    </div>
  );
}
