async function get(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`/api${path}${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  config: () => get("/config"),
  forecast: (delivery_date, cutoff) => get("/forecast", { delivery_date, cutoff }),
  metrics: (cutoff) => get("/metrics", { cutoff }),
  horizon: () => get("/horizon"),
};
