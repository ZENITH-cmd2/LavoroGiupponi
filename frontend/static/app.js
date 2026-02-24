/* ═══════════════════════════════════════════════════════════════
   CALOR SYSTEMS — Dashboard Application
   ═══════════════════════════════════════════════════════════════ */

// ── State ──
let selectedFiles = [];
const CATEGORY_LABELS = {
    contanti: { label: '💰 Contanti', color: '#d29922' },
    carte_bancarie: { label: '💳 Carte Bancarie', color: '#3fb950' },
    carte_petrolifere: { label: '⛽ Carte Petrolifere', color: '#58a6ff' },
    satispay: { label: '📱 Satispay', color: '#8b949e' },
    crediti: { label: '🟣 Crediti', color: '#bc8cff' },
};

const STATUS_MAP = {
    QUADRATO: { label: '✅ Quadrato', css: 'status-quadrato' },
    QUADRATO_ARROT: { label: '✅ Quadrato (≈)', css: 'status-quadrato-arrot' },
    ANOMALIA_LIEVE: { label: '⚠️ Anomalia lieve', css: 'status-anomalia-lieve' },
    ANOMALIA_GRAVE: { label: '🔴 Anomalia grave', css: 'status-anomalia-grave' },
    NON_TROVATO: { label: '❓ Non trovato', css: 'status-non-trovato' },
    IN_ATTESA: { label: '⏳ In attesa', css: 'status-in-attesa' },
    INCOMPLETO: { label: '❓ Incompleto', css: 'status-incompleto' },
};

// File type detection (mirrors backend FileClassifier)
function classifyFile(name) {
    const n = name.toLowerCase();
    if (n.includes('fortech') || n.includes('file generale') || n.includes('a_file'))
        return { type: 'FORTECH', label: 'Fortech', css: 'badge-fortech' };
    if (n.includes('as400') || n.includes('contanti') || n.includes('giallo'))
        return { type: 'AS400', label: 'AS400', css: 'badge-as400' };
    if (n.includes('numia') || n.includes('carte bancarie') || n.includes('verde'))
        return { type: 'NUMIA', label: 'Numia', css: 'badge-numia' };
    if (n.includes('carte petrolifere') || n.includes('azzurro') || (n.includes('ip') && n.includes('carte')))
        return { type: 'IP_CARTE', label: 'iP Carte', css: 'badge-ip-carte' };
    if (n.includes('buoni') || n.includes('rosso'))
        return { type: 'IP_BUONI', label: 'iP Buoni', css: 'badge-ip-buoni' };
    if (n.includes('satispay') || n.includes('grigio'))
        return { type: 'SATISPAY', label: 'Satispay', css: 'badge-satispay' };
    return { type: 'UNKNOWN', label: '???', css: 'badge-unknown' };
}

// ═══════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════

const navItems = document.querySelectorAll('.nav-item');
const views = document.querySelectorAll('.view');

function switchView(viewName) {
    // Update nav
    navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.view === viewName);
    });
    // Update views
    views.forEach(v => {
        v.classList.toggle('active', v.id === `view-${viewName}`);
    });
    // Update title
    const titles = {
        dashboard: '📊 Dashboard',
        upload: '📂 Carica File Excel',
        riconciliazioni: '🔄 Riconciliazioni',
        contanti: '💰 Contanti — Vista Simona',
        impianti: '🏢 Impianti',
        sicurezza: '🔐 Sicurezza',
        'ai-report': '🤖 Report AI',
    };
    document.getElementById('pageTitle').textContent = titles[viewName] || viewName;

    // Load data for the view
    if (viewName === 'dashboard') loadDashboard();
    if (viewName === 'riconciliazioni') loadRiconciliazioni();
    if (viewName === 'contanti') loadContantiBanca();
    if (viewName === 'impianti') loadImpianti();
    if (viewName === 'sicurezza') loadSicurezza();

    // Close mobile sidebar
    document.getElementById('sidebar').classList.remove('open');
}

