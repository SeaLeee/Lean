/**
 * QuantConnect LEAN - Dashboard Application
 */

// ---- State ----
let allAlgos = { CSharp: [], Python: [] };
let algoDescriptions = {};
let algoTags = {};       // { "algoName": ["tag1", "tag2"] }
let algoBookmarks = {};  // { "algoName": true }
let currentTab = "dashboard";
let logPollTimer = null;
let batchPollTimer = null;
let batchAllSelected = false;

// ---- Init ----
document.addEventListener("DOMContentLoaded", () => {
  updateClock();
  setInterval(updateClock, 1000);
  loadAllData();
});

function updateClock() {
  const el = document.getElementById("clock");
  if (el) el.textContent = new Date().toLocaleString("zh-CN");
}

async function loadAllData() {
  await Promise.all([loadDashboard(), loadAlgorithms(), loadTags(), loadDescriptions()]);
  filterAlgorithms();
}

// ============================================================
// Tab Switching
// ============================================================

function switchTab(name) {
  currentTab = name;
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  const tabEl = document.getElementById("tab-" + name);
  if (tabEl) tabEl.classList.add("active");
  const navEl = document.querySelector(`[data-tab="${name}"]`);
  if (navEl) navEl.classList.add("active");
  const titles = {
    dashboard: "控制台 Dashboard", backtest: "回测中心", algorithms: "算法管理",
    batch: "批量回测排名", live: "实盘交易", data: "数据管理",
    config: "配置编辑", logs: "日志查看",
  };
  document.getElementById("page-title").textContent = titles[name] || name;
  if (name === "dashboard") loadDashboard();
  if (name === "backtest") { loadBacktestAlgos(); refreshResults(); }
  if (name === "algorithms") filterAlgorithms();
  if (name === "batch") loadBatchAlgoList();
  if (name === "data") refreshDataTree();
  if (name === "logs") refreshLogs();
  if (name === "config") loadConfigToEditor();
  if (name !== "backtest" && logPollTimer) { clearTimeout(logPollTimer); logPollTimer = null; }
  if (name !== "batch" && batchPollTimer) { clearTimeout(batchPollTimer); batchPollTimer = null; }
}

// ============================================================
// Dashboard
// ============================================================

async function loadDashboard() {
  try {
    const sys = await fetch("/api/system").then(r => r.json());
    document.getElementById("stat-dotnet").textContent = sys.dotnet || "-";
    document.getElementById("stat-python").textContent = sys.python || "-";
    document.getElementById("stat-data-status").textContent = sys.data_exists ? "已配置" : "未配置";
    document.getElementById("info-path").textContent = sys.project_dir || "-";
    document.getElementById("info-data-path").textContent = sys.data_dir || "-";
    document.getElementById("info-version").textContent = sys.lean_version || "-";
    document.getElementById("info-os").textContent = sys.os || "-";
    const env = currentTab === "live" ? "live-paper" : "backtesting";
    document.getElementById("info-env").textContent = sys.data_exists ? env : "未配置";
  } catch (e) { console.error(e); }
  try {
    const algos = await fetch("/api/algorithms").then(r => r.json());
    const total = (algos.CSharp || []).length + (algos.Python || []).length;
    document.getElementById("stat-algo-count").textContent = total;
  } catch (e) {}
}

// ============================================================
// Tags & Bookmarks
// ============================================================

async function loadTags() {
  try {
    const data = await fetch("/api/tags").then(r => r.json());
    algoTags = data.tags || {};
    algoBookmarks = data.bookmarks || {};
    updateTagFilter();
  } catch (e) { algoTags = {}; algoBookmarks = {}; }
}

async function saveTags() {
  try {
    await fetch("/api/tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags: algoTags, bookmarks: algoBookmarks }),
    });
  } catch (e) { console.error(e); }
}

function toggleBookmark(algoName) {
  algoBookmarks[algoName] = !algoBookmarks[algoName];
  saveTags();
  filterAlgorithms();
}

function addTag(algoName, tag) {
  if (!tag) return;
  if (!algoTags[algoName]) algoTags[algoName] = [];
  if (!algoTags[algoName].includes(tag)) {
    algoTags[algoName].push(tag);
    saveTags();
    updateTagFilter();
    filterAlgorithms();
  }
}

