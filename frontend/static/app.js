/* ═══════════════════════════════════════════════════════════════
   CALOR SYSTEMS — Web App Logic (Desktop App Replica)
   Handles frame switching, file upload, and data fetching.
   ═══════════════════════════════════════════════════════════════ */

(function () {
    "use strict";

    const $ = (id) => document.getElementById(id);
    const $$ = (sel) => document.querySelectorAll(sel);

    /* ─── State ─── */
    let selectedFiles = []; // Array of File objects

    /* ─── Navigation ─── */
    function showFrame(frameId) {
        $$(".frame").forEach(el => el.classList.remove("active"));
        const target = $(frameId);
        if (target) {
            target.classList.add("active");
        }
    }

    /* ─── File Handling ─── */
    function renderFileList() {
        const list = $("file-list");
        const header = $("file-list-header");
        const btnUpload = $("btnUpload");

        list.innerHTML = "";

        if (selectedFiles.length === 0) {
            list.innerHTML = `
                <div style="text-align: center; color: #777; padding: 2rem;">
                    Nessun file ancora selezionato.<br>
                    Clicca «Aggiungi File» per iniziare.
                </div>`;
            header.textContent = "File selezionati (0)";
            btnUpload.disabled = true;
            return;
        }

        header.textContent = `File selezionati (${selectedFiles.length})`;
        btnUpload.disabled = false;

        selectedFiles.forEach((file, index) => {
            const row = document.createElement("div");
            row.style.cssText = "display: flex; align-items: center; padding: 8px; border-bottom: 1px solid #333; font-size: 13px;";
            row.innerHTML = `
                <span style="font-weight: bold; width: 30px; color: #888;">${index + 1}.</span>
                <span style="flex: 1;">${file.name}</span>
                <span style="color: #666; font-size: 11px;">${(file.size / 1024).toFixed(1)} KB</span>
            `;
            list.appendChild(row);
        });
    }

    function handleFileSelect(event) {
        const files = Array.from(event.target.files);
        // Avoid duplicates by name (simple check)
        files.forEach(f => {
            if (!selectedFiles.some(sf => sf.name === f.name)) {
                selectedFiles.push(f);
            }
        });
        renderFileList();
        event.target.value = ""; // Reset input
    }

    /* ─── Processing ─── */
    async function startUpload() {
        if (selectedFiles.length === 0) return;

        showFrame("ProcessingFrame");
        const bar = $("proc-bar");
        const log = $("proc-log");
        const phase = $("proc-phase");

        // Reset UI
        log.innerHTML = "";
        phase.textContent = "Caricamento file al server…";

        const logMsg = (msg) => {
            const line = document.createElement("div");
            line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            log.appendChild(line);
            log.scrollTop = log.scrollHeight;
        }

        logMsg(`Preparazione caricamento di ${selectedFiles.length} file...`);

        const formData = new FormData();
        selectedFiles.forEach(f => formData.append("files[]", f));

        try {
            const res = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.error || res.statusText);
            }

            const data = await res.json();

            logMsg("✅ Caricamento completato.");
            logMsg("Elaborazione server avviata...");

            if (data.logs && data.logs.length) {
                data.logs.forEach(l => logMsg("> " + l));
            }

            logMsg(`✅ Importati: ${data.files_imported} file.`);
            logMsg(`✅ Analizzati: ${data.days_analyzed} giorni.`);

            phase.textContent = "Elaborazione completata!";

            setTimeout(() => {
                showFrame("ResultsFrame");
                loadResults();
                // Clear state
                selectedFiles = [];
                renderFileList();
            }, 1200);

        } catch (e) {
            phase.textContent = "Errore durante l'elaborazione.";
            phase.style.color = "#e74c3c"; // Red
            logMsg("❌ ERRORE CRITICO:");
            logMsg(e.message);
            // Don't auto-advance on error
        }
    }

    /* ─── Loading Results ─── */
    async function loadResults() {
        const container = $("cards-container");
        const summary = $("res-summary");

        container.innerHTML = '<div class="loader" style="margin: 2rem auto;"></div>';

        try {
            const res = await fetch("/api/riconciliazioni?limit=50");
            if (!res.ok) throw new Error("Errore API");
            const data = await res.json();

            container.innerHTML = ""; // Clear loader

            if (!data || data.length === 0) {
                container.innerHTML = '<p class="description">Nessun risultato disponibile.</p>';
                summary.textContent = "0 giornate analizzate";
                return;
            }

            // Calc summary
            const ok = data.filter(r => r.stato === "QUADRATO").length;
            const warn = data.filter(r => r.stato.includes("ANOMALIA")).length;
            summary.textContent = `${data.length} giornate analizzate — ✅ ${ok} OK  ⚠️ ${warn} con anomalie`;

            /* Group by Date */
            const grouped = {};
            data.forEach(row => {
                const key = row.data; // Date
                if (!grouped[key]) grouped[key] = { date: row.data, items: [], status: "QUADRATO" };
                grouped[key].items.push(row);

                // Downgrade status
                if (row.stato === "ANOMALIA_GRAVE") grouped[key].status = "ANOMALIA_GRAVE";
                else if (row.stato === "ANOMALIA_LIEVE" && grouped[key].status !== "ANOMALIA_GRAVE") grouped[key].status = "ANOMALIA_LIEVE";
            });

            // Sort dates descending
            const dates = Object.keys(grouped).sort().reverse();

            dates.forEach(d => {
                const g = grouped[d];
                // Render Card
                const card = document.createElement("div");
                card.className = "result-card";

                // Status Header
                let statusLabel = "✅ Quadrato";
                let statusColorClass = "color-ok";
                if (g.status === "ANOMALIA_GRAVE") { statusLabel = "🔴 Anomalia Grave"; statusColorClass = "color-err"; }
                else if (g.status === "ANOMALIA_LIEVE") { statusLabel = "⚠️ Anomalia Lieve"; statusColorClass = "color-warn"; }

                let itemsHtml = "";
                g.items.forEach(item => {
                    let sLabel = "✅";
                    let sClass = "color-ok";
                    if (item.stato === "ANOMALIA_GRAVE") { sLabel = "🔴"; sClass = "color-err"; }
                    else if (item.stato === "ANOMALIA_LIEVE") { sLabel = "⚠️"; sClass = "color-warn"; }
                    else if (item.stato === "IN_ATTESA") { sLabel = "⏳"; sClass = "color-info"; }

                    const catName = formatCategory(item.categoria);
                    const diffStr = parseFloat(item.differenza) > 0 ? `+${Number(item.differenza).toFixed(2)}` : Number(item.differenza).toFixed(2);

                    itemsHtml += `
                        <div class="detail-row">
                            <span class="detail-status ${sClass}">${sLabel}</span>
                            <span class="detail-text">
                                ${catName}: <span class="${sClass}">${item.stato.replace("_", " ")}</span> (diff €${diffStr})
                                ${item.note ? ` — <i>${item.note}</i>` : ""}
                            </span>
                        </div>
                    `;
                });

                card.innerHTML = `
                    <div class="card-header">
                        <div class="date-label">📅 ${d}</div>
                        <div class="status-label ${statusColorClass}">${statusLabel}</div>
                    </div>
                    <div class="card-details">
                        ${itemsHtml}
                    </div>
                `;
                container.appendChild(card);
            });

        } catch (e) {
            console.error(e);
            container.innerHTML = '<p class="description" style="color:red">Errore caricamento dati.</p>';
        }
    }

    function formatCategory(cat) {
        const map = {
            "CONTANTI": "Contanti",
            "CARTE_BANCARIE": "Carte Bancarie",
            "CARTE_PETROLIFERE": "Carte Petrolifere",
            "BUONI": "Buoni",
            "SATISPAY": "Satispay",
            "CREDITO": "Credito"
        };
        return map[cat] || cat;
    }

    /* ─── Event Listeners ─── */
    document.addEventListener("DOMContentLoaded", () => {

        // Start -> Go to Input
        $("btnStart").addEventListener("click", () => {
            showFrame("InputFrame");
        });

        // Skip to Results
        $("lnkSkip").addEventListener("click", (e) => {
            e.preventDefault();
            loadResults();
            showFrame("ResultsFrame");
        });

        // Input Frame Controls
        $("btnAddFile").addEventListener("click", () => $("fileInput").click());
        $("fileInput").addEventListener("change", handleFileSelect);
        $("btnClearFiles").addEventListener("click", () => {
            selectedFiles = [];
            renderFileList();
        });
        $("btnUpload").addEventListener("click", startUpload);
        $("btnBackInput").addEventListener("click", () => showFrame("WelcomeFrame"));

        // Results Frame Controls
        $("btnHome").addEventListener("click", () => showFrame("WelcomeFrame"));

        // Floating Scroll Buttons
        $("btnScrollUp").addEventListener("click", () => {
            const activeFrame = document.querySelector(".frame.active");
            if (activeFrame) {
                const scrollArea = activeFrame.querySelector(".scroll-area");
                if (scrollArea) scrollArea.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });

        $("btnScrollDown").addEventListener("click", () => {
            const activeFrame = document.querySelector(".frame.active");
            if (activeFrame) {
                const scrollArea = activeFrame.querySelector(".scroll-area");
                if (scrollArea) scrollArea.scrollTo({ top: scrollArea.scrollHeight, behavior: 'smooth' });
            }
        });

    });

})();