navItems.forEach(item => {
    item.addEventListener('click', () => switchView(item.dataset.view));
});

// Mobile menu toggle
document.getElementById('menuToggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
});

// ═══════════════════════════════════════════════════════════════
// FILE UPLOAD
// ═══════════════════════════════════════════════════════════════

const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');

// Click to select
uploadZone.addEventListener('click', () => fileInput.click());

// Drag & Drop
uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
});
uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('drag-over');
});
uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    addFiles(e.dataTransfer.files);
});

// File input change
fileInput.addEventListener('change', () => {
    addFiles(fileInput.files);
    fileInput.value = ''; // Reset so same file can be selected again
});

function addFiles(fileList) {
    for (const file of fileList) {
        // Only accept Excel/CSV
        if (!file.name.match(/\.(xlsx|xls|csv)$/i)) continue;
        // Avoid duplicates
        if (selectedFiles.some(f => f.name === file.name && f.size === file.size)) continue;
        selectedFiles.push(file);
    }
    renderFileList();
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderFileList();
}

function clearFiles() {
    selectedFiles = [];
    renderFileList();
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function renderFileList() {
    const container = document.getElementById('fileList');
    const actions = document.getElementById('uploadActions');

    if (selectedFiles.length === 0) {
        container.innerHTML = '';
        actions.style.display = 'none';
        return;
    }

    actions.style.display = 'flex';
    container.innerHTML = selectedFiles.map((file, i) => {
        const cls = classifyFile(file.name);
        return `
            <div class="file-item">
                <span class="file-type-badge ${cls.css}">${cls.label}</span>
                <span class="file-name">${file.name}</span>
                <span class="file-size">${formatSize(file.size)}</span>
                <button class="file-remove" onclick="removeFile(${i})" title="Rimuovi">✕</button>
            </div>
        `;
    }).join('');
}

// ═══════════════════════════════════════════════════════════════
// PROCESS FILES (Upload + Import + Analyze)
// ═══════════════════════════════════════════════════════════════

async function processFiles() {
    if (selectedFiles.length === 0) return;

    const btn = document.getElementById('btnProcess');
    btn.disabled = true;

    // Show progress
    document.getElementById('progressSection').style.display = 'block';
    document.getElementById('resultsSummary').style.display = 'none';

    const fill = document.getElementById('progressFill');
    const phase = document.getElementById('progressPhase');
    const pct = document.getElementById('progressPct');
    const log = document.getElementById('progressLog');

    phase.textContent = 'Caricamento file...';
    pct.textContent = '10%';
    fill.style.width = '10%';
    log.innerHTML = '';
    logLine(log, 'Preparazione upload...');

    // Build FormData
    const formData = new FormData();
    selectedFiles.forEach(f => formData.append('files[]', f));

    try {
        logLine(log, `Invio di ${selectedFiles.length} file al server...`);
        phase.textContent = 'Elaborazione sul server...';
        pct.textContent = '30%';
        fill.style.width = '30%';

        const resp = await fetch('/api/upload', {
            method: 'POST',
            body: formData,
        });

        pct.textContent = '90%';
        fill.style.width = '90%';

        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || 'Errore sconosciuto');
        }

        // Show logs from server
        if (data.logs) {
            data.logs.forEach(msg => logLine(log, msg));
        }

        pct.textContent = '100%';
        fill.style.width = '100%';
        phase.textContent = '✅ Completato!';

        logLine(log, `Importati ${data.files_imported} file, analizzate ${data.days_analyzed} giornate.`);

        // Show results summary
        document.getElementById('resultsSummary').style.display = 'block';
        document.getElementById('resultsStats').textContent =
            `${data.files_imported} file importati — ${data.days_analyzed} giornate elaborate`;

        // Clear selection
        selectedFiles = [];
        renderFileList();

    } catch (err) {
        phase.textContent = '❌ Errore';
        logLine(log, `ERRORE: ${err.message}`);
        pct.textContent = 'Errore';
        fill.style.width = '100%';
        fill.style.background = 'var(--status-danger)';
    } finally {
        btn.disabled = false;
    }
}

