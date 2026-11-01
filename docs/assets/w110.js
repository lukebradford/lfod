// Rule 110 unit cell player: FWKnightship's six-cell W110 torus in Live Free or Die, simulated with WebGL2.
// The torus is 4320 x 7200, stored 32 cells per texel (R32UI). Each unit cell is 720 wide; its Rule 110 state is
// a lone dot at (346 + 720j, 0), read every 7200 generations, when one sweep of the lightspeed fleets has finished.
(async function () {
  "use strict";
  const W = 4320, H = 7200, NW = W / 32, CELL = 720, DOTX = 346, DOTY = 0, PERIOD = 7200;
  const $ = (id) => document.getElementById(id);
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const rgb = (s) => {
    const c = document.createElement("canvas").getContext("2d"); c.fillStyle = s; c.fillRect(0, 0, 1, 1);
    const d = c.getImageData(0, 0, 1, 1).data; return [d[0] / 255, d[1] / 255, d[2] / 255];
  };

  // ---- Pattern ----
  const rleText = await (await fetch("files/lfod-flying-rule110-simulator.rle")).text();
  function pack(text) {
    const words = new Uint32Array(NW * H);
    const body = text.split("\n").filter((l) => !/^\s*(#|x\s*=)/.test(l)).join("");
    let x = 0, y = 0, n = "";
    for (const ch of body) {
      if (ch >= "0" && ch <= "9") { n += ch; continue; }
      const k = n ? parseInt(n, 10) : 1; n = "";
      if (ch === "b") x += k;
      else if (ch === "$") { y += k; x = 0; }
      else if (ch === "!") break;
      else if (ch === "o") { for (let i = 0; i < k; i++, x++) words[y * NW + (x >> 5)] |= (1 << (x & 31)) >>> 0; }
    }
    return words;
  }
  const initial = pack(rleText);

  // ---- WebGL2 ----
  const glc = $("gl"), ov = $("ov");
  const gl = glc.getContext("webgl2", { antialias: false, preserveDrawingBuffer: false });
  if (!gl) { $("info").innerHTML = '<span class="err">This page needs WebGL2.</span>'; return; }

  const vs = `#version 300 es
  in vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }`;
  // One generation of B2/S0 on 32 cells at once; bit b of word i is cell 32*i+b.
  const stepFs = `#version 300 es
  precision highp float; precision highp int; precision highp usampler2D;
  uniform usampler2D s; out uint o;
  const int NW = ${NW}, H = ${H};
  uint at(int x, int y){ return texelFetch(s, ivec2((x + NW) % NW, (y + H) % H), 0).r; }
  void add(inout uint s0, inout uint s1, inout uint s2, uint n){ uint c0 = s0 & n; s0 ^= n; uint c1 = s1 & c0; s1 ^= c0; s2 |= c1; }
  void main(){
    int x = int(gl_FragCoord.x), y = int(gl_FragCoord.y);
    uint s0 = 0u, s1 = 0u, s2 = 0u, c = 0u;
    for (int dy = -1; dy <= 1; dy++) {
      uint l = at(x - 1, y + dy), m = at(x, y + dy), r = at(x + 1, y + dy);
      uint west = (m << 1) | (l >> 31), east = (m >> 1) | (r << 31);
      add(s0, s1, s2, west); add(s0, s1, s2, east);
      if (dy != 0) add(s0, s1, s2, m); else c = m;
    }
    uint any = s0 | s1 | s2, two = ~s0 & s1 & ~s2;
    o = (~c & two) | (c & ~any);
  }`;
  // Draw: each device pixel shows a cell if any live cell falls inside it, so zoomed-out views keep every dot.
  const drawFs = `#version 300 es
  precision highp float; precision highp int; precision highp usampler2D;
  uniform usampler2D s; uniform vec2 org; uniform float cpp, vh; uniform vec3 bg, fg, out_, line;
  out vec4 o;
  const int NW = ${NW}, W = ${W}, H = ${H}, CELL = ${CELL};
  void main(){
    float px = gl_FragCoord.x - 0.5, py = vh - gl_FragCoord.y - 0.5;
    vec2 a = org + vec2(px, py) * cpp, b = a + vec2(cpp);
    if (b.x <= 0.0 || b.y <= 0.0 || a.x >= float(W) || a.y >= float(H)) { o = vec4(out_, 1.0); return; }
    int x0 = max(int(floor(a.x)), 0), x1 = min(int(ceil(b.x)) - 1, W - 1);
    int y0 = max(int(floor(a.y)), 0), y1 = min(int(ceil(b.y)) - 1, H - 1);
    x1 = max(x1, x0); y1 = max(y1, y0);
    int ys = max(1, (y1 - y0 + 1) / 24);
    bool on = false;
    for (int y = y0; y <= y1 && !on; y += ys) {
      for (int w = x0 >> 5; w <= (x1 >> 5) && !on; w++) {
        uint v = texelFetch(s, ivec2(w, y), 0).r;
        int lo = max(x0 - w * 32, 0), hi = min(x1 - w * 32, 31);
        uint m = (hi - lo == 31) ? 0xffffffffu : (((1u << uint(hi - lo + 1)) - 1u) << uint(lo));
        on = (v & m) != 0u;
      }
    }
    bool edge = (x0 / CELL) != (x1 / CELL) || (x0 % CELL == 0 && cpp >= 1.0);
    o = vec4(on ? fg : (edge ? line : bg), 1.0);
  }`;
  function prog(fsrc) {
    const p = gl.createProgram();
    for (const [type, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fsrc]]) {
      const sh = gl.createShader(type); gl.shaderSource(sh, src); gl.compileShader(sh);
      if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh));
      gl.attachShader(p, sh);
    }
    gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    return p;
  }
  const stepP = prog(stepFs), drawP = prog(drawFs);
  const quad = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

  const tex = [], fbo = [];
  for (let i = 0; i < 2; i++) {
    const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texStorage2D(gl.TEXTURE_2D, 1, gl.R32UI, NW, H);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    const f = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, f);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
    tex.push(t); fbo.push(f);
  }
  let cur = 0, gen = 0;
  const sLocStep = gl.getUniformLocation(stepP, "s");
  const U = {}; for (const n of ["s", "org", "cpp", "vh", "bg", "fg", "out_", "line"]) U[n] = gl.getUniformLocation(drawP, n);

  function upload() {
    gl.bindTexture(gl.TEXTURE_2D, tex[0]);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, NW, H, gl.RED_INTEGER, gl.UNSIGNED_INT, initial);
    cur = 0; gen = 0;
  }
  function steps(n) {
    gl.useProgram(stepP); gl.viewport(0, 0, NW, H); gl.uniform1i(sLocStep, 0); gl.activeTexture(gl.TEXTURE0);
    for (let i = 0; i < n; i++) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, fbo[1 - cur]); gl.bindTexture(gl.TEXTURE_2D, tex[cur]);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); cur = 1 - cur;
    }
    gen += n;
  }
  const rowBuf = new Uint32Array(NW * 4);
  function readBits() {
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo[cur]);
    gl.readPixels(0, DOTY, NW, 1, gl.RGBA_INTEGER, gl.UNSIGNED_INT, rowBuf);
    let s = "";
    for (let j = 0; j < 6; j++) { const x = DOTX + CELL * j; s += (rowBuf[(x >> 5) * 4] >>> (x & 31)) & 1; }
    return s;
  }

  // ---- View ----
  const view = { cx: W / 2, cy: H / 2, cpp: 1 }; // centre in cells, cells per device pixel
  let dpr = 1, vw = 1, vh = 1;
  function resize() {
    dpr = window.devicePixelRatio || 1;
    const w = glc.parentElement.clientWidth, h = Math.max(360, Math.min(820, innerHeight - 120));
    for (const c of [glc, ov]) { c.style.width = w + "px"; c.style.height = h + "px"; c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
    vw = glc.width; vh = glc.height;
  }
  function fit() { view.cx = W / 2; view.cy = H / 2; view.cpp = Math.max(W / (vw - 16 * dpr), H / (vh - 70 * dpr)); view.cy = H / 2 - 12 * dpr * view.cpp; }
  const colors = {};
  function readColors() { colors.bg = rgb(css("--grid-bg")); colors.fg = rgb(css("--cell")); colors.out = rgb(css("--panel")); colors.line = rgb(css("--rule")); colors.muted = css("--muted"); colors.fgs = css("--fg"); colors.bgs = css("--grid-bg"); }

  let bits = "000100";
  function draw() {
    gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, vw, vh); gl.useProgram(drawP);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, tex[cur]); gl.uniform1i(U.s, 0);
    const ox = view.cx - (vw / 2) * view.cpp, oy = view.cy - (vh / 2) * view.cpp;
    gl.uniform2f(U.org, ox, oy); gl.uniform1f(U.cpp, view.cpp); gl.uniform1f(U.vh, vh);
    gl.uniform3fv(U.bg, colors.bg); gl.uniform3fv(U.fg, colors.fg); gl.uniform3fv(U.out_, colors.out); gl.uniform3fv(U.line, colors.line);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    // Overlay: circle each unit cell's state dot and label the column.
    const c = ov.getContext("2d"); c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, ov.width, ov.height);
    c.font = `${11 * dpr}px ui-monospace, Menlo, monospace`; c.textAlign = "center";
    for (let j = 0; j < 6; j++) {
      const sx = (DOTX + CELL * j + 0.5 - ox) / view.cpp, sy = (DOTY + 0.5 - oy) / view.cpp;
      const r = Math.max(7 * dpr, 3 / view.cpp);
      c.strokeStyle = colors.fgs; c.lineWidth = 1.5 * dpr; c.beginPath(); c.arc(sx, sy, r, 0, 2 * Math.PI); c.stroke();
      c.fillStyle = colors.muted; c.fillText(`cell ${j}`, sx, sy - r - 6 * dpr);
    }
    const phase = gen % PERIOD;
    $("info").textContent = `GEN ${gen} · RULE 110 GEN ${Math.floor(gen / PERIOD)} · PHASE ${String(phase).padStart(4, " ")}/${PERIOD}`;
  }

  // ---- History panel ----
  function addRow(t, s) {
    const row = document.createElement("div"); row.className = "row";
    row.innerHTML = `<span class="t">${t}</span>` + [...s].map((b) => `<span class="b${b === "1" ? " on" : ""}"></span>`).join("");
    row.title = `Rule 110 generation ${t}: ${s}`;
    $("hist").appendChild(row); $("hist").scrollTop = $("hist").scrollHeight;
  }
  function resetHist() { $("hist").innerHTML = ""; bits = readBits(); addRow(0, bits); }

  // ---- Run loop ----
  let playing = false, target = Infinity, perFrame = 4, last = 0;
  function frame(ts) {
    if (!playing) return;
    const sp = $("speed").value;
    if (sp === "max") {
      // Adapt the generations per frame to keep the page responsive.
      if (last) { const dt = ts - last; perFrame = dt > 22 ? Math.max(1, perFrame * 0.8) : Math.min(400, perFrame * 1.1 + 0.5); }
    } else perFrame = +sp;
    last = ts;
    let n = Math.max(1, Math.round(perFrame));
    while (n > 0) {
      // Never step past a multiple of 7200, so the dots can be read there.
      const toBoundary = PERIOD - (gen % PERIOD), k = Math.min(n, toBoundary, target - gen);
      steps(k); n -= k;
      if (gen % PERIOD === 0) { bits = readBits(); addRow(gen / PERIOD, bits); }
      if (gen >= target) { pause(); break; }
    }
    draw();
    if (playing) requestAnimationFrame(frame);
  }
  function play() { if (playing) return; playing = true; last = 0; $("play").textContent = "⏸"; requestAnimationFrame(frame); }
  function pause() { playing = false; target = Infinity; $("play").textContent = "▶"; }
  $("play").onclick = () => (playing ? pause() : play());
  $("step").onclick = () => { pause(); steps(1); if (gen % PERIOD === 0) { bits = readBits(); addRow(gen / PERIOD, bits); } draw(); };
  $("next").onclick = () => { pause(); target = (Math.floor(gen / PERIOD) + 1) * PERIOD; $("speed").value = "max"; play(); };
  $("reset").onclick = () => { pause(); upload(); resetHist(); draw(); };
  $("fit").onclick = () => { fit(); draw(); };

  // Zoom around the cursor; drag to pan.
  glc.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const r = glc.getBoundingClientRect(), mx = (ev.clientX - r.left) * dpr - vw / 2, my = (ev.clientY - r.top) * dpr - vh / 2;
    const wx = view.cx + mx * view.cpp, wy = view.cy + my * view.cpp;
    view.cpp = Math.min(48, Math.max(1 / 40, view.cpp * Math.exp(ev.deltaY * 0.002)));
    view.cx = wx - mx * view.cpp; view.cy = wy - my * view.cpp; draw();
  }, { passive: false });
  let drag = null;
  glc.addEventListener("pointerdown", (ev) => { drag = { x: ev.clientX, y: ev.clientY }; glc.setPointerCapture(ev.pointerId); glc.classList.add("dragging"); });
  glc.addEventListener("pointermove", (ev) => {
    if (!drag) return;
    view.cx -= (ev.clientX - drag.x) * dpr * view.cpp; view.cy -= (ev.clientY - drag.y) * dpr * view.cpp;
    drag.x = ev.clientX; drag.y = ev.clientY; draw();
  });
  glc.addEventListener("pointerup", () => { drag = null; glc.classList.remove("dragging"); });
  addEventListener("resize", () => { resize(); draw(); });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { readColors(); draw(); });

  readColors(); resize(); fit(); upload(); resetHist(); draw();
})().catch((e) => { document.getElementById("info").innerHTML = '<span class="err">' + e.message + "</span>"; console.error(e); });
