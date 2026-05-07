// AI Viral Shorts Generator — single-page UI
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const state = {
  style: "fruit_head",
  theme: "",
  themeHint: "",
  runtime: 25,
  sceneCount: 8,
  ideas: [],
  themes: [],
  slug: null,
  pack: null,
  videos_done: new Set(),
  password: localStorage.getItem("app_password") || "",
};

// All API/file fetches go through this so the password header is always attached on public deploys.
function authHeaders(extra = {}) {
  const h = { ...extra };
  if (state.password) h["X-App-Password"] = state.password;
  return h;
}

const STEP_ORDER = ["setup", "ideas", "pack", "images", "videos", "assemble", "done"];
const visitedSteps = new Set(["setup"]);

function show(id) {
  $$(".step").forEach(s => s.classList.remove("active"));
  $(`#${id}`).classList.add("active");
  $(`#${id}`).scrollIntoView({ behavior: "smooth", block: "start" });
  const key = id.replace("step-", "");
  visitedSteps.add(key);
  const idx = STEP_ORDER.indexOf(key);
  $$("#stepper li").forEach((li, i) => {
    li.classList.toggle("current", i === idx);
    li.classList.toggle("done", i < idx);
    // Make any visited step clickable
    if (visitedSteps.has(STEP_ORDER[i])) {
      li.classList.add("clickable");
      li.style.cursor = "pointer";
    }
  });
}

// Wire clicks on stepper LIs — jump to any visited step
$$("#stepper li").forEach((li) => {
  li.addEventListener("click", () => {
    const key = li.dataset.step;
    if (visitedSteps.has(key)) {
      show(`step-${key}`);
    }
  });
});

function showError(message) {
  const el = $("#error-banner");
  el.innerHTML = `<button class="close" title="dismiss">×</button><strong>Error:</strong>\n${escapeHtml(message)}`;
  el.hidden = false;
  el.querySelector(".close").addEventListener("click", () => el.hidden = true);
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

function clearError() {
  $("#error-banner").hidden = true;
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: authHeaders({ "Content-Type": "application/json", ...(opts.headers || {}) }),
  });
  if (res.status === 401) {
    state.password = "";
    localStorage.removeItem("app_password");
    await promptForPassword();
    // Retry once with the new password
    return api(path, opts);
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body.error) detail = body.error;
      if (body.trace) detail += "\n\n" + body.trace;
    } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
}

// --- Step 1: setup ---

async function loadStyles() {
  const styles = await api("/api/styles");
  const sel = $("#style");
  sel.innerHTML = "";
  for (const [key, val] of Object.entries(styles)) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = val.label;
    sel.appendChild(opt);
  }
  sel.value = state.style;
  sel.addEventListener("change", e => state.style = e.target.value);
  $("#theme").addEventListener("input", e => state.theme = e.target.value);
  $("#runtime").addEventListener("input", e => state.runtime = parseInt(e.target.value || "25", 10));
  const sc = $("#scene-count");
  if (sc) sc.addEventListener("change", e => state.sceneCount = parseInt(e.target.value, 10));
}

async function loadThemes() {
  const data = await api("/api/themes");
  state.themes = data.presets || [];
  const sel = $("#theme-preset");
  sel.innerHTML = "";
  // Default: surprise me
  sel.appendChild(new Option("— Surprise me (no theme) —", ""));
  for (const t of state.themes) {
    const opt = new Option(t.label, t.key);
    opt.title = t.hint;
    sel.appendChild(opt);
  }
  sel.appendChild(new Option("Custom — type your own…", "__custom__"));

  sel.addEventListener("change", () => {
    const v = sel.value;
    const wrap = $("#theme-custom-wrap");
    if (v === "__custom__") {
      wrap.hidden = false;
      state.theme = $("#theme").value || "";
      state.themeHint = "";
    } else if (v === "") {
      wrap.hidden = true;
      state.theme = "";
      state.themeHint = "";
    } else {
      wrap.hidden = true;
      const preset = state.themes.find(t => t.key === v);
      state.theme = preset ? preset.label : "";
      state.themeHint = preset ? preset.hint : "";
    }
  });
}