function logLine(container, msg) {
    const time = new Date().toLocaleTimeString('it-IT');
    container.innerHTML += `[${time}] ${msg}\n`;
    container.scrollTop = container.scrollHeight;
}

// ═══════════════════════════════════════════════════════════════
// API CALLS & RENDERING
// ═══════════════════════════════════════════════════════════════

async function apiFetch(endpoint) {
    try {
        const resp = await fetch(endpoint);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error(`API error (${endpoint}):`, err);
        return null;
    }
}

function renderStatus(stato) {
    const s = STATUS_MAP[stato] || { label: stato, css: 'status-non-trovato' };
    return `<span class="status-badge ${s.css}">${s.label}</span>`;
}

function renderDiff(val) {
    if (val === null || val === undefined) return '—';
    const v = parseFloat(val);
    if (v === 0) return `<span class="diff-zero">€ 0.00</span>`;
    const cls = v > 0 ? 'diff-positive' : 'diff-negative';
    return `<span class="${cls}">€ ${v >= 0 ? '+' : ''}${v.toFixed(2)}</span>`;
}

function renderMoney(val) {
    if (val === null || val === undefined) return '—';
    return `€ ${parseFloat(val).toLocaleString('it-IT', { minimumFractionDigits: 2 })}`;
}

function renderCatBadge(cat) {
    const c = CATEGORY_LABELS[cat] || { label: cat };
    return `<span class="cat-badge cat-${cat}">${c.label || cat}</span>`;
}

// ── Dashboard ──
async function loadDashboard() {
    const stats = await apiFetch('/api/stats');
    if (stats) {
        setStatValue('statImpianti', stats.total_impianti ?? '—');
        setStatValue('statGiornate', stats.total_giornate ?? '—');
        setStatValue('statQuadrate', stats.quadrate ?? '—');
        setStatValue('statAnomalie', stats.anomalie_aperte ?? '—');
        setStatValue('statGravi', stats.anomalie_gravi ?? '—');
        setStatValue('statRecords', stats.fortech_records ?? '—');
    }
    loadStatoVerifiche();
}

function setStatValue(id, val) {
    const el = document.getElementById(id);
    if (!el) return;
    const valEl = el.querySelector('.stat-value');
    if (valEl) {
        valEl.textContent = val;
        valEl.style.animation = 'none';
        valEl.offsetHeight; // trigger reflow
        valEl.style.animation = 'fadeIn 0.3s ease';
    }
}

async function loadStatoVerifiche() {
    const data = await apiFetch('/api/stato-verifiche');
    const grid = document.getElementById('verificheGrid');

    if (!data || data.length === 0) {
        grid.innerHTML = '<div class="empty-state">Nessun dato disponibile. Carica i file Excel dalla sezione "Carica File".</div>';
        return;
    }

    grid.innerHTML = data.map(imp => {
        const cats = Object.entries(imp.categorie || {}).map(([cat, det]) => {
            const c = CATEGORY_LABELS[cat] || { color: '#8b949e' };
            const sMap = {
                QUADRATO: '#3fb950', QUADRATO_ARROT: '#56d364',
                ANOMALIA_LIEVE: '#d29922', ANOMALIA_GRAVE: '#f85149',
                IN_ATTESA: '#58a6ff', NON_TROVATO: '#8b949e',
            };
            const dotColor = sMap[det.stato] || '#8b949e';
            return `
                <div class="verifiche-row">
                    <div class="verifiche-cat">
                        <span class="verifiche-dot" style="background:${dotColor}"></span>
                        <span>${CATEGORY_LABELS[cat]?.label || cat}</span>
                    </div>
                    ${renderStatus(det.stato)}
                </div>
            `;
        }).join('');

        return `
            <div class="verifiche-card">
                <div class="verifiche-card-header">
                    <h4>${imp.nome}</h4>
                    <span class="verifiche-tipo">${imp.tipo_gestione || 'PRESIDIATO'}</span>
                </div>
                <div class="verifiche-body">
                    ${cats || '<div style="color:var(--text-muted);font-size:12px">Nessuna verifica</div>'}
                </div>
            </div>
        `;
    }).join('');
}

