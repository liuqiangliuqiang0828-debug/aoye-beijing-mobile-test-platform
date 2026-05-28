/** Token 测试平台 v2.1 前端控制脚本 */
const API = location.origin;

// ── Navigation ──
document.querySelectorAll('.nav-item').forEach(el => {
  el.onclick = () => {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.getElementById(el.dataset.panel)?.classList.add('active');
    if (el.dataset.panel === 'p-results') loadResults();
    if (el.dataset.panel === 'p-reports') loadReports();
    if (el.dataset.panel === 'p-settings') loadSettings();
  };
});

// ── Helpers ──
async function api(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' }, ...opts
  });
  return r.json();
}

function log(msg) {
  const box = document.getElementById('logBox');
  const t = new Date().toLocaleTimeString('zh-CN');
  box.textContent += `[${t}] ${msg}\n`;
  box.scrollTop = box.scrollHeight;
}

// ── Dashboard Init ──
async function init() {
  try {
    // Load tracks
    const tracks = await api('/api/config/tracks');
    const sel = document.getElementById('trackSel');
    if (tracks.tracks) {
      tracks.tracks.forEach(t => {
        const o = document.createElement('option');
        o.value = t; o.textContent = t;
        if (t === 'all') o.value = 'all';
        sel.appendChild(o);
      });
    }

    // Load models
    const models = await api('/api/config/models');
    renderModels(models.models || []);

    // Load metrics
    await refreshMetrics();
  } catch (e) {
    log('❌ 初始化失败: ' + e.message);
  }
}

function renderModels(models) {
  const tb = document.getElementById('monTB');
  tb.innerHTML = '';
  let en = 0;
  models.forEach((m, i) => {
    const ok = m.enabled !== false;
    if (ok) en++;
    const ctrl = `'${m.id}','base_url":"${m.base_url||'—'}"'` ;
    tb.innerHTML += `<tr>
      <td>${i+1}</td>
      <td><strong>${m.name}</strong></td>
      <td><span class="badge badgeB">${m.track}</span></td>
      <td style="font-size:11px;color:#64748b">${m.base_url||'未配置'}</td>
      <td><span class="badge ${ok?'badgeG':'badgeR'}">${ok?'启用':'禁用'}</span></td>
      <td style="font-size:11px">${m.api_key ? m.api_key.substring(0,8)+'****' : '—'}</td>
    </tr>`;
  });
  document.getElementById('mTotal').textContent = models.length;
  document.getElementById('mEn').textContent = en;
}

async function refreshMetrics() {
  try {
    const m = await api('/api/metrics/summary');
    const o = m.overall || {};
    document.getElementById('statTotalReq').textContent = o.total_requests || 0;
    document.getElementById('statSuccess').textContent = o.success_count || 0;
    document.getElementById('statError').textContent = o.error_count || 0;
    const total = o.total_requests || 1;
    document.getElementById('statSuccessRate').textContent =
      Math.round(((o.success_count||0)/total)*100) + '%';

    // Render track status
    const grid = document.getElementById('tracksGrid');
    grid.innerHTML = '';
    const tracks = m.tracks || {};
    Object.entries(tracks).forEach(([track, trackData]) => {
      let totalReq = 0, success = 0, err = 0;
      Object.values(trackData || {}).forEach(tm => {
        totalReq += tm.total_requests || 0;
        success += tm.success_count || 0;
        err += tm.error_count || 0;
      });
      const rate = totalReq > 0 ? Math.round((success/totalReq)*100) : 0;
      const cls = totalReq === 0 ? '' : rate === 100 ? 'dok' : rate > 80 ? '' : 'dng';
      grid.innerHTML += `<div class="sTrack ${cls}">
        <h3>${track}</h3>
        <div class="stat">任务: ${totalReq} | 成功: ${success} | 失败: ${err} | 成功率: ${rate}%</div>
      </div>`;
    });
  } catch (e) {
    console.warn('metrics refresh failed', e);
  }
}

// ── Test Controls ──
async function doRunAll() {
  const conc = parseInt(document.getElementById('concIn').value) || 10;
  log('▶ 启动全部赛道测试 (并发=' + conc + ')...');
  const rp = new URL('/api/test/run-all', API);
  try {
    const res = await fetch(rp, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ concurrent: conc }),
    });
    const data = await res.json();
    log('✅ 测试已提交: ' + data.run_id);
  } catch (er) {
    log('❌ 提交失败: ' + er.message);
  }
}