async function loadMusic() {
  const tracks = await api("/api/music");
  const sel = $("#music");
  // Wipe existing options except the placeholder, then re-add
  [...sel.options].forEach((opt, i) => { if (i > 0) opt.remove(); });
  for (const t of tracks) {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    sel.appendChild(opt);
  }
  // Wire preview on first call only
  if (!sel.dataset.wired) {
    sel.dataset.wired = "1";
    sel.addEventListener("change", () => {
      const audio = $("#music-preview");
      if (sel.value) {
        audio.src = `/api/music/${encodeURIComponent(sel.value)}`;
        audio.hidden = false;
        audio.play().catch(() => {});
      } else {
        audio.pause();
        audio.hidden = true;
      }
    });
  }
}

async function uploadMusicFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/upload_music", { method: "POST", body: fd, headers: authHeaders() });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { msg = (await res.json()).error || msg; } catch {}
    showError("Music upload failed: " + msg);
    return;
  }
  const j = await res.json();
  await loadMusic();
  // Auto-select the freshly uploaded track
  const sel = $("#music");
  sel.value = j.filename;
  sel.dispatchEvent(new Event("change"));
}

function wireMusicDrop() {
  const drop = $("#music-drop");
  if (!drop) return;
  drop.addEventListener("click", () => {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.accept = "audio/mp3,audio/wav,audio/m4a,audio/*";
    inp.onchange = () => inp.files[0] && uploadMusicFile(inp.files[0]);
    inp.click();
  });
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", async e => {
    e.preventDefault();
    drop.classList.remove("over");
    if (e.dataTransfer.files[0]) await uploadMusicFile(e.dataTransfer.files[0]);
  });
}
wireMusicDrop();

$("#btn-ideas").addEventListener("click", async () => {
  clearError();
  $("#btn-ideas").disabled = true;
  $("#btn-ideas").textContent = "Generating…";
  try {
    const data = await api("/api/ideas", {
      method: "POST",
      body: JSON.stringify({
        style: state.style,
        theme: state.theme,
        theme_hint: state.themeHint,
        runtime_seconds: state.runtime,
        scene_count: state.sceneCount,
      }),
    });
    state.ideas = data.ideas;
    renderIdeas();
    show("step-ideas");
  } catch (e) {
    showError(e.message);
  } finally {
    $("#btn-ideas").disabled = false;
    $("#btn-ideas").textContent = "Generate 10 story ideas";
  }
});

// --- Step 2: ideas ---

function renderIdeas() {
  const list = $("#ideas-list");
  list.innerHTML = "";
  state.ideas.forEach((idea) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${idea}</span>`;
    li.addEventListener("click", () => pickIdea(idea));
    list.appendChild(li);
  });
}

async function pickIdea(idea) {
  clearError();
  $$("#ideas-list li").forEach(li => li.style.opacity = "0.4");
  try {
    const data = await api("/api/scene_pack", {
      method: "POST",
      body: JSON.stringify({
        idea,
        style: state.style,
        runtime_seconds: state.runtime,
        scene_count: state.sceneCount,
      }),
    });
    state.slug = data.slug;
    state.pack = data.pack;
    renderPack();
    show("step-pack");
  } catch (e) {
    showError(e.message);
    $$("#ideas-list li").forEach(li => li.style.opacity = "1");
  }
}

// --- Step 3: pack ---

function renderPack() {
  $("#pack-meta").innerHTML = `<strong>${state.pack.title}</strong> — ${state.pack.logline || ""}`;
  $("#pack-pre").textContent = JSON.stringify(state.pack, null, 2);
}

$("#btn-images").addEventListener("click", async () => {
  await api("/api/images/start", {
    method: "POST",
    body: JSON.stringify({ slug: state.slug }),
  });
  renderImageGrid();
  show("step-images");
  pollImages();
});

// --- Step 4: images ---

function renderImageGrid() {
  const grid = $("#img-grid");
  const n = state.pack?.scene_count || state.sceneCount || 8;
  $("#img-progress").max = n;
  grid.innerHTML = "";
  for (let i = 1; i <= n; i++) {
    const cell = document.createElement("div");
    cell.className = "cell";
    cell.id = `img-cell-${i}`;
    cell.innerHTML = `<span class="num">${i}</span>scene ${i}`;
    grid.appendChild(cell);
  }
}

async function refreshImageThumbnails() {
  const data = await api(`/api/scene_pack/${state.slug}`);
  let anyDone = false;
  data.images.forEach((url, idx) => {
    if (!url) return;
    anyDone = true;
    const n = idx + 1;
    const cell = $(`#img-cell-${n}`);
    if (cell && !cell.querySelector("img")) {
      cell.innerHTML =
        `<span class="num">${n}</span>` +
        `<img src="${url}?t=${Date.now()}" alt="scene ${n}">` +
        `<a class="dl" href="${url}" download="scene_${n}.png" title="Download scene ${n}" onclick="event.stopPropagation()">⬇</a>`;
    }
  });
  // Reveal the toolbar as soon as any image is on disk
  if (anyDone) $("#img-toolbar").hidden = false;
}