// ── Riconciliazioni ──
async function loadRiconciliazioni() {
    const data = await apiFetch('/api/riconciliazioni');
    const tbody = document.getElementById('riconciliazioniBody');

    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Nessun dato. Carica i file Excel per generare i risultati.</td></tr>';
        return;
    }

    tbody.innerHTML = data.map(r => `
        <tr>
            <td>${r.data || '—'}</td>
            <td>${r.impianto || '—'}</td>
            <td>${renderCatBadge(r.categoria)}</td>
            <td>${renderMoney(r.valore_fortech)}</td>
            <td>${renderMoney(r.valore_reale)}</td>
            <td>${renderDiff(r.differenza)}</td>
            <td>${renderStatus(r.stato)}</td>
            <td style="max-width:200px;font-size:11px;color:var(--text-secondary)">${r.note || ''}</td>
        </tr>
    `).join('');
}

// ── Contanti / Banca (Simona — Conferma Matching) ──

const TIPO_MATCH_LABELS = {
    '1:1_esatto': { label: 'Match Esatto 1:1', icon: '✅', css: 'tm-esatto' },
    '1:1_arrotondato': { label: 'Arrotondamento', icon: '≈', css: 'tm-arrotondato' },
    'cumulativo_2gg': { label: 'Cumulativo 2gg', icon: '📦', css: 'tm-cumulativo' },
    'cumulativo_3gg': { label: 'Cumulativo 3gg', icon: '📦', css: 'tm-cumulativo' },
    'cumulativo_4gg': { label: 'Cumulativo 4gg', icon: '📦', css: 'tm-cumulativo' },
    'nessuno': { label: 'Nessun Match', icon: '❌', css: 'tm-nessuno' },
    'zero': { label: 'Niente Contanti', icon: '—', css: 'tm-zero' },
    '': { label: 'Legacy', icon: '📋', css: 'tm-legacy' },
};

function renderTipoMatch(tipo) {
    const t = TIPO_MATCH_LABELS[tipo] || TIPO_MATCH_LABELS[''];
    return `<span class="tipo-match-badge ${t.css}">${t.icon} ${t.label}</span>`;
}

