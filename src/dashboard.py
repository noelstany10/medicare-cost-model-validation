"""Generate the interactive validation dashboard (docs/index.html for GitHub Pages)."""
import json

from . import config as C

TEMPLATE = r"""<title>Medicare Cost Model Validation</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: validation memo header -> KPI strip -> 2-col evidence grid -> findings register */
:root{
  --bg:#f6f7f9; --panel:#ffffff; --ink:#14202e; --ink2:#4a5666; --muted:#7a8594; --line:#e1e5ea; --chip:#eef1f5;
  --accent:#1f4e8c; --s1:#2a78d6; --s2:#eb6834; --grid:#eceef2;
  --good:#0ca30c; --warn:#b47a00; --serious:#d0602f; --crit:#d03b3b;
  --good-bg:#e5f5e5; --warn-bg:#fff3d6; --crit-bg:#fbe3e3;
  --f-display:"Source Serif 4", Georgia, "Times New Roman", serif;
  --f-body:"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --f-mono:"IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --bg:#12161c; --panel:#1a1f27; --ink:#eef1f5; --ink2:#b9c1cc; --muted:#8892a0; --line:#2b323d; --chip:#232a34;
  --accent:#8fb6ec; --s1:#3987e5; --s2:#d95926; --grid:#262d37;
  --good:#3fc43f; --warn:#f0b53a; --serious:#ec835a; --crit:#e66767;
  --good-bg:#16301a; --warn-bg:#352a10; --crit-bg:#3a1c1c; color-scheme:dark } }
:root[data-theme="dark"]{
  --bg:#12161c; --panel:#1a1f27; --ink:#eef1f5; --ink2:#b9c1cc; --muted:#8892a0; --line:#2b323d; --chip:#232a34;
  --accent:#8fb6ec; --s1:#3987e5; --s2:#d95926; --grid:#262d37;
  --good:#3fc43f; --warn:#f0b53a; --serious:#ec835a; --crit:#e66767;
  --good-bg:#16301a; --warn-bg:#352a10; --crit-bg:#3a1c1c; color-scheme:dark }
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:15px/1.55 var(--f-body);margin:0}
.wrap{max-width:1180px;margin:0 auto;padding-inline:20px;padding-block:28px 56px;display:flex;flex-direction:column;gap:22px}
header{display:flex;flex-direction:column;gap:8px}
.eyebrow{font:500 12px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
h1{font:700 clamp(26px,4vw,36px)/1.15 var(--f-display);margin:0;text-wrap:balance}
h2{font:600 19px/1.3 var(--f-display);margin:0 0 4px}
.sub{color:var(--ink2);max-width:75ch;margin:0}
.meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.pill{font:500 12.5px var(--f-body);padding:4px 10px;border-radius:999px;background:var(--chip);color:var(--ink2);border:1px solid var(--line)}
.rating{display:flex;gap:12px;align-items:flex-start;background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:6px;padding:14px 16px}
.rating b{font-family:var(--f-display);font-size:17px}
.banner{background:var(--crit-bg);color:var(--ink);border:1px solid var(--crit);border-radius:6px;padding:10px 14px;font-weight:500}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px 14px;display:flex;flex-direction:column;gap:2px}
.kpi .l{font-size:12.5px;color:var(--muted)}
.kpi .v{font:500 24px var(--f-mono);font-variant-numeric:tabular-nums}
.kpi .c{font:12px var(--f-mono);color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
@media (max-width:860px){.grid{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:16px;min-width:0;display:flex;flex-direction:column;gap:8px}
.card p{margin:0;color:var(--ink2);font-size:13.5px}
.chart{position:relative;height:280px}
.chart.tall{height:420px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--ink2)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.tbl{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th{font:600 11.5px var(--f-body);text-transform:uppercase;letter-spacing:.05em;color:var(--muted);text-align:left;padding:8px;border-bottom:1px solid var(--line)}
td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}
td.n{font-family:var(--f-mono);font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.sev{display:inline-flex;align-items:center;gap:6px;font:600 12px var(--f-body);padding:2px 8px;border-radius:4px;white-space:nowrap}
.sev::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.High,.FAIL{color:var(--crit);background:var(--crit-bg)} .Medium,.WARN{color:var(--warn);background:var(--warn-bg)}
.Low,.PASS{color:var(--good);background:var(--good-bg)} .INFO{color:var(--ink2);background:var(--chip)}
.tabs{display:flex;gap:6px;flex-wrap:wrap}
.tabs button{font:500 13px var(--f-body);padding:6px 12px;border-radius:6px;border:1px solid var(--line);background:var(--panel);color:var(--ink2);cursor:pointer}
.tabs button[aria-pressed="true"]{background:var(--accent);color:var(--panel);border-color:var(--accent)}
.tabs button:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
a{color:var(--accent)}
footer{color:var(--muted);font-size:12.5px}
</style>

<div class="wrap">
<header>
  <div class="eyebrow">Independent model validation · Medicare fee-for-service</div>
  <h1>Medicare Prospective Cost Model</h1>
  <p class="sub">Predicts each beneficiary's next-year Medicare paid cost (Part A inpatient + Part B outpatient + carrier) and flags likely high-cost claimants. Validated with an out-of-time backtest: 2009 features scored against actual 2010 cost.</p>
  <div class="meta" id="meta"></div>
</header>
<div id="banner"></div>
<div class="rating" id="rating"></div>
<section class="kpis" id="kpis" aria-label="Key out-of-time metrics"></section>

<section class="grid">
  <div class="card">
    <h2>Decile backtest</h2>
    <p>Mean predicted vs actual cost per member, by predicted-risk decile.</p>
    <div class="tabs" role="group" aria-label="Sample">
      <button id="t-oot" aria-pressed="true">Out-of-time 2010</button><button id="t-test" aria-pressed="false">In-time test 2009</button>
    </div>
    <div class="legend"><span><i style="background:var(--s1)"></i>Predicted</span><span><i style="background:var(--s2)"></i>Actual</span></div>
    <div class="chart"><canvas id="c-decile" role="img" aria-label="Decile backtest bar chart"></canvas></div>
  </div>
  <div class="card">
    <h2>Benchmarking</h2>
    <p>Cumming's Prediction Measure on the out-of-time sample. Champion in blue, benchmarks in grey.</p>
    <div class="chart"><canvas id="c-bench" role="img" aria-label="Model benchmark bar chart"></canvas></div>
  </div>
  <div class="card">
    <h2>High-cost claimant ROC</h2>
    <p id="roc-note"></p>
    <div class="chart"><canvas id="c-roc" role="img" aria-label="ROC curve"></canvas></div>
  </div>
  <div class="card">
    <h2>Score stability (PSI)</h2>
    <p id="psi-note"></p>
    <div class="legend"><span><i style="background:var(--s1)"></i>Development</span><span><i style="background:var(--s2)"></i>Out-of-time</span></div>
    <div class="chart"><canvas id="c-psi" role="img" aria-label="PSI distribution chart"></canvas></div>
  </div>
  <div class="card">
    <h2>What drives the prediction</h2>
    <p>Permutation importance: increase in mean absolute error ($) when each feature is shuffled.</p>
    <div class="chart tall"><canvas id="c-imp" role="img" aria-label="Feature importance chart"></canvas></div>
  </div>
  <div class="card">
    <h2>Segment calibration</h2>
    <p>Predictive ratio (predicted ÷ actual) by member segment, out-of-time. Tolerance band 0.85–1.15.</p>
    <div class="chart tall"><canvas id="c-seg" role="img" aria-label="Segment predictive ratio chart"></canvas></div>
  </div>
</section>

<section class="card">
  <h2>Findings register</h2>
  <div class="tbl"><table id="t-find"></table></div>
</section>
<section class="grid">
  <div class="card"><h2>Model comparison</h2><div class="tbl"><table id="t-models"></table></div></div>
  <div class="card"><h2>Robustness re-fits (OOT)</h2><div class="tbl"><table id="t-rob"></table></div></div>
</section>
<section class="card"><h2>Data-quality tests</h2><div class="tbl"><table id="t-dq"></table></div></section>
<footer id="foot"></footer>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
const D = __DATA__;
const $ = id => document.getElementById(id);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const f3 = v => v == null ? "–" : (+v).toFixed(3), usd = v => "$" + Math.round(v).toLocaleString("en-US"), pct = v => (100*v).toFixed(1) + "%";
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const CH = "M3 Gradient boosting (champion)", CC = "C2 Gradient boosting (champion)", OOT = "OOT 2009->2010";
const reg = D.reg_comparison.find(r => r.model === CH && r.sample === OOT);
const clf = D.clf_comparison.find(r => r.model === CC && r.sample === OOT);

$("meta").innerHTML = [D.meta.data_source, "Run " + D.meta.run_date, "Train " + D.meta.n_train.toLocaleString() + " · Test " + D.meta.n_test.toLocaleString() + " · OOT " + D.meta.n_oot.toLocaleString(), "High-cost threshold " + usd(D.meta.hcc_threshold)].map(t => `<span class="pill">${esc(t)}</span>`).join("");
if (D.meta.synthetic) $("banner").innerHTML = `<div class="banner">Test run on the generated sample, not CMS data. The GitHub Actions workflow replaces this with real DE-SynPUF results.</div>`;
const sev = D.findings.reduce((a, f) => (a[f.severity] = (a[f.severity] || 0) + 1, a), {});
$("rating").innerHTML = `<div><div class="eyebrow">Overall validation rating</div><b>${esc(D.rating)}</b><div class="sub" style="margin-top:4px">${sev.High||0} High · ${sev.Medium||0} Medium · ${sev.Low||0} Low findings</div></div>`;
const ci = D.ci;
const kpis = [
  ["R² (cost)", f3(reg.R2), `95% CI ${f3(ci.R2_oot[0])}–${f3(ci.R2_oot[1])}`],
  ["Cumming's Prediction Measure", f3(reg.CPM), `95% CI ${f3(ci.CPM_oot[0])}–${f3(ci.CPM_oot[1])}`],
  ["Predictive ratio", f3(reg.Predictive_ratio), "target 0.95–1.05"],
  ["Cost captured by top 10%", pct(reg.Top10_cost_capture), "of actual 2010 spend"],
  ["High-cost AUC", f3(clf.AUC), `95% CI ${f3(ci.AUC_oot[0])}–${f3(ci.AUC_oot[1])}`],
  ["Top-decile lift", (+clf.Lift_top10).toFixed(2) + "×", "high-cost claimants"],
  ["Score PSI", f3(D.psi_score), D.psi_score < 0.1 ? "stable (< 0.10)" : D.psi_score < 0.25 ? "monitor" : "significant shift"],
];
$("kpis").innerHTML = kpis.map(k => `<div class="kpi"><span class="l">${k[0]}</span><span class="v">${k[1]}</span><span class="c">${k[2]}</span></div>`).join("");
$("roc-note").textContent = `Out-of-time AUC ${f3(clf.AUC)}, KS ${f3(clf.KS)}, precision in top 10% ${pct(clf.Precision_top10)} vs base rate ${pct(clf.Event_rate)}.`;
$("psi-note").textContent = `Share of members per development score decile. PSI ${f3(D.psi_score)}: below 0.10 is stable, 0.10–0.25 needs monitoring, above 0.25 is a material shift.`;

function table(id, cols, rows) {
  $(id).innerHTML = "<thead><tr>" + cols.map(c => `<th>${c[0]}</th>`).join("") + "</tr></thead><tbody>" +
    rows.map(r => "<tr>" + cols.map(c => { const v = c[1](r); return `<td class="${c[2]||""}">${v}</td>`; }).join("") + "</tr>").join("") + "</tbody>";
}
table("t-find", [["ID", r => esc(r.id)], ["Area", r => esc(r.area)], ["Severity", r => `<span class="sev ${esc(r.severity)}">${esc(r.severity)}</span>`],
  ["Finding", r => esc(r.finding)], ["Evidence", r => esc(r.evidence)], ["Recommendation", r => esc(r.recommendation)]], D.findings);
table("t-models", [["Model", r => esc(r.model)], ["Sample", r => esc(r.sample)], ["R²", r => f3(r.R2), "n"], ["CPM", r => f3(r.CPM), "n"], ["Pred. ratio", r => f3(r.Predictive_ratio), "n"], ["Gini", r => f3(r.Gini), "n"]],
  D.reg_comparison.filter(r => r.sample !== "Train"));
table("t-rob", [["Re-fit", r => esc(r.test)], ["R²", r => f3(r.R2), "n"], ["CPM", r => f3(r.CPM), "n"], ["Pred. ratio", r => f3(r.Predictive_ratio), "n"]], D.robustness);
table("t-dq", [["Check", r => esc(r.check_id)], ["Category", r => esc(r.category)], ["Description", r => esc(r.description)], ["Observed", r => (+r.observed).toLocaleString("en-US", {maximumFractionDigits: 4}), "n"],
  ["Status", r => `<span class="sev ${esc(r.status)}">${esc(r.status)}</span>`]], D.dq);
$("foot").innerHTML = `Source: CMS 2008–2010 DE-SynPUF Sample 1 (synthetic Medicare claims). Code, SQL, full validation report and Excel workbook are in the project repository.`;

let charts = [], view = "oot";
function draw() {
  charts.forEach(c => c.destroy()); charts = [];
  const ink2 = css("--ink2"), grid = css("--grid"), s1 = css("--s1"), s2 = css("--s2"), muted = css("--muted"), panel = css("--panel");
  Chart.defaults.font.family = css("--f-body"); Chart.defaults.color = ink2;
  const base = (extra = {}) => ({ responsive: true, maintainAspectRatio: false, animation: false,
    plugins: { legend: { display: false }, tooltip: { backgroundColor: css("--ink"), titleColor: panel, bodyColor: panel, padding: 10 } },
    interaction: { mode: "index", intersect: false }, ...extra });
  const dec = view === "oot" ? D.decile_oot : D.decile_test;
  charts.push(new Chart($("c-decile"), { type: "bar", data: { labels: dec.map(d => d.decile), datasets: [
      { label: "Predicted", data: dec.map(d => d.mean_pred), backgroundColor: s1, borderRadius: 4, borderSkipped: "start" },
      { label: "Actual", data: dec.map(d => d.mean_actual), backgroundColor: s2, borderRadius: 4, borderSkipped: "start" }] },
    options: base({ scales: { x: { grid: { display: false }, title: { display: true, text: "Predicted-risk decile (1 = lowest)" } },
      y: { grid: { color: grid }, ticks: { callback: v => usd(v) } } },
      plugins: { ...base().plugins, tooltip: { ...base().plugins.tooltip, callbacks: { label: c => `${c.dataset.label}: ${usd(c.raw)}`,
        afterBody: it => `Predictive ratio ${f3(dec[it[0].dataIndex].predictive_ratio)}` } } } }) }));
  const bo = D.reg_comparison.filter(r => r.sample === OOT);
  charts.push(new Chart($("c-bench"), { type: "bar", data: { labels: bo.map(r => r.model.replace(" (champion)", " ★")), datasets: [
      { data: bo.map(r => r.CPM), backgroundColor: bo.map(r => r.model === CH ? s1 : muted), borderRadius: 4, borderSkipped: "start" }] },
    options: base({ indexAxis: "y", interaction: { mode: "nearest", intersect: true }, scales: { x: { grid: { color: grid }, title: { display: true, text: "CPM (higher is better)" } }, y: { grid: { display: false } } },
      plugins: { ...base().plugins, tooltip: { ...base().plugins.tooltip, callbacks: { label: c => `CPM ${f3(c.raw)} · R² ${f3(bo[c.dataIndex].R2)} · PR ${f3(bo[c.dataIndex].Predictive_ratio)}` } } } }) }));
  charts.push(new Chart($("c-roc"), { type: "line", data: { datasets: [
      { data: D.roc_oot.map(p => ({ x: p.fpr, y: p.tpr })), borderColor: s1, borderWidth: 2, pointRadius: 0, label: "Champion" },
      { data: [{ x: 0, y: 0 }, { x: 1, y: 1 }], borderColor: muted, borderDash: [4, 4], borderWidth: 1, pointRadius: 0, label: "Random" }] },
    options: base({ interaction: { mode: "nearest", intersect: false, axis: "x" }, scales: { x: { type: "linear", min: 0, max: 1, grid: { color: grid }, title: { display: true, text: "False positive rate" } },
      y: { min: 0, max: 1, grid: { color: grid }, title: { display: true, text: "True positive rate" } } },
      plugins: { ...base().plugins, tooltip: { ...base().plugins.tooltip, filter: i => i.datasetIndex === 0, callbacks: { label: c => `FPR ${f3(c.raw.x)} · TPR ${f3(c.raw.y)}` } } } }) }));
  charts.push(new Chart($("c-psi"), { type: "bar", data: { labels: D.psi_table.map(b => b.bin), datasets: [
      { label: "Development", data: D.psi_table.map(b => b.expected_pct), backgroundColor: s1, borderRadius: 4, borderSkipped: "start" },
      { label: "Out-of-time", data: D.psi_table.map(b => b.actual_pct), backgroundColor: s2, borderRadius: 4, borderSkipped: "start" }] },
    options: base({ scales: { x: { grid: { display: false }, title: { display: true, text: "Score bin" } }, y: { grid: { color: grid }, ticks: { callback: v => pct(v) } } },
      plugins: { ...base().plugins, tooltip: { ...base().plugins.tooltip, callbacks: { label: c => `${c.dataset.label}: ${pct(c.raw)}`, afterBody: it => `PSI contribution ${(+D.psi_table[it[0].dataIndex].psi_contrib).toFixed(4)}` } } } }) }));
  const imp = D.perm_importance;
  charts.push(new Chart($("c-imp"), { type: "bar", data: { labels: imp.map(r => r.feature), datasets: [{ data: imp.map(r => r.importance), backgroundColor: s1, borderRadius: 4, borderSkipped: "start" }] },
    options: base({ indexAxis: "y", interaction: { mode: "nearest", intersect: true }, scales: { x: { grid: { color: grid }, ticks: { callback: v => usd(v) } }, y: { grid: { display: false }, ticks: { font: { family: css("--f-mono"), size: 11 } } } },
      plugins: { ...base().plugins, tooltip: { ...base().plugins.tooltip, callbacks: { label: c => `ΔMAE ${usd(c.raw)} (± ${usd(imp[c.dataIndex].std)})` } } } }) }));
  const sg = D.subgroups_oot;
  const band = { id: "band", beforeDatasetsDraw(ch) { const { ctx, chartArea: a, scales: { x } } = ch; ctx.save(); ctx.fillStyle = grid;
      ctx.fillRect(x.getPixelForValue(0.85), a.top, x.getPixelForValue(1.15) - x.getPixelForValue(0.85), a.bottom - a.top);
      ctx.strokeStyle = muted; ctx.beginPath(); ctx.moveTo(x.getPixelForValue(1), a.top); ctx.lineTo(x.getPixelForValue(1), a.bottom); ctx.stroke(); ctx.restore(); } };
  const lo = Math.min(0.7, ...sg.map(s => s.predictive_ratio)) - 0.02, hi = Math.max(1.3, ...sg.map(s => s.predictive_ratio)) + 0.02;
  charts.push(new Chart($("c-seg"), { type: "scatter", plugins: [band], data: { datasets: [{ data: sg.map((s, i) => ({ x: s.predictive_ratio, y: i })),
      backgroundColor: sg.map(s => (s.predictive_ratio < 0.85 || s.predictive_ratio > 1.15) && s.n >= 500 ? css("--crit") : s1), pointRadius: 5, pointHoverRadius: 7, pointBorderColor: panel, pointBorderWidth: 2 }] },
    options: base({ interaction: { mode: "nearest", intersect: true }, scales: { x: { min: lo, max: hi, grid: { color: grid }, title: { display: true, text: "Predictive ratio" } },
      y: { reverse: true, min: -0.5, max: sg.length - 0.5, grid: { display: false }, afterBuildTicks: ax => { ax.ticks = sg.map((_, i) => ({ value: i })); },
        ticks: { autoSkip: false, callback: v => sg[v] ? `${sg[v].dimension.replace("_", " ")}: ${sg[v].level}` : "", font: { size: 11 } } } },
      plugins: { ...base().plugins, tooltip: { ...base().plugins.tooltip, callbacks: { label: c => { const s = sg[c.raw.y]; return `${s.dimension}=${s.level}: PR ${f3(s.predictive_ratio)} · n ${s.n.toLocaleString()} · actual ${usd(s.actual_mean)}`; } } } } }) }));
}
function setView(v) { view = v; $("t-oot").setAttribute("aria-pressed", v === "oot"); $("t-test").setAttribute("aria-pressed", v === "test"); draw(); }
$("t-oot").onclick = () => setView("oot"); $("t-test").onclick = () => setView("test");
if (window.Chart) { draw(); matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  new MutationObserver(draw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] }); }
</script>
"""


def build(results):
    data = json.dumps(results, default=float).replace("</", "<\\/")
    body = TEMPLATE.replace("__DATA__", data)
    C.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n' + body + "\n</body>\n</html>\n")
    (C.DOCS_DIR / "index.html").write_text(full)
    (C.OUT_DIR / "dashboard_fragment.html").write_text(body)   # used for the hosted artifact copy
    return C.DOCS_DIR / "index.html"