async function doRunSel() {
  const track = document.getElementById('trackSel').value;
  const conc = parseInt(document.getElementById('concIn').value) || 10;
  if (track === 'all') { await doRunAll(); return; }
  log(`▶ 启动赛道: ${track} (并发=${conc})...`);
  const rp = new URL(`/api/test/run-track/${track}`, API);
  try {
    const res = await fetch(rp, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ concurrent: conc }),
    });
    const data = await res.json();
    log('✅ 测试已提交: ' + data.run_id);
  } catch (er) {
    log('❌ 提交失败: ' + er.message);
  }
}

async function doCancel() {
  try {
    const res = await fetch(new URL('/api/test/cancel-all', API), { method: 'POST' });
    await res.json();
    log('⏹ 已取消所有任务');
  } catch (e) {
    log('取消失败: ' + e.message);
  }
}

let refreshTimer = null;
async function doRefresh() {
  await refreshMetrics();
}

// Auto-refresh every 5s
setInterval(refreshMetrics, 5000);
init();

// ── Results ──
async function loadResults() {
  try {
    const data = await api('/api/results');
    const el = document.getElementById('resultsList');
    if (!data.runs || Object.keys(data.runs).length === 0) {
      el.innerHTML = '<p style="color:#999">暂无测试结果</p>';
      return;
    }
    let html = '';
    Object.entries(data.runs).forEach(([runId, run]) => {
      const sum = run.summary || {};
      html += `<div class="result-entry">
        <h4>${run.track || 'all'} | ${run.run_id || runId} | ${run.completed_at || ''}</h4>
        <span class="badge ${run.status==='completed'?'badgeG':'badgeY'}">${run.status}</span>
        <span class="badge badgeB">${run.models_tested || 0} 模型</span>
        ${run.error ? '<p style="color:#dc2626;margin-top:6px">'+run.error+'</p>' : ''}
      </div>`;
    });
    el.innerHTML = html;
  } catch (e) {
    document.getElementById('resultsList').innerHTML = `<p style="color:#dc2626">加载失败: ${e.message}</p>`;
  }
}

// ── Settings ──
async function loadSettings() {
  try {
    const s = await api('/api/settings');
    document.getElementById('setDefaultConc').value = s.default_concurrent || 10;
    // Render model configs
    const modelsData = await api('/api/config/models');
    const container = document.getElementById('modelConfigs');
    container.innerHTML = '';
    (modelsData.models || []).forEach(m => {
      container.innerHTML += `<div class="card" style="margin-bottom:10px">
        <h4>${m.name} <span class="badge badgeB">${m.track}</span></h4>
        <div class="grid3">
          <div class="field"><label>Base URL</label>
            <input value="${m.base_url||''}" onchange="updateModelCfg('${m.id}','base_url',this.value)" placeholder="http://ip:port/v1"></div>
          <div class="field"><label>API Key</label>
            <input value="${m.api_key||''}" onchange="updateModelCfg('${m.id}','api_key',this.value)" type="password"></div>
          <div class="field"><label>Model Name</label>
            <input value="${m.model_name||''}" onchange="updateModelCfg('${m.id}','model_name',this.value)" placeholder="Qwen3.5-35B-A3B"></div>
        </div>
      </div>`;
    });
  } catch (e) {
    document.getElementById('modelConfigs').innerHTML = `<p style="color:#dc2626">加载失败: ${e.message}</p>`;
  }
}

async function updateModelCfg(modelId, field, value) {
  try {
    await api(`/api/settings/models/${modelId}`, {
      method: 'POST',
      body: JSON.stringify({ [field]: value }),
    });
  } catch (e) {
    alert('更新失败: ' + e.message);
  }
}

async function saveSettings() {
  try {
    await api('/api/settings', {
      method: 'PUT',
      body: JSON.stringify({
        default_concurrent: parseInt(document.getElementById('setDefaultConc').value) || 10,
      }),
    });
    alert('设置已保存');
  } catch (e) {
    alert('保存失败: ' + e.message);
  }
}

// ── Reports ──
async function loadReports() {
  try {
    const r = await api('/api/report');
    const el = document.getElementById('reportList');
    if (!r.reports || r.reports.length === 0) {
      el.innerHTML = '<p style="color:#999">暂无报告（运行测试后自动生成）</p>';
      return;
    }
    let html = '';
    r.reports.forEach(f => {
      html += `<div class="card" style="margin-bottom:8px">
        📄 <a href="/reports/${f}" target="_blank">${f}</a>
      </div>`;
    });
    el.innerHTML = html;
  } catch (e) {
    document.getElementById('reportList').innerHTML = `<p style="color:#dc2626">加载失败: ${e.message}</p>`;
  }
}