async function loadContantiBanca() {
    const data = await apiFetch('/api/contanti-banca');
    const container = document.getElementById('contantiList');
    const statsContainer = document.getElementById('contantiStats');

    if (!data || data.length === 0) {
        container.innerHTML = '<div class="empty-state">Nessun dato contanti disponibile. Carica i file Excel per generare i risultati.</div>';
        statsContainer.innerHTML = '';
        return;
    }

    // Summary stats
    const daConfermare = data.filter(r => !r.risolto && r.stato !== 'IN_ATTESA').length;
    const confermati = data.filter(r => r.risolto).length;
    const anomalie = data.filter(r => r.stato === 'ANOMALIA_GRAVE' || r.stato === 'IN_ATTESA').length;
    const totale = data.length;

    statsContainer.innerHTML = `
        <div class="cs-stat cs-stat-warn">
            <div class="cs-stat-value">${daConfermare}</div>
            <div class="cs-stat-label">Da Confermare</div>
        </div>
        <div class="cs-stat cs-stat-ok">
            <div class="cs-stat-value">${confermati}</div>
            <div class="cs-stat-label">Confermati</div>
        </div>
        <div class="cs-stat cs-stat-danger">
            <div class="cs-stat-value">${anomalie}</div>
            <div class="cs-stat-label">Anomalie</div>
        </div>
        <div class="cs-stat">
            <div class="cs-stat-value">${totale}</div>
            <div class="cs-stat-label">Totale</div>
        </div>
    `;

    // Render cards
    container.innerHTML = data.map((r, idx) => {
        const statoInfo = STATUS_MAP[r.stato] || { label: r.stato, css: 'status-non-trovato' };
        const isCumulativo = (r.tipo_match || '').startsWith('cumulativo');
        const isConfermato = r.risolto;
        const isAnomalia = r.stato === 'ANOMALIA_GRAVE' || r.stato === 'IN_ATTESA';

        // Card border color
        let cardClass = 'cc-card';
        if (isConfermato) cardClass += ' cc-confermato';
        else if (isAnomalia) cardClass += ' cc-anomalia';
        else if (r.stato === 'QUADRATO' || r.stato === 'QUADRATO_ARROT') cardClass += ' cc-ok';

        // Differenza display
        const diff = parseFloat(r.differenza) || 0;
        const diffCls = diff === 0 ? 'diff-zero' : diff > 0 ? 'diff-positive' : 'diff-negative';

        // Build detail section for expand
        let detailHtml = '';

        // Matching breakdown
        detailHtml += '<div class="cc-detail-section">';
        detailHtml += '<div class="cc-detail-title">Dettaglio Calcolo</div>';
        detailHtml += '<div class="cc-calc-grid">';
        detailHtml += `<div class="cc-calc-row"><span class="cc-calc-label">Fortech (teorico):</span><span class="cc-calc-value">${renderMoney(r.contanti_teorico)}</span></div>`;
        detailHtml += `<div class="cc-calc-row"><span class="cc-calc-label">AS400 (versato):</span><span class="cc-calc-value">${renderMoney(r.contanti_versato)}</span></div>`;
        detailHtml += `<div class="cc-calc-row cc-calc-result"><span class="cc-calc-label">Differenza:</span><span class="cc-calc-value ${diffCls}">${renderDiff(r.differenza)}</span></div>`;
        detailHtml += '</div>';
        detailHtml += '</div>';

        // Type info
        if (isCumulativo) {
            const nGiorni = parseInt((r.tipo_match || '').replace(/[^0-9]/g, '')) || 2;
            const tolleranza = nGiorni * 5;
            detailHtml += '<div class="cc-detail-section cc-detail-cumul">';
            detailHtml += `<div class="cc-detail-title">📦 Versamento Cumulativo (${nGiorni} giorni)</div>`;
            detailHtml += `<div class="cc-detail-info">Il gestore ha versato ${nGiorni} giornate insieme. Tolleranza applicata: <strong>&plusmn;${tolleranza} EUR</strong> (${nGiorni} &times; 5 EUR)</div>`;
            detailHtml += '</div>';
        }

        // Notes
        if (r.note) {
            detailHtml += '<div class="cc-detail-section">';
            detailHtml += `<div class="cc-detail-title">Note</div>`;
            detailHtml += `<div class="cc-detail-info">${r.note}</div>`;
            detailHtml += '</div>';
        }

        // Verification info
        if (r.verificato_da) {
            detailHtml += '<div class="cc-detail-section">';
            detailHtml += `<div class="cc-detail-title">Verifica</div>`;
            detailHtml += `<div class="cc-detail-info">Verificato da <strong>${r.verificato_da}</strong> il ${r.data_verifica || '—'}</div>`;
            detailHtml += '</div>';
        }

        // Action buttons
        let actionsHtml = '';
        if (!isConfermato) {
            actionsHtml = `
                <div class="cc-actions">
                    <button class="btn cc-btn-conferma" onclick="confermaContanti(${r.id}, 'conferma', this)" title="Conferma matching">
                        ✅ Conferma
                    </button>
                    <button class="btn cc-btn-segnala" onclick="segnalaContanti(${r.id}, this)" title="Segnala anomalia">
                        ❌ Segnala
                    </button>
                </div>
            `;
        } else {
            actionsHtml = '<div class="cc-actions"><span class="cc-confermato-badge">✅ Confermato</span></div>';
        }

        return `
            <div class="${cardClass}" id="cc-card-${r.id}">
                <div class="cc-header" onclick="this.parentElement.classList.toggle('cc-expanded')">
                    <span class="cc-date">${r.data || '—'}</span>
                    <span class="cc-impianto">${r.impianto || '—'}</span>
                    <span class="cc-amounts">
                        <span class="cc-teorico">${renderMoney(r.contanti_teorico)}</span>
                        <span class="cc-arrow">&rarr;</span>
                        <span class="cc-versato">${renderMoney(r.contanti_versato)}</span>
                    </span>
                    <span class="${diffCls} cc-diff">${renderDiff(r.differenza)}</span>
                    ${renderTipoMatch(r.tipo_match)}
                    <span class="status-badge ${statoInfo.css}">${statoInfo.label}</span>
                    <span class="cc-expand-icon">▼</span>
                </div>
                <div class="cc-body">
                    ${detailHtml}
                    ${actionsHtml}
                </div>
            </div>
        `;
    }).join('');
}

