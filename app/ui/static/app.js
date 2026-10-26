const $ = (id) => document.getElementById(id);
const files = $("files");
const text = $("text");
const confirmed = $("confirmed");
const voice = $("voice");
const previewButton = $("previewButton");
const previewStatus = $("previewStatus");
const previewAudio = $("preview");
const generateButton = $("generateButton");
const ocrButton = $("ocrButton");
const ocrStatus = $("ocrStatus");
const ttsStatus = $("ttsStatus");
const fileSummary = $("fileSummary");
const textStats = $("textStats");
const editorOcrBadge = $("editorOcrBadge");
const ocrProgressLine = $("ocrProgressLine");
const pronunciationForm = $("pronunciationForm");
const pronunciationId = $("pronunciationId");
const pronunciationSource = $("pronunciationSource");
const pronunciationSpoken = $("pronunciationSpoken");
const pronunciationSave = $("pronunciationSave");
const pronunciationTry = $("pronunciationTry");
const pronunciationCancel = $("pronunciationCancel");
const pronunciationStatus = $("pronunciationStatus");
const pronunciationPreview = $("pronunciationPreview");
const pronunciationList = $("pronunciationList");
const pronunciationCount = $("pronunciationCount");
const navTabBulletin = $("navTabBulletin");
const navTabPronunciation = $("navTabPronunciation");
const viewBulletin = $("viewBulletin");
const viewPronunciation = $("viewPronunciation");
const linkOpenDictionary = $("linkOpenDictionary");
const navDictionaryCount = $("navDictionaryCount");
const pronunciationSearch = $("pronunciationSearch");
let pronunciationEntries = [];

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/[&<>"']/g, (m) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[m]));
}

function setButtonLoading(button, isLoading, loadingText = "") {
  if (!button) return;
  button.disabled = isLoading;
  if (isLoading) {
    button.classList.add("is-loading");
    if (!button.dataset.originalHtml) {
      button.dataset.originalHtml = button.innerHTML;
    }
    button.innerHTML = `
      <svg class="spinner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.25"/>
        <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-linecap="round"/>
      </svg>
      <span>${escapeHtml(loadingText || "Đang xử lý…")}</span>
    `;
  } else {
    button.classList.remove("is-loading");
    if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
    }
  }
}

function setStatus(element, message, kind = "") {
  if (!element) return;
  if (!message) {
    element.innerHTML = "";
    element.className = "status";
    return;
  }

  if (kind === "loading-ocr") {
    element.className = "status loading";
    element.innerHTML = `
      <div class="status-content-row">
        <svg class="spinner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.25"/>
          <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-linecap="round"/>
        </svg>
        <span class="status-text">${escapeHtml(message)}</span>
      </div>
      <div class="status-loading-bar">
        <div class="status-loading-bar-inner"></div>
      </div>
    `;
    return;
  }

  if (kind === "loading-tts") {
    element.className = "status loading tts-loading";
    element.innerHTML = `
      <div class="status-content-row">
        <div class="soundwave-anim">
          <span></span><span></span><span></span><span></span><span></span>
        </div>
        <span class="status-text">${escapeHtml(message)}</span>
      </div>
      <div class="status-loading-bar tts">
        <div class="status-loading-bar-inner"></div>
      </div>
    `;
    return;
  }

  if (kind === "loading-preview") {
    element.className = "status loading";
    element.innerHTML = `
      <div class="status-content-row">
        <div class="soundwave-anim">
          <span></span><span></span><span></span><span></span><span></span>
        </div>
        <span class="status-text">${escapeHtml(message)}</span>
      </div>
      <div class="status-loading-bar">
        <div class="status-loading-bar-inner"></div>
      </div>
    `;
    return;
  }

  if (kind === "ok") {
    element.className = "status ok";
    element.innerHTML = `
      <div class="status-content-row">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width: 15px; height: 15px; flex-shrink: 0;">
          <path d="M20 6L9 17l-5-5"/>
        </svg>
        <span class="status-text">${escapeHtml(message)}</span>
      </div>
    `;
    return;
  }

  if (kind === "error") {
    element.className = "status error";
    element.innerHTML = `
      <div class="status-content-row">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 15px; height: 15px; flex-shrink: 0;">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span class="status-text">${escapeHtml(message)}</span>
      </div>
    `;
    return;
  }

  element.className = `status ${kind}`.trim();
  element.textContent = message;
}