function removeTag(algoName, tag) {
  if (algoTags[algoName]) {
    algoTags[algoName] = algoTags[algoName].filter(t => t !== tag);
    if (algoTags[algoName].length === 0) delete algoTags[algoName];
    saveTags();
    updateTagFilter();
    filterAlgorithms();
  }
}

function updateTagFilter() {
  const sel = document.getElementById("algo-tag-filter");
  if (!sel) return;
  const allTags = new Set();
  Object.values(algoTags).forEach(tags => tags.forEach(t => allTags.add(t)));
  const currentVal = sel.value;
  sel.innerHTML = '<option value="">全部标记</option>' +
    [...allTags].sort().map(t => `<option value="${t}">${t}</option>`).join("");
  sel.value = currentVal;
}

// ============================================================
// Algorithm Descriptions
// ============================================================

async function loadDescriptions() {
  try {
    const data = await fetch("/api/algorithms/descriptions").then(r => r.json());
    algoDescriptions = data; // {CSharp: [...], Python: [...]}
  } catch (e) { algoDescriptions = {}; }
}

function getAlgoDesc(name, lang) {
  const langKey = lang === "Python" ? "Python" : "CSharp";
  const list = algoDescriptions[langKey] || [];
  return list.find(a => a.name === name) || null;
}

// ============================================================
// Algorithm Detail Modal
// ============================================================

async function showDetail(algoName, lang) {
  const modal = document.getElementById("detail-modal");
  const body = document.getElementById("detail-body");
  document.getElementById("detail-title").textContent = algoName;
  body.innerHTML = '<p class="text-muted">加载中...</p>';
  modal.style.display = "flex";

  try {
    const resp = await fetch(`/api/algorithms/describe/${algoName}?language=${lang}`);
    const d = await resp.json();
    let html = "";
    // Tags
    const tags = algoTags[algoName] || [];
    const isBookmarked = algoBookmarks[algoName];
    html += `<div class="detail-section">`;
    html += `<button class="btn btn-sm ${isBookmarked ? 'btn-warning' : ''}" onclick="toggleBookmark('${algoName}');showDetail('${algoName}','${lang}')">${isBookmarked ? '★ 已收藏' : '☆ 收藏'}</button> `;
    if (tags.length > 0) {
      html += tags.map(t => `<span class="tag-chip">${t} <span class="tag-remove" onclick="removeTag('${algoName}','${t}');showDetail('${algoName}','${lang}')">&times;</span></span>`).join(" ");
    }
    html += `</div>`;

    // Add tag input
    html += `<div class="detail-section"><div class="tag-input-row">
      <input type="text" id="new-tag-input" class="form-control form-control-sm" placeholder="添加标签...">
      <button class="btn btn-sm" onclick="addTag('${algoName}',document.getElementById('new-tag-input').value);showDetail('${algoName}','${lang}')">+ 添加</button>
    </div></div>`;

    // Description
    html += `<div class="detail-section">`;
    html += `<h3>中文名称</h3><p style="font-size:18px;color:var(--accent);">${escapeHtml(d.cn_title || algoName)}</p>`;
    html += `<h3>策略说明</h3><p>${escapeHtml(d.description || "暂无说明")}</p>`;
    if (d.purpose) html += `<h3>解决的问题</h3><p>${escapeHtml(d.purpose)}</p>`;
    html += `</div>`;

    // Meta info
    html += `<div class="detail-section">`;
    html += `<h3>分类信息</h3>`;
    html += `<span class="algo-category">${escapeHtml(d.category || "未知")}</span> `;
    html += `<span class="algo-difficulty ${d.difficulty || 'intermediate'}">${d.difficulty === 'beginner' ? '入门' : d.difficulty === 'advanced' ? '高级' : '中级'}</span>`;
    html += `<span style="margin-left:12px;font-size:12px;color:var(--text-muted);">语言: ${lang} | 源文件: ${d.file_path || 'N/A'} | 行数: ${d.source_lines || 0}</span>`;
    html += `</div>`;

    // Features
    if (d.features && d.features.length > 0) {
      html += `<div class="detail-section"><h3>技术特性</h3><ul class="detail-features">`;
      d.features.forEach(f => { html += `<li>${escapeHtml(f)}</li>`; });
      html += `</ul></div>`;
    }

    // Indicators
    if (d.indicators && d.indicators.length > 0) {
      html += `<div class="detail-section"><h3>使用的指标</h3><p>${d.indicators.join(", ")}</p></div>`;
    }

    // Source preview
    if (d.source_preview) {
      html += `<div class="detail-section"><h3>源代码预览</h3>`;
      html += `<div class="source-preview">${escapeHtml(d.source_preview.substring(0, 2000))}</div>`;
      html += `</div>`;
    }

    // Quick run
    html += `<div class="form-actions">
      <button class="btn btn-primary" onclick="closeDetail();switchTab('backtest');setTimeout(()=>{document.getElementById('bt-language').value='${lang}';onBacktestLanguageChange();setTimeout(()=>{document.getElementById('bt-algorithm').value='${algoName}';},200);},200)">▶ 在回测中心运行</button>
      <button class="btn btn-sm" onclick="closeDetail()">关闭</button>
    </div>`;

    body.innerHTML = html;
  } catch (e) {
    body.innerHTML = `<p class="text-muted">加载失败: ${e.message}</p>`;
  }
}