async function confermaContanti(id, azione, btnEl) {
    if (btnEl) btnEl.disabled = true;
    try {
        const resp = await fetch('/api/contanti-conferma', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, azione })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Errore');

        // Update card visually
        const card = document.getElementById(`cc-card-${id}`);
        if (card) {
            card.classList.add('cc-confermato');
            card.classList.remove('cc-anomalia', 'cc-ok');
            const actions = card.querySelector('.cc-actions');
            if (actions) actions.innerHTML = '<span class="cc-confermato-badge">✅ Confermato</span>';
        }
    } catch (err) {
        alert('Errore: ' + err.message);
        if (btnEl) btnEl.disabled = false;
    }
}

async function segnalaContanti(id, btnEl) {
    const nota = prompt('Motivo della segnalazione (opzionale):') || '';
    if (btnEl) btnEl.disabled = true;
    try {
        const resp = await fetch('/api/contanti-conferma', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, azione: 'rifiuta', nota })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Errore');

        // Update card visually
        const card = document.getElementById(`cc-card-${id}`);
        if (card) {
            card.classList.remove('cc-ok');
            card.classList.add('cc-anomalia');
            const actions = card.querySelector('.cc-actions');
            if (actions) actions.innerHTML = '<span class="cc-segnalato-badge">❌ Segnalato</span>';
        }
    } catch (err) {
        alert('Errore: ' + err.message);
        if (btnEl) btnEl.disabled = false;
    }
}

// ── Impianti ──
async function loadImpianti() {
    const data = await apiFetch('/api/impianti');
    const grid = document.getElementById('impiantiGrid');

    if (!data || data.length === 0) {
        grid.innerHTML = '<div class="empty-state">Nessun impianto registrato</div>';
        return;
    }

    grid.innerHTML = data.map(imp => {
        const safeName = (imp.nome || 'N/A').replace(/'/g, "\\'");
        return `
        <div class="impianto-card" onclick="openAndamento(${imp.id}, '${safeName}')" style="cursor:pointer">
            <div class="impianto-name">${imp.nome || 'N/A'}</div>
            <div class="impianto-code">PV: ${imp.codice_pv || '—'} · ${imp.tipo || 'PRESIDIATO'}</div>
            <div class="impianto-stats">
                <span class="impianto-stat" style="color:var(--status-ok)">✅ ${imp.cnt_ok || 0}</span>
                <span class="impianto-stat" style="color:var(--status-warn)">⚠️ ${imp.cnt_warn || 0}</span>
                <span class="impianto-stat" style="color:var(--status-danger)">🔴 ${imp.cnt_grave || 0}</span>
            </div>
            <div style="font-size:10px;color:var(--text-muted);margin-top:8px">🔍 Clicca per andamento</div>
        </div>`;
    }).join('');
}

// ── Sicurezza (Taleggio) ──
async function loadSicurezza() {
    const data = await apiFetch('/api/sicurezza');
    const tbody = document.getElementById('sicurezzaBody');

    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Nessun evento di sicurezza registrato</td></tr>';
        return;
    }

    tbody.innerHTML = data.map(r => `
        < tr >
            <td style="white-space:nowrap">${r.timestamp || '—'}</td>
            <td>${r.giorno || '—'}</td>
            <td>${r.impianto || '—'}</td>
            <td>${renderMoney(r.importo_fortech)}</td>
            <td>${renderMoney(r.importo_atteso)}</td>
            <td>${renderDiff(r.differenza)}</td>
            <td>${r.autorizzata === true ? '✅ Si' : r.autorizzata === false ? '❌ No' : '—'}</td>
            <td style="font-size:11px;color:var(--text-secondary)">${r.note || ''}</td>
        </tr >
        `).join('');
}