async function pollImages() {
  $("#img-grid").classList.add("loading");
  const tick = async () => {
    const job = await api(`/api/job/${state.slug}`);
    if (job.total) $("#img-progress").max = job.total;
    if (job.progress != null) $("#img-progress").value = job.progress;
    $("#img-status").textContent = job.status || "";
    await refreshImageThumbnails();

    if (job.status === "error") {
      $("#img-grid").classList.remove("loading");
      $("#img-status").innerHTML = `<span style="color:var(--bad)">Error: ${escapeHtml(job.error || "")}</span>`;
      $("#btn-to-videos").hidden = false;
      return;
    }
    if (job.status === "done") {
      $("#img-grid").classList.remove("loading");
      $("#btn-to-videos").hidden = false;
      return;
    }
    setTimeout(tick, 1500);
  };
  tick();
}

$("#btn-to-videos").addEventListener("click", async () => {
  await renderScenes();
  show("step-videos");
});

// Bulk download all 8 images as a single .zip
$("#btn-download-zip").addEventListener("click", () => {
  if (!state.slug) return;
  window.location.href = `/api/download_zip/${state.slug}?kind=images`;
});

// Open the project folder in the OS file manager
$("#btn-open-folder").addEventListener("click", async () => {
  if (!state.slug) return;
  try {
    await api("/api/open_folder", {
      method: "POST",
      body: JSON.stringify({ slug: state.slug }),
    });
  } catch (e) {
    showError(e.message);
  }
});

// --- Step 5: videos ---

async function renderScenes() {
  const data = await api(`/api/scene_pack/${state.slug}`);
  state.pack = data.pack;
  state.videos_done = new Set(data.videos.map((v, i) => v ? i + 1 : null).filter(Boolean));
  const list = $("#scenes-list");
  list.innerHTML = "";
  data.pack.scenes.forEach((s, idx) => {
    const i = idx + 1;
    const card = document.createElement("div");
    card.className = "scene-card";
    if (state.videos_done.has(i)) card.classList.add("done");
    const imgUrl = data.images[idx];
    const vidUrl = data.videos[idx];
    card.innerHTML = `
      <div class="thumb">${imgUrl ? `<img src="${imgUrl}" alt="">` : "?"}</div>
      <div>
        <h3>Scene ${i}: ${s.voiceover_script.speaker || "—"}</h3>
        <pre>${escapeHtml(s.combined_veo_prompt)}</pre>
        <div class="row">
          <button class="copy-btn" data-copy="${i}">Copy prompt</button>
          <div class="drop ${state.videos_done.has(i) ? "done" : ""}" data-scene="${i}">
            ${state.videos_done.has(i) ? "✓ uploaded — drop to replace" : "Drop scene_" + i + ".mp4 here (or click to choose)"}
          </div>
        </div>
        ${vidUrl ? `<video src="${vidUrl}" controls></video>` : ""}
      </div>
    `;
    list.appendChild(card);
  });

  // wire copy buttons
  $$("button.copy-btn[data-copy]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const i = parseInt(btn.dataset.copy, 10) - 1;
      await copyText(data.pack.scenes[i].combined_veo_prompt);
      btn.textContent = "✓ copied";
      setTimeout(() => btn.textContent = "Copy prompt", 1200);
    });
  });

  // wire drop zones
  $$(".drop[data-scene]").forEach(zone => {
    const scene = parseInt(zone.dataset.scene, 10);
    zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("over"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("over"));
    zone.addEventListener("drop", async e => {
      e.preventDefault();
      zone.classList.remove("over");
      const file = e.dataTransfer.files[0];
      if (file) await uploadVideo(scene, file);
    });
    zone.addEventListener("click", () => {
      const inp = document.createElement("input");
      inp.type = "file";
      inp.accept = "video/mp4,video/*";
      inp.onchange = () => inp.files[0] && uploadVideo(scene, inp.files[0]);
      inp.click();
    });
  });

  updateContinueButton();
}