function closeDetail(e) {
  if (e && e.target !== document.getElementById("detail-modal")) return;
  document.getElementById("detail-modal").style.display = "none";
}

// ============================================================
// Algorithms List
// ============================================================

async function loadAlgorithms() {
  try {
    allAlgos = await fetch("/api/algorithms").then(r => r.json());
  } catch (e) { console.error(e); }
}

function filterAlgorithms() {
  const search = (document.getElementById("algo-search")?.value || "").toLowerCase();
  const lang = document.getElementById("algo-lang-filter")?.value || "";
  const cat = document.getElementById("algo-cat-filter")?.value || "";
  const tag = document.getElementById("algo-tag-filter")?.value || "";
  const diff = document.getElementById("algo-diff-filter")?.value || "";

  let items = [];
  const addItems = (langKey, algos) => {
    for (const a of algos) {
      const desc = getAlgoDesc(a.name, langKey);
      items.push({ ...a, language: langKey, desc: desc });
    }
  };

  if (lang) {
    if (allAlgos[lang]) addItems(lang, allAlgos[lang]);
  } else {
    if (allAlgos.CSharp) addItems("CSharp", allAlgos.CSharp);
    if (allAlgos.Python) addItems("Python", allAlgos.Python);
  }

  // Apply filters
  if (search) items = items.filter(a => a.name.toLowerCase().includes(search));
  if (cat) items = items.filter(a => (a.desc && a.desc.category === cat));
  if (tag) items = items.filter(a => algoTags[a.name] && algoTags[a.name].includes(tag));
  if (diff) items = items.filter(a => a.desc && a.desc.difficulty === diff);

  // Sort: bookmarked first
  items.sort((a, b) => {
    const ba = algoBookmarks[a.name] ? 1 : 0;
    const bb = algoBookmarks[b.name] ? 1 : 0;
    return bb - ba;
  });

  renderAlgoCards(items);
}