// ═══════════════════════════════════════════════════════════════
// MODAL / ANDAMENTO
// ═══════════════════════════════════════════════════════════════

function closeModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('modalOverlay').style.display = 'none';
    document.body.style.overflow = '';
}

// Close on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

async function openAndamento(id, nome) {
    const overlay = document.getElementById('modalOverlay');
    const body = document.getElementById('modalBody');
    const title = document.getElementById('modalTitle');
    const subtitle = document.getElementById('modalSubtitle');

    title.textContent = `🏢 ${nome}`;
    subtitle.textContent = 'Caricamento andamento...';
    body.innerHTML = '<div class="empty-state" style="padding:40px">⏳ Caricamento dati...</div>';
    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    try {
        const resp = await fetch(`/api/impianti/${id}/andamento`);
        const data = await resp.json();

        if (!resp.ok) throw new Error(data.error || 'Errore');

        const imp = data.impianto;
        subtitle.textContent = `PV: ${imp.codice_pv || '—'} · ${imp.tipo || 'PRESIDIATO'} · ${data.totale_giorni} giornate analizzate`;

        renderAndamento(body, data);
    } catch (err) {
        body.innerHTML = '<div class="empty-state" style="color:var(--status-danger)">Errore: ' + err.message + '</div>';
    }
}