async function uploadVideo(scene, file) {
  clearError();
  const fd = new FormData();
  fd.append("slug", state.slug);
  fd.append("scene", scene);
  fd.append("file", file);
  const res = await fetch("/api/upload_video", { method: "POST", body: fd, headers: authHeaders() });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { msg = (await res.json()).error || msg; } catch {}
    showError("Upload failed: " + msg);
    return;
  }
  const j = await res.json();
  state.videos_done = new Set(j.videos_done);
  await renderScenes();
}

function updateContinueButton() {
  const n = state.pack?.scene_count || state.sceneCount || 8;
  $("#btn-to-assemble").hidden = state.videos_done.size < n;
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}

$("#btn-to-assemble").addEventListener("click", () => show("step-assemble"));

// --- Step 6: assemble ---

$("#btn-assemble").addEventListener("click", async () => {
  $("#btn-assemble").disabled = true;
  await api("/api/assemble", {
    method: "POST",
    body: JSON.stringify({ slug: state.slug, music: $("#music").value || null }),
  });
  pollAssemble();
});

async function pollAssemble() {
  const tick = async () => {
    const job = await api(`/api/job/${state.slug}`);
    $("#assemble-status").textContent = `${job.status || ""}${job.progress != null ? ` (${job.progress}/${job.total})` : ""}`;
    if (job.status === "error") {
      $("#assemble-status").innerHTML = `<span style="color:var(--bad)">Error: ${job.error}</span>`;
      $("#btn-assemble").disabled = false;
      return;
    }
    if (job.status === "done") {
      await showFinal();
      return;
    }
    setTimeout(tick, 1500);
  };
  tick();
}

// --- Step 7: done ---

async function showFinal() {
  $("#final-video").src = `/files/${state.slug}/final.mp4?t=${Date.now()}`;
  const meta = await api(`/api/metadata/${state.slug}`);
  const md = $("#metadata");
  md.innerHTML = `
    <div class="field"><div class="label">Title <button class="copy-btn" data-c="t">Copy</button></div><div class="value" id="m-t">${escapeHtml(meta.title || "")}</div></div>
    <div class="field"><div class="label">Description <button class="copy-btn" data-c="d">Copy</button></div><div class="value" id="m-d">${escapeHtml(meta.description || "")}</div></div>
    <div class="field"><div class="label">Hashtags <button class="copy-btn" data-c="h">Copy</button></div><div class="value" id="m-h">${(meta.hashtags || []).map(h => "#" + h).join(" ")}</div></div>
  `;
  md.querySelectorAll("button.copy-btn").forEach(b => {
    b.addEventListener("click", async () => {
      const map = { t: "m-t", d: "m-d", h: "m-h" };
      await copyText(md.querySelector("#" + map[b.dataset.c]).textContent);
      b.textContent = "✓"; setTimeout(() => b.textContent = "Copy", 1000);
    });
  });
  show("step-done");
}

// --- Resume menu ---