function renderAlgoCards(items) {
  const grid = document.getElementById("algo-grid");
  if (!grid) return;
  if (items.length === 0) {
    grid.innerHTML = '<p class="text-muted">没有找到匹配的算法</p>';
    return;
  }
  grid.innerHTML = items.slice(0, 200).map(a => {
    const desc = a.desc || {};
    const isBookmarked = algoBookmarks[a.name];
    const tags = algoTags[a.name] || [];
    return `
    <div class="algo-card">
      <button class="algo-bookmark ${isBookmarked ? 'active' : ''}" title="收藏" onclick="event.stopPropagation();toggleBookmark('${a.name}')">${isBookmarked ? '★' : '☆'}</button>
      ${desc.cn_title ? `<div class="algo-cn-title">${escapeHtml(desc.cn_title)}</div>` : ''}
      <div class="algo-name" onclick="showDetail('${a.name}','${a.language}')" style="cursor:pointer;">${a.name}</div>
      ${desc.description ? `<div class="algo-desc">${escapeHtml(desc.description)}</div>` : ''}
      <div class="algo-meta">
        <span class="algo-lang ${a.language === 'CSharp' ? 'cs' : 'py'}">${a.language}</span>
        ${desc.category ? `<span class="algo-category">${escapeHtml(desc.category)}</span>` : ''}
        ${desc.difficulty ? `<span class="algo-difficulty ${desc.difficulty}">${desc.difficulty === 'beginner' ? '入门' : desc.difficulty === 'advanced' ? '高级' : '中级'}</span>` : ''}
      </div>
      ${tags.length > 0 ? `<div class="algo-tags">${tags.map(t => `<span class="algo-tag" onclick="event.stopPropagation();document.getElementById('algo-tag-filter').value='${t}';filterAlgorithms()">${escapeHtml(t)}</span>`).join("")}</div>` : ''}
      <div class="algo-actions">
        <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();showDetail('${a.name}','${a.language}')">详情</button>
        <button class="btn btn-sm" onclick="event.stopPropagation();switchTab('backtest');setTimeout(()=>{document.getElementById('bt-language').value='${a.language}';onBacktestLanguageChange();setTimeout(()=>{document.getElementById('bt-algorithm').value='${a.name}';},200);},200)">▶ 回测</button>
      </div>
    </div>`;
  }).join("");
  if (items.length > 200) {
    grid.innerHTML += `<p class="text-muted" style="grid-column:1/-1;">显示前200个，共${items.length}个匹配。请使用搜索缩小范围。</p>`;
  }
}

// ============================================================
// Backtest
// ============================================================

function onBacktestLanguageChange() { loadBacktestAlgos(); }

function loadBacktestAlgos() {
  const lang = document.getElementById("bt-language").value;
  const select = document.getElementById("bt-algorithm");
  if (!select) return;
  const algos = allAlgos[lang] || [];
  select.innerHTML = algos.map(a => `<option value="${a.name}">${a.name}</option>`).join("");
}

function filterBacktestAlgorithms() {
  const search = (document.getElementById("bt-algo-search")?.value || "").toLowerCase();
  const select = document.getElementById("bt-algorithm");
  if (!select) return;
  const lang = document.getElementById("bt-language").value;
  const algos = allAlgos[lang] || [];
  const filtered = search ? algos.filter(a => a.name.toLowerCase().includes(search)) : algos;
  select.innerHTML = filtered.map(a => `<option value="${a.name}">${a.name}</option>`).join("");
}

async function runBacktest() {
  const algorithm = document.getElementById("bt-algorithm").value;
  const language = document.getElementById("bt-language").value;
  const environment = document.getElementById("bt-environment").value;
  if (!algorithm) { alert("请选择一个算法"); return; }

  document.getElementById("btn-run-backtest").disabled = true;
  document.getElementById("btn-stop-backtest").disabled = false;
  document.getElementById("bt-status").style.display = "flex";
  document.getElementById("bt-status-text").textContent = `运行: ${algorithm}...`;
  document.getElementById("log-output").innerHTML = "";

  try {
    await fetch("/api/backtest/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ algorithm, language, environment }),
    });
    startLogPolling();
  } catch (e) { console.error(e); }
}

async function stopBacktest() {
  try {
    await fetch("/api/backtest/stop", { method: "POST" });
    document.getElementById("btn-stop-backtest").disabled = true;
  } catch (e) {}
}

function startLogPolling() {
  let since = 0;
  async function poll() {
    try {
      const resp = await fetch(`/api/backtest/logs/stream?since=${since}&timeout=5`);
      const data = await resp.json();
      if (data.logs && data.logs.length > 0) { appendLogs(data.logs); since = data.total; }
      if (data.running) { logPollTimer = setTimeout(poll, 500); }
      else {
        document.getElementById("btn-run-backtest").disabled = false;
        document.getElementById("btn-stop-backtest").disabled = true;
        document.getElementById("bt-status-text").textContent = "回测完成";
        document.getElementById("engine-status-dot").classList.remove("running");
        logPollTimer = null;
        refreshResults();
      }
    } catch (e) { logPollTimer = setTimeout(poll, 2000); }
  }
  document.getElementById("engine-status-dot").classList.add("running");
  document.getElementById("engine-status-text").textContent = "回测运行中";
  poll();
}

