// The race on the Speeds page: one lane per ship, noses on one column at generation 0, every lane
// stepped together with the shared B2/S0 engine in lfod.js, the side beyond the light front shaded.
// Cells are whole device pixels. Each lane is its own unbounded plane; the run restarts when the
// moon's nose is one column short of the right edge. After the race, a diagonal ship on a fixed
// square plane, the side beyond the diagonal speed limit (x + y gains at most one a generation) shaded.
(function () {
  "use strict";
  const RATE = 12, HOLD = 1600;
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");

  function init() { race(); diagonal(); }

  // A clock that runs while it is on screen and wanted, holding a moment before each restart.
  function clock(el, tick, wanted, onState) {
    const c = { timer: null, wanted, visible: false };
    const run = () => { const wait = tick(); c.timer = setTimeout(() => requestAnimationFrame(run), wait); };
    c.sync = () => {
      const on = c.wanted && c.visible;
      if (on && !c.timer) c.timer = setTimeout(run, 0);
      if (!on && c.timer) { clearTimeout(c.timer); c.timer = null; }
      if (onState) onState(c.wanted);
    };
    c.toggle = () => { c.wanted = !c.wanted; c.sync(); };
    if ("IntersectionObserver" in window) {
      new IntersectionObserver((ents) => { c.visible = ents[0].isIntersecting; c.sync(); }, { rootMargin: "50px" }).observe(el);
    } else c.visible = true;
    return c;
  }

  function diagonal() {
    const el = document.querySelector(".diag");
    if (!el || !window.LFoD) return;
    const { parseRLE, step, kx, ky } = window.LFoD;
    const [x0, y0, x1, y1] = el.dataset.ext.split(",").map(Number);
    const s0 = +el.dataset.s0, lap = +el.dataset.lap, travel = +el.dataset.travel;
    const canvas = el.querySelector("canvas"), info = el.querySelector(".pinfo");
    canvas.setAttribute("aria-label", `${el.dataset.label}, behind the diagonal speed limit, simulated exactly.`);
    const start = parseRLE(el.dataset.rle);
    // the square plane: the first period's box 2 cells in from the top left, room to travel, 2 cells to spare
    const N = Math.max(x1 - x0, y1 - y0) + 1 + travel + 4, tx = x0 - 2, ty = y0 - 2;
    const d = { live: start, gen: 0 };
    const to = (g) => { d.live = start; for (let i = 0; i < g; i++) d.live = step(d.live); d.gen = g; };
    function draw() {
      const dpr = window.devicePixelRatio || 1, side = Math.round((el.clientWidth || 300) * dpr);
      const cs = Math.max(1, Math.floor(side / N)), W = N * cs;
      if (canvas.width !== W) { canvas.width = W; canvas.height = W; }
      canvas.style.width = canvas.style.height = `${W / dpr}px`;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = css("--grid-bg"); ctx.fillRect(0, 0, W, W);
      const k = s0 + d.gen; // nothing can be alive where x + y > k
      ctx.fillStyle = css("--panel");
      for (let y = ty; y < ty + N; y++) {
        const X = (Math.max(k - y + 1, tx) - tx) * cs;
        if (X < W) ctx.fillRect(X, (y - ty) * cs, W - X, cs);
      }
      ctx.fillStyle = css("--cell");
      for (const c of d.live) ctx.fillRect((kx(c) - tx) * cs, (ky(c) - ty) * cs, cs, cs);
      info.textContent = `GEN ${d.gen}`;
    }
    const c = clock(el, () => {
      if (d.gen >= lap) { to(0); draw(); return HOLD; }
      d.live = step(d.live); d.gen++; draw(); return 1000 / RATE;
    }, !reduced.matches);
    if (reduced.matches) to(lap);
    canvas.addEventListener("click", c.toggle);
    window.addEventListener("resize", draw);
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
    draw(); c.sync();
  }

  function race() {
    const el = document.querySelector(".race");
    if (!el || !window.LFoD) return;
    const { parseRLE, step, kx, ky } = window.LFoD;
    const lanes = [...el.querySelectorAll(".lane")].map((l) => {
      const [x0, y0, x1, y1] = l.dataset.ext.split(",").map(Number);
      const canvas = l.querySelector("canvas");
      canvas.setAttribute("aria-label", `${l.dataset.label}, racing from the starting line, simulated exactly.`);
      const start = parseRLE(l.dataset.rle);
      return { canvas, start, live: start, f0: +l.dataset.f0, ext: { x0, y0, x1, y1 } };
    });
    const genEl = el.querySelector(".race-gen"), playBtn = el.querySelector(".race-play");
    // columns behind the start line that hold every ship's tail at generation 0
    const TAILS = Math.max(...lanes.map((l) => l.f0 - l.ext.x0)) + 2;
    const r = { gen: 0, cs: 2, mx: 0, behind: TAILS, lap: 1, timer: null, wanted: !reduced.matches, visible: false };

    function to(g) {
      for (const l of lanes) { l.live = l.start; for (let i = 0; i < g; i++) l.live = step(l.live); }
      r.gen = g;
    }
    function layout() {
      const dpr = window.devicePixelRatio || 1, cw = lanes[0].canvas.clientWidth || 300, W = Math.round(cw * dpr);
      // On narrow screens the longest tails start cropped by the left edge, so cells stay readable.
      const narrow = cw < 640;
      r.behind = narrow ? Math.min(TAILS, 40) : TAILS;
      r.cs = Math.max(2, Math.floor(W / (r.behind + (narrow ? 110 : 240))));
      const cols = Math.floor(W / r.cs);
      r.mx = Math.floor((W - cols * r.cs) / 2);
      r.lap = cols - r.behind - 2;
      for (const l of lanes) {
        const H = (l.ext.y1 - l.ext.y0 + 3) * r.cs;
        l.canvas.width = W; l.canvas.height = H;
        l.canvas.style.height = `${H / dpr}px`;
      }
      if (r.gen > r.lap) to(0);
      if (!r.timer && reduced.matches && !r.wanted) to(r.lap);
      draw();
    }
    function draw() {
      const { cs, mx } = r, bg = css("--grid-bg"), shade = css("--panel"), ink = css("--cell");
      for (const l of lanes) {
        const c = l.canvas, ctx = c.getContext("2d"), W = c.width, H = c.height;
        const ox = mx + (r.behind - l.f0) * cs, oy = cs - l.ext.y0 * cs;
        ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
        const X = ox + (l.f0 + r.gen + 1) * cs; // the light front: no cell can be alive at or beyond it
        ctx.fillStyle = shade; ctx.fillRect(X, 0, W - X, H);
        ctx.fillStyle = ink;
        for (const k of l.live) {
          const px = ox + kx(k) * cs, py = oy + ky(k) * cs;
          if (px > -cs && px < W) ctx.fillRect(px, py, cs, cs);
        }
      }
      genEl.textContent = `GEN ${r.gen}`;
    }
    function tick() {
      let wait = 1000 / RATE;
      if (r.gen >= r.lap) { to(0); wait = HOLD; }
      else { for (const l of lanes) l.live = step(l.live); r.gen++; }
      draw();
      r.timer = setTimeout(() => requestAnimationFrame(tick), wait);
    }
    function sync() {
      const on = r.wanted && r.visible;
      if (on && !r.timer) r.timer = setTimeout(tick, 0);
      if (!on && r.timer) { clearTimeout(r.timer); r.timer = null; }
      playBtn.textContent = r.wanted ? "⏸" : "▶";
    }
    const toggle = () => { r.wanted = !r.wanted; sync(); };
    playBtn.addEventListener("click", toggle);
    el.querySelector(".race-reset").addEventListener("click", () => { to(0); draw(); });
    for (const l of lanes) l.canvas.addEventListener("click", toggle);
    if ("IntersectionObserver" in window) {
      new IntersectionObserver((ents) => { r.visible = ents[0].isIntersecting; sync(); }, { rootMargin: "50px" }).observe(el);
    } else r.visible = true;
    window.addEventListener("resize", layout);
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
    layout(); sync();
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", init) : init();
})();