$("#resume-link").addEventListener("click", async (e) => {
  e.preventDefault();
  revealGenerator();
  clearError();
  const list = await api("/api/projects");
  if (!list.length) { showError("No projects yet — generate one first."); return; }
  const choice = prompt("Resume which?\n\n" + list.map((p, i) => `${i + 1}. ${p.title} (${p.stage})`).join("\n"));
  const idx = parseInt(choice, 10) - 1;
  if (Number.isNaN(idx) || !list[idx]) return;
  state.slug = list[idx].slug;
  const data = await api(`/api/scene_pack/${state.slug}`);
  state.pack = data.pack;
  state.sceneCount = data.pack.scene_count || data.pack.scenes?.length || 8;
  state.videos_done = new Set(data.videos.map((v, i) => v ? i + 1 : null).filter(Boolean));
  if (data.state.stage === "done") { await showFinal(); }
  else if (state.videos_done.size === 8) { show("step-assemble"); }
  else if (data.images.some(Boolean)) { await renderScenes(); show("step-videos"); }
  else { renderPack(); show("step-pack"); }
});

async function loadDemo() {
  let manifest;
  try {
    manifest = await api("/api/demo");
  } catch {
    return;
  }
  // Pick a hero video — prefer the polished final reel, fall back to the first scene clip
  const heroSrc =
    (manifest.finals && manifest.finals[0]) ||
    (manifest.scene_videos && manifest.scene_videos[0]);
  if (heroSrc) {
    const v = $("#hero-demo");
    v.src = heroSrc;
    v.play().catch(() => {/* autoplay can fail until user interacts; that's fine */});
  }

  // Marquee — duplicate the strip so the loop is seamless
  const track = $("#marquee-track");
  if (track && manifest.images && manifest.images.length) {
    const html = manifest.images.map(src =>
      `<img src="${src}" alt="" loading="lazy">`
    ).join("");
    track.innerHTML = html + html;  // duplicated for the seamless loop
  }

  // Gallery grid
  const grid = $("#gallery-grid");
  if (grid && manifest.images && manifest.images.length) {
    grid.innerHTML = manifest.images.slice(0, 8).map((src, i) => `
      <div class="tile">
        <img src="${src}" alt="Demo scene ${i + 1}" loading="lazy">
        <span class="tag">Scene ${i + 1}</span>
      </div>
    `).join("");
  }
}

function revealGenerator() {
  const gen = $("#generator");
  if (!gen) return;
  gen.hidden = false;
  setTimeout(() => {
    gen.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 50);
}

$("#btn-get-started")?.addEventListener("click", revealGenerator);

async function loadHealth() {
  const h = await api("/api/health");
  const el = $("#provider-status");
  const textCls = h.groq_configured ? "ok" : "warn";
  const imgCls = h.gemini_configured ? "ok" : "warn";
  el.innerHTML =
    `text: <span class="${textCls}">${escapeHtml(h.text_provider)}</span> · ` +
    `image: <span class="${imgCls}">${escapeHtml(h.image_provider)}</span>`;
  return h;
}

async function promptForPassword() {
  // Simple browser prompt — keeps UI surface minimal. Stores in localStorage on success.
  for (let i = 0; i < 5; i++) {
    const pw = window.prompt(
      i === 0
        ? "This deployment is password-protected. Enter the access password:"
        : "Wrong password. Try again:"
    );
    if (!pw) {
      alert("A password is required to use this app. Reload the page to try again.");
      throw new Error("Password required");
    }
    const res = await fetch("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw }),
    });
    if (res.ok) {
      state.password = pw;
      localStorage.setItem("app_password", pw);
      return;
    }
  }
  throw new Error("Too many failed attempts");
}

async function init() {
  // Health is auth-exempt — safe to call before we know if a password is needed.
  let h;
  try { h = await loadHealth(); }
  catch (e) { console.error("Health check failed:", e); return; }

  // If the deploy is gated and we don't yet have a working password, prompt.
  if (h.password_required && !state.password) {
    try { await promptForPassword(); }
    catch { return; }
  }

  // Now load the rest. If our stored password is stale, api() will re-prompt + retry.
  loadStyles().catch(() => {});
  loadThemes().catch(() => {});
  loadMusic().catch(() => {});
  loadDemo().catch(() => {});
}

init();