function appendLogs(lines) {
  const el = document.getElementById("log-output");
  if (!el) return;
  const frag = document.createDocumentFragment();
  for (const line of lines) {
    const div = document.createElement("div");
    const lower = line.toLowerCase();
    if (lower.includes("error") || lower.includes("fail")) div.className = "error";
    else if (lower.includes("warn")) div.className = "warn";
    else if (lower.includes("trace")) div.className = "trace";
    div.textContent = line;
    frag.appendChild(div);
  }
  el.appendChild(frag);
  el.scrollTop = el.scrollHeight;
}

function clearLogs() { const el = document.getElementById("log-output"); if (el) el.innerHTML = ""; }

async function refreshResults() {
  const container = document.getElementById("results-container");
  if (!container) return;
  try {
    const results = await fetch("/api/results").then(r => r.json());
    if (!results || results.length === 0) {
      container.innerHTML = '<p class="text-muted">暂无回测结果</p>';
      return;
    }
    container.innerHTML = results.slice(0, 10).map(r =>
      `<div class="result-item" onclick="viewResult('${r.name}')">
        <div class="result-name">${r.name}</div>
        <div class="result-meta">${r.files.length} 个文件</div>
      </div>`
    ).join("");
  } catch (e) {}
}

async function viewResult(name) {
  const container = document.getElementById("results-container");
  if (!container) return;
  try {
    const data = await fetch("/api/backtest/results").then(r => r.json());
    const keys = Object.keys(data).filter(k => !k.startsWith("_"));
    let html = `<div class="result-name" style="margin-bottom:12px;">${data._name || name}</div>`;
    if (keys.length === 0) { html += '<p class="text-muted">暂无统计数据</p>'; }
    else {
      html += '<div class="result-stats">';
      for (const k of keys.slice(0, 20)) {
        const v = data[k];
        const dv = typeof v === "object" ? JSON.stringify(v).substring(0, 100) : String(v).substring(0, 200);
        html += `<div class="result-stat"><span class="key">${k}</span><span class="val">${escapeHtml(dv)}</span></div>`;
      }
      html += '</div>';
    }
    container.innerHTML = html;
  } catch (e) {}
}

// ============================================================
// Batch Backtest
// ============================================================

function loadBatchAlgoList() {
  const lang = document.getElementById("batch-lang").value;
  const search = (document.getElementById("batch-algo-search")?.value || "").toLowerCase();
  const container = document.getElementById("batch-algo-list");
  if (!container) return;
  const algos = allAlgos[lang] || [];
  const filtered = search ? algos.filter(a => a.name.toLowerCase().includes(search)) : algos;
  const bookmarked = filtered.filter(a => algoBookmarks[a.name]);
  const rest = filtered.filter(a => !algoBookmarks[a.name]);

  let html = "";
  if (bookmarked.length > 0) {
    html += `<div style="font-size:11px;color:var(--text-muted);margin:4px 0;">★ 已收藏</div>`;
    bookmarked.forEach(a => {
      html += `<label><input type="checkbox" value="${a.name}" class="batch-cb" onchange="updateBatchCount()"> ${a.name}</label>`;
    });
  }
  if (rest.length > 0) {
    if (bookmarked.length > 0) html += `<div style="font-size:11px;color:var(--text-muted);margin:4px 0;">其他</div>`;
    rest.slice(0, 100).forEach(a => {
      html += `<label><input type="checkbox" value="${a.name}" class="batch-cb" onchange="updateBatchCount()"> ${a.name}</label>`;
    });
  }
  container.innerHTML = html || '<p class="text-muted">没有匹配的算法</p>';
  updateBatchCount();
}

function updateBatchCount() {
  const count = document.querySelectorAll(".batch-cb:checked").length;
  const el = document.getElementById("batch-selected-count");
  if (el) el.textContent = `已选 ${count} 个`;
}

function batchSelectAll() {
  batchAllSelected = !batchAllSelected;
  document.querySelectorAll(".batch-cb").forEach(cb => { cb.checked = batchAllSelected; });
  updateBatchCount();
}