async function errorMessage(response) {
  try {
    const data = await response.json();
    return data.detail || "Không thể xử lý yêu cầu.";
  } catch {
    return "Không thể xử lý yêu cầu.";
  }
}

function resetPronunciationForm() {
  if (!pronunciationForm) return;
  pronunciationForm.reset();
  pronunciationId.value = "";
  pronunciationCancel.hidden = true;
  pronunciationSave.querySelector("span").textContent = "Thêm vào từ điển";
}

function pronunciationButton(label, title, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `pronunciation-mini-button ${className}`.trim();
  button.textContent = label;
  button.title = title;
  button.setAttribute("aria-label", title);
  return button;
}

async function savePronunciationEntry(entry, enabled) {
  const response = await fetch(`/api/pronunciations/${encodeURIComponent(entry.id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: entry.source, spoken: entry.spoken, enabled }),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()).entry;
}

async function playPronunciation(spoken) {
  const value = (spoken || "").trim();
  if (!value) throw new Error("Hãy nhập cách đọc trước khi nghe thử.");
  setStatus(pronunciationStatus, "Đang tạo âm thanh nghe thử…", "loading-preview");
  const response = await fetch("/api/pronunciations/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spoken: value, voice: voice.value }),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  const blob = await response.blob();
  pronunciationPreview.src = URL.createObjectURL(blob);
  pronunciationPreview.hidden = false;
  pronunciationPreview.play().catch(() => {});
  setStatus(pronunciationStatus, "Đang phát cách đọc thử.", "ok");
}

function switchView(viewName) {
  if (viewName === "pronunciation") {
    if (navTabBulletin) navTabBulletin.classList.remove("active");
    if (navTabPronunciation) navTabPronunciation.classList.add("active");
    if (viewBulletin) viewBulletin.hidden = true;
    if (viewPronunciation) viewPronunciation.hidden = false;
    if (pronunciationSource) pronunciationSource.focus();
  } else {
    if (navTabBulletin) navTabBulletin.classList.add("active");
    if (navTabPronunciation) navTabPronunciation.classList.remove("active");
    if (viewBulletin) viewBulletin.hidden = false;
    if (viewPronunciation) viewPronunciation.hidden = true;
  }
}

if (navTabBulletin) navTabBulletin.addEventListener("click", () => switchView("bulletin"));
if (navTabPronunciation) navTabPronunciation.addEventListener("click", () => switchView("pronunciation"));
if (linkOpenDictionary) linkOpenDictionary.addEventListener("click", () => switchView("pronunciation"));

function renderPronunciations(filterText = "") {
  if (!pronunciationList) return;
  pronunciationList.replaceChildren();
  const total = pronunciationEntries.length;
  if (pronunciationCount) pronunciationCount.textContent = `${total} mục`;
  if (navDictionaryCount) navDictionaryCount.textContent = `${total}`;

  const query = (filterText || (pronunciationSearch ? pronunciationSearch.value : "")).trim().toLowerCase();
  const filtered = query
    ? pronunciationEntries.filter(
        (item) =>
          (item.source || "").toLowerCase().includes(query) ||
          (item.spoken || "").toLowerCase().includes(query)
      )
    : pronunciationEntries;

  if (!filtered.length) {
    const empty = document.createElement("div");
    empty.className = "pronunciation-empty";
    empty.textContent = query
      ? "Không tìm thấy mục phát âm nào khớp với từ khóa tìm kiếm."
      : "Chưa có mục phát âm tùy chỉnh.";
    pronunciationList.append(empty);
    return;
  }

  for (const entry of filtered) {
    const row = document.createElement("div");
    row.className = `pronunciation-entry${entry.enabled ? "" : " is-disabled"}`;

    const entryText = document.createElement("div");
    entryText.className = "pronunciation-entry-text";
    const source = document.createElement("span");
    source.className = "pronunciation-entry-source";
    source.textContent = entry.source;
    const arrow = document.createElement("span");
    arrow.className = "pronunciation-entry-arrow";
    arrow.textContent = "→";
    const spoken = document.createElement("span");
    spoken.className = "pronunciation-entry-spoken";
    spoken.textContent = entry.spoken;
    entryText.append(source, arrow, spoken);

    const actions = document.createElement("div");
    actions.className = "pronunciation-entry-actions";
    const toggleLabel = document.createElement("label");
    toggleLabel.className = "pronunciation-toggle";
    toggleLabel.title = entry.enabled ? "Đang áp dụng" : "Đang tắt";
    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.checked = entry.enabled;
    toggle.setAttribute("aria-label", `Bật hoặc tắt ${entry.source}`);
    toggle.addEventListener("change", async () => {
      try {
        const updated = await savePronunciationEntry(entry, toggle.checked);
        pronunciationEntries = pronunciationEntries.map((item) => item.id === updated.id ? updated : item);
        renderPronunciations();
        setStatus(pronunciationStatus, toggle.checked ? "Đã bật mục phát âm." : "Đã tắt mục phát âm.", "ok");
      } catch (error) {
        toggle.checked = !toggle.checked;
        setStatus(pronunciationStatus, error.message, "error");
      }
    });
    toggleLabel.append(toggle);

    const listen = pronunciationButton("▶", `Nghe thử ${entry.spoken}`);
    listen.addEventListener("click", async () => {
      try { await playPronunciation(entry.spoken); }
      catch (error) { setStatus(pronunciationStatus, error.message, "error"); }
    });
    const edit = pronunciationButton("✎", `Sửa ${entry.source}`);
    edit.addEventListener("click", () => {
      pronunciationId.value = entry.id;
      pronunciationSource.value = entry.source;
      pronunciationSpoken.value = entry.spoken;
      pronunciationCancel.hidden = false;
      pronunciationSave.querySelector("span").textContent = "Lưu thay đổi";
      pronunciationSource.focus();
    });
    const remove = pronunciationButton("×", `Xóa ${entry.source}`, "delete");
    remove.addEventListener("click", async () => {
      if (!window.confirm(`Xóa “${entry.source}” khỏi từ điển phát âm?`)) return;
      try {
        const response = await fetch(`/api/pronunciations/${encodeURIComponent(entry.id)}`, { method: "DELETE" });
        if (!response.ok) throw new Error(await errorMessage(response));
        pronunciationEntries = pronunciationEntries.filter((item) => item.id !== entry.id);
        if (pronunciationId.value === entry.id) resetPronunciationForm();
        renderPronunciations();
        setStatus(pronunciationStatus, "Đã xóa mục khỏi từ điển phát âm.", "ok");
      } catch (error) {
        setStatus(pronunciationStatus, error.message, "error");
      }
    });
    actions.append(toggleLabel, listen, edit, remove);
    row.append(entryText, actions);
    pronunciationList.append(row);
  }
}

async function loadPronunciations() {
  if (!pronunciationList) return;
  try {
    const response = await fetch("/api/pronunciations");
    if (!response.ok) throw new Error(await errorMessage(response));
    pronunciationEntries = (await response.json()).entries || [];
    renderPronunciations();
  } catch (error) {
    setStatus(pronunciationStatus, error.message, "error");
  }
}

if (pronunciationForm) {
  pronunciationForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const editingId = pronunciationId.value;
    const previous = pronunciationEntries.find((entry) => entry.id === editingId);
    const payload = {
      source: pronunciationSource.value,
      spoken: pronunciationSpoken.value,
      enabled: previous ? previous.enabled : true,
    };
    try {
      pronunciationSave.disabled = true;
      pronunciationSave.querySelector("span").textContent = editingId ? "Đang lưu…" : "Đang thêm…";
      const response = await fetch(editingId ? `/api/pronunciations/${encodeURIComponent(editingId)}` : "/api/pronunciations", {
        method: editingId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const saved = (await response.json()).entry;
      if (editingId) {
        pronunciationEntries = pronunciationEntries.map((entry) => entry.id === saved.id ? saved : entry);
      } else {
        pronunciationEntries.push(saved);
      }
      resetPronunciationForm();
      renderPronunciations();
      setStatus(pronunciationStatus, editingId ? "Đã cập nhật cách đọc." : "Đã thêm vào từ điển phát âm.", "ok");
    } catch (error) {
      setStatus(pronunciationStatus, error.message, "error");
    } finally {
      pronunciationSave.disabled = false;
      pronunciationSave.querySelector("span").textContent = pronunciationId.value ? "Lưu thay đổi" : "Thêm vào từ điển";
    }
  });
  pronunciationCancel.addEventListener("click", resetPronunciationForm);
  pronunciationTry.addEventListener("click", async () => {
    try { await playPronunciation(pronunciationSpoken.value); }
    catch (error) { setStatus(pronunciationStatus, error.message, "error"); }
  });
}

if (pronunciationSearch) {
  pronunciationSearch.addEventListener("input", (e) => {
    renderPronunciations(e.target.value);
  });
}

function updateTextStats() {
  if (!textStats || !text) return;
  const val = text.value || "";
  const charCount = val.length;
  const wordCount = val.trim() ? val.trim().split(/\s+/).length : 0;
  textStats.textContent = `${charCount.toLocaleString("vi-VN")} ký tự • ${wordCount.toLocaleString("vi-VN")} từ`;
}

if (text) {
  text.addEventListener("input", updateTextStats);
}

if (files) {
  files.addEventListener("change", () => {
    if (!fileSummary) return;
    if (!files.files || !files.files.length) {
      fileSummary.textContent = "Chọn hoặc kéo thả ảnh JPG, PNG hoặc PDF";
    } else if (files.files.length === 1) {
      fileSummary.textContent = `Đã chọn: ${files.files[0].name}`;
    } else {
      fileSummary.textContent = `Đã chọn ${files.files.length} tệp (${files.files[0].name}, ...)`;
    }
  });
}

if (voice) {
  voice.addEventListener("change", () => {
    setStatus(previewStatus, "");
  });
}

function isNewsVoice(label) {
  const l = (label || "").toLowerCase();
  return l.includes("tin tức") || l.includes("tin tuc");
}

async function loadVoices() {
  try {
    const response = await fetch("/api/voices");
    if (!response.ok) throw new Error(await errorMessage(response));
    const data = await response.json();
    const sorted = [...(data.voices || [])].sort((a, b) => {
      const aNews = isNewsVoice(a.label);
      const bNews = isNewsVoice(b.label);
      if (aNews && !bNews) return -1;
      if (!aNews && bNews) return 1;
      return 0;
    });
    voice.replaceChildren(...sorted.map((item) => new Option(item.label, item.value)));
    voice.disabled = false;
  } catch (error) {
    voice.replaceChildren(new Option("Không tải được giọng đọc", ""));
    setStatus(previewStatus, error.message, "error");
  }
}

function applyOcr(payload, complete = false) {
  text.value = payload.text || "";
  confirmed.checked = false;
  updateTextStats();
  if (complete) {
    const base = `Hoàn tất: đã nhận diện ${payload.page_count} trang bằng ${payload.engine}.`;
    const warning = payload.warnings?.length ? `\nLưu ý: ${payload.warnings.join("; ")}` : "";
    setStatus(ocrStatus, base + warning, payload.warnings?.length ? "error" : "ok");
  }
}

ocrButton.addEventListener("click", async () => {
  if (!files.files.length) {
    return setStatus(ocrStatus, "Hãy chọn ít nhất một ảnh JPG, PNG hoặc PDF.", "error");
  }
  setButtonLoading(ocrButton, true, "ĐANG NHẬN DIỆN OCR…");
  confirmed.checked = false;
  if (text) text.classList.add("is-processing");
  if (editorOcrBadge) editorOcrBadge.classList.remove("hidden");
  if (ocrProgressLine) ocrProgressLine.classList.remove("hidden");
  setStatus(ocrStatus, "Đang tải tệp và chuẩn bị nhận diện…", "loading-ocr");

  const form = new FormData();
  for (const file of files.files) {
    form.append("files", file);
  }

  try {
    const response = await fetch("/api/ocr/stream", { method: "POST", body: form });
    if (!response.ok || !response.body) throw new Error(await errorMessage(response));

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const events = buffer.split("\n\n");
      buffer = events.pop();

      for (const raw of events) {
        const name = raw.match(/^event: (.+)$/m)?.[1];
        const body = raw.match(/^data: (.+)$/m)?.[1];
        if (!name || !body) continue;
        const payload = JSON.parse(body);

        if (name === "status") {
          setStatus(ocrStatus, payload.message || "Đang nhận diện…", "loading-ocr");
        }
        if (name === "page") {
          applyOcr(payload, false);
          setStatus(ocrStatus, `Đang nhận diện: đã xử lý trang ${payload.page_count}…`, "loading-ocr");
        }
        if (name === "complete") {
          applyOcr(payload, true);
        }
        if (name === "error") {
          setStatus(ocrStatus, payload.message, "error");
        }
      }
      if (done) break;
    }
  } catch (error) {
    setStatus(ocrStatus, error.message, "error");
  } finally {
    setButtonLoading(ocrButton, false);
    if (text) text.classList.remove("is-processing");
    if (editorOcrBadge) editorOcrBadge.classList.add("hidden");
    if (ocrProgressLine) ocrProgressLine.classList.add("hidden");
  }
});

if (previewButton) {
  previewButton.addEventListener("click", async () => {
    try {
      setButtonLoading(previewButton, true, "Đang tạo câu nghe thử…");
      setStatus(previewStatus, "Đang tổng hợp giọng nói nghe thử…", "loading-preview");
      const r = await fetch("/api/voice-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice: voice.value }),
      });
      if (!r.ok) throw new Error(await errorMessage(r));
      const blob = await r.blob();
      if (previewAudio) {
        previewAudio.src = URL.createObjectURL(blob);
        previewAudio.play().catch(() => {});
      }
      setStatus(previewStatus, "Đã tạo câu nghe thử thành công.", "ok");
    } catch (error) {
      setStatus(previewStatus, error.message, "error");
    } finally {
      setButtonLoading(previewButton, false);
    }
  });
}

if (generateButton) {
  generateButton.addEventListener("click", async () => {
    try {
      setButtonLoading(generateButton, true, "ĐANG TẠO BẢN TIN MP3…");
      setStatus(ttsStatus, "Hệ thống AI đang đọc và tạo file âm thanh MP3, vui lòng chờ…", "loading-tts");
      const r = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.value, confirmed: confirmed.checked, voice: voice.value }),
      });
      if (!r.ok) throw new Error(await errorMessage(r));
      const data = await r.json();
      $("output").src = data.url;
      const download = $("download");
      download.href = data.url;
      download.hidden = false;
      download.title = `Tải ${data.filename}`;
      const downloadLabel = $("downloadLabel");
      if (downloadLabel) {
        downloadLabel.textContent = "Tải file MP3";
      } else {
        download.textContent = `⬇ Tải ${data.filename}`;
      }
      const outputFileInfo = $("outputFileInfo");
      const outputFilename = $("outputFilename");
      if (outputFileInfo && outputFilename) {
        outputFilename.textContent = data.filename;
        outputFileInfo.hidden = false;
      }
      const normalized = data.normalizations?.length ? ` Đã áp dụng: ${data.normalizations.join("; ")}.` : "";
      setStatus(ttsStatus, `Đã tạo MP3 thành công (${data.segment_count} đoạn xử lý).${normalized}`, "ok");
    } catch (error) {
      setStatus(ttsStatus, error.message, "error");
    } finally {
      setButtonLoading(generateButton, false);
    }
  });
}

loadVoices();
loadPronunciations();
updateTextStats();