function renderAndamento(container, data) {
    const stats = data.stats || {};
    const giorni = data.giorni || [];

    // Summary stats
    const totalOk = (stats.QUADRATO || 0) + (stats.QUADRATO_ARROT || 0);
    const totalWarn = stats.ANOMALIA_LIEVE || 0;
    const totalGrave = stats.ANOMALIA_GRAVE || 0;
    const totalMissing = (stats.NON_TROVATO || 0) + (stats.IN_ATTESA || 0);

    let html = '<div class="trend-summary">';
    html += '<div class="trend-stat"><div class="trend-stat-value" style="color:var(--status-ok)">' + totalOk + '</div><div class="trend-stat-label">Quadrature</div></div>';
    html += '<div class="trend-stat"><div class="trend-stat-value" style="color:var(--status-warn)">' + totalWarn + '</div><div class="trend-stat-label">Anomalie Lievi</div></div>';
    html += '<div class="trend-stat"><div class="trend-stat-value" style="color:var(--status-danger)">' + totalGrave + '</div><div class="trend-stat-label">Anomalie Gravi</div></div>';
    html += '<div class="trend-stat"><div class="trend-stat-value" style="color:var(--text-muted)">' + totalMissing + '</div><div class="trend-stat-label">Dati Mancanti</div></div>';
    html += '<div class="trend-stat"><div class="trend-stat-value">' + data.totale_giorni + '</div><div class="trend-stat-label">Giorni Totali</div></div>';
    html += '</div>';

    // Bar chart: one row per day
    const stateColors = {
        QUADRATO: '#3fb950', QUADRATO_ARROT: '#56d364',
        ANOMALIA_LIEVE: '#d29922', ANOMALIA_GRAVE: '#f85149',
        NON_TROVATO: '#8b949e', IN_ATTESA: '#58a6ff', INCOMPLETO: '#8b949e'
    };
    const stateIcons = {
        QUADRATO: '\u2705', QUADRATO_ARROT: '\u2705', ANOMALIA_LIEVE: '\u26a0\ufe0f',
        ANOMALIA_GRAVE: '\ud83d\udd34', NON_TROVATO: '\u2753', IN_ATTESA: '\u23f3'
    };

    if (giorni.length > 0) {
        html += '<div class="trend-chart"><div class="trend-chart-title">Andamento Giornaliero</div>';

        const maxCats = Math.max(...giorni.map(g => Object.keys(g.categorie).length), 1);

        for (const g of giorni) {
            const cats = Object.entries(g.categorie);
            const dateShort = (g.data || '').substring(0, 10);
            const statusIcon = stateIcons[g.stato_peggiore] || '\u2753';

            const segWidth = 100 / maxCats;
            let segments = '';
            cats.forEach(([cat, det]) => {
                const color = stateColors[det.stato] || '#8b949e';
                segments += '<div class="trend-bar-segment" style="width:' + segWidth + '%;background:' + color + '" title="' + cat + ': ' + det.stato + '"></div>';
            });

            html += '<div class="trend-bar-row" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display===\'none\'?\'block\':\'none\'">';
            html += '<span class="trend-bar-date">' + dateShort + '</span>';
            html += '<div class="trend-bar-track">' + segments + '</div>';
            html += '<span class="trend-bar-value">' + renderDiff(g.totale_diff) + '</span>';
            html += '<span class="trend-bar-status">' + statusIcon + '</span>';
            html += '</div>';

            // Expandable detail card
            html += '<div class="trend-day-card" style="display:none;margin:0 0 8px 102px"><div class="trend-day-cats">';
            cats.forEach(([cat, det]) => {
                html += '<div class="trend-cat-row">';
                html += '<span class="trend-cat-name">' + renderCatBadge(cat) + '</span>';
                html += '<span class="trend-cat-vals">';
                html += '<span>Teorico: ' + renderMoney(det.teorico) + '</span>';
                html += '<span>Reale: ' + renderMoney(det.reale) + '</span>';
                html += '<span>' + renderDiff(det.differenza) + '</span>';
                html += '</span>';
                html += '<span class="trend-cat-status">' + renderStatus(det.stato) + '</span>';
                html += '</div>';
            });
            html += '</div></div>';
        }
        html += '</div>';
    } else {
        html += '<div class="empty-state">Nessun dato disponibile per questo impianto</div>';
    }

    container.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════════
// AI REPORT
// ═══════════════════════════════════════════════════════════════

function simpleMarkdownToHtml(md) {
    if (!md) return '';
    let html = md
        // Escape HTML first
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        // Headers
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        // Bold and italic
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Code
        .replace(/`(.+?)`/g, '<code>$1</code>')
        // Horizontal rule
        .replace(/^---$/gm, '<hr>')
        // Unordered lists
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        // Line breaks to paragraphs
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
    // Wrap lists
    html = html.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>');
    // Clean up consecutive uls
    html = html.replace(/<\/ul>\s*<ul>/g, '');
    return '<p>' + html + '</p>';
}

async function generateAIReport() {
    const btn = document.getElementById('btnGenerateAI');
    const status = document.getElementById('aiStatus');
    const container = document.getElementById('aiReportContainer');
    const body = document.getElementById('aiReportBody');
    const timestamp = document.getElementById('aiTimestamp');

    btn.disabled = true;
    status.textContent = 'Analisi in corso...';
    status.className = 'ai-status loading';
    container.style.display = 'none';

    try {
        const resp = await fetch('/api/ai-report', { method: 'POST' });
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || 'Errore API');
        }

        // Render markdown report
        body.innerHTML = simpleMarkdownToHtml(data.report);
        timestamp.textContent = new Date().toLocaleString('it-IT');
        container.style.display = 'block';
        status.textContent = 'Report generato!';
        status.className = 'ai-status';

    } catch (err) {
        status.textContent = 'Errore: ' + err.message;
        status.className = 'ai-status';
        status.style.color = 'var(--status-danger)';
    } finally {
        btn.disabled = false;
    }
}

// ═══════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
});