async function startBatchBacktest() {
  const selected = Array.from(document.querySelectorAll(".batch-cb:checked")).map(cb => ({
    name: cb.value,
    language: document.getElementById("batch-lang").value,
  }));

  if (selected.length === 0) { alert("请至少选择一个算法"); return; }
  if (selected.length > 20 && !confirm(`选中了 ${selected.length} 个算法，可能需要较长时间。继续？`)) return;

  document.getElementById("btn-batch-run").disabled = true;
  document.getElementById("batch-results-container").innerHTML = '<p class="text-muted">正在启动...</p>';

  try {
    const resp = await fetch("/api/batch/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ algorithms: selected }),
    });
    const data = await resp.json();
    if (data.status === "started") {
      pollBatchStatus(data.batch_id);
    }
  } catch (e) {
    document.getElementById("batch-results-container").innerHTML = `<p class="error">启动失败: ${e.message}</p>`;
    document.getElementById("btn-batch-run").disabled = false;
  }
}

function pollBatchStatus(batchId) {
  async function poll() {
    try {
      const resp = await fetch(`/api/batch/status/${batchId}`);
      const data = await resp.json();
      renderBatchResults(data);
      document.getElementById("batch-progress").textContent =
        `${data.completed}/${data.total} 完成` + (data.current ? ` · 当前: ${data.current}` : "");

      if (data.running) {
        batchPollTimer = setTimeout(poll, 1000);
      } else {
        document.getElementById("btn-batch-run").disabled = false;
        document.getElementById("batch-progress").textContent = `全部完成! ${data.total} 个算法`;
        batchPollTimer = null;
      }
    } catch (e) {
      batchPollTimer = setTimeout(poll, 2000);
    }
  }
  poll();
}

function renderBatchResults(data) {
  const container = document.getElementById("batch-results-container");
  if (!container) return;

  const results = data.results || [];
  if (results.length === 0 && data.running) {
    container.innerHTML = `<p class="text-muted">运行中... (${data.completed}/${data.total})</p>`;
    return;
  }

  // Progress bar
  const pct = data.total > 0 ? (data.completed / data.total * 100) : 0;
  let html = `<div class="batch-progress-bar"><div class="batch-progress-fill" style="width:${pct}%"></div></div>`;

  // Ranking table
  html += `<table class="ranking-table">
    <thead><tr>
      <th>排名</th><th>算法</th><th>语言</th><th>收益</th><th>Sharpe</th><th>回撤</th><th>胜率</th><th>状态</th>
    </tr></thead><tbody>`;

  results.forEach(r => {
    const stats = r.stats || {};
    const profit = stats["Net Profit"] || stats["Compounding Annual Return"] || "N/A";
    const sharpe = stats["Sharpe Ratio"] || "N/A";
    const drawdown = stats["Drawdown"] || "N/A";
    const winRate = stats["Win Rate"] || "N/A";
    const rank = r.rank || "-";
    const rankClass = rank === 1 ? "rank-1" : rank === 2 ? "rank-2" : rank === 3 ? "rank-3" : "";
    const profitClass = String(profit).startsWith("-") ? "profit-negative" : "profit-positive";
    const sharpeClass = parseFloat(sharpe) > 1 ? "sharpe-high" : "";

    html += `<tr>
      <td class="${rankClass}">#${rank}</td>
      <td><span class="algo-link" onclick="showDetail('${r.name}','${r.language}')">${r.name}</span></td>
      <td>${r.language}</td>
      <td class="${profitClass}">${profit}</td>
      <td class="${sharpeClass}">${sharpe}</td>
      <td>${drawdown}</td>
      <td>${winRate}</td>
      <td>${r.success ? '<span style="color:var(--green);">✓</span>' : '<span style="color:var(--red);" title="' + escapeHtml(r.error || '') + '">✗</span>'}</td>
    </tr>`;
  });

  html += "</tbody></table>";
  container.innerHTML = html;
}

// ============================================================
// Live Trading
// ============================================================

function startLiveTrading() {
  const algo = document.getElementById("live-algorithm").value;
  if (!algo) { alert("请先选择算法"); return; }
  alert(`实盘交易请使用 LEAN CLI 或 Docker 环境启动。\n\n终端执行:\nlean live "${algo}" --environment "${document.getElementById('live-brokerage').value}"`);
}

(function() {
  setTimeout(() => {
    const sel = document.getElementById("live-algorithm");
    if (!sel) return;
    const items = [
      ...(allAlgos.CSharp || []).map(a => ({ ...a, language: "CSharp" })),
      ...(allAlgos.Python || []).map(a => ({ ...a, language: "Python" })),
    ];
    sel.innerHTML = items.map(a => `<option value="${a.name}">[${a.language}] ${a.name}</option>`).join("");
  }, 500);
})();

// ============================================================
// Data Tree
// ============================================================

async function refreshDataTree() {
  const el = document.getElementById("data-tree");
  if (!el) return;
  try {
    const data = await fetch("/api/data-tree").then(r => r.json());
    el.innerHTML = renderTree(data);
    el.querySelectorAll(".tree-toggle").forEach(t => {
      t.onclick = function() {
        const children = this.parentElement.querySelector(".tree-children");
        if (children) {
          children.classList.toggle("open");
          this.textContent = children.classList.contains("open") ? "▾ " : "▸ ";
        }
      };
    });
  } catch (e) { el.innerHTML = '<p class="text-muted">数据目录无法访问</p>'; }
}

function renderTree(data, depth = 0) {
  if (!data || Object.keys(data).length === 0) return '<p class="text-muted">数据目录为空</p>';
  let html = '<div class="tree">';
  for (const [key, val] of Object.entries(data)) {
    if (typeof val === "object" && !Array.isArray(val)) {
      html += `<div class="tree-item"><span class="tree-toggle">▸ </span><span class="tree-folder">${escapeHtml(key)}/</span><div class="tree-children">${renderTree(val, depth + 1)}</div></div>`;
    } else if (Array.isArray(val)) {
      if (val.length === 0) {
        html += `<div class="tree-item"><span class="tree-folder" style="margin-left:20px;">${escapeHtml(key)}/ (空)</span></div>`;
      } else {
        html += `<div class="tree-item"><span class="tree-toggle">▸ </span><span class="tree-folder">${escapeHtml(key)}/ <span class="tree-size">${val.length} files</span></span><div class="tree-children">${val.map(f => `<div class="tree-file">${escapeHtml(f)}</div>`).join("")}</div></div>`;
      }
    }
  }
  html += '</div>';
  return html;
}

// ============================================================
// Config Editor
// ============================================================

async function loadConfigToEditor() {
  try {
    const config = await fetch("/api/config").then(r => r.json());
    document.getElementById("config-editor").value = JSON.stringify(config, null, 2);
  } catch (e) {}
}

async function saveConfig() {
  const statusEl = document.getElementById("config-save-status");
  try {
    const config = JSON.parse(document.getElementById("config-editor").value);
    const resp = await fetch("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(config) });
    const result = await resp.json();
    if (result.status === "ok") { statusEl.textContent = "✓ 配置已保存"; statusEl.className = "save-status success"; }
    else { statusEl.textContent = "✗ 保存失败: " + result.message; statusEl.className = "save-status error"; }
  } catch (e) { statusEl.textContent = "✗ JSON 格式错误: " + e.message; statusEl.className = "save-status error"; }
}

// ============================================================
// Logs
// ============================================================

async function refreshLogs() {
  const el = document.getElementById("log-viewer");
  if (!el) return;
  try {
    const data = await fetch("/api/logs?count=300").then(r => r.json());
    if (!data.logs || data.logs.length === 0) { el.innerHTML = '<p class="text-muted">暂无日志</p>'; return; }
    el.innerHTML = data.logs.map(line => {
      const lower = line.toLowerCase();
      let cls = lower.includes("error") || lower.includes("fail") ? "error" : lower.includes("warn") ? "warn" : lower.includes("trace") ? "trace" : "";
      return `<div class="${cls}">${escapeHtml(line)}</div>`;
    }).join("\n");
  } catch (e) {}
}

// ============================================================
// Utils
// ============================================================

function escapeHtml(text) {
  if (!text) return "";
  const d = document.createElement("div");
  d.textContent = String(text);
  return d.innerHTML;
}
