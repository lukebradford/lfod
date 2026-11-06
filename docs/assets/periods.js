// The table at the bottom of the Periods page: the smallest known oscillator at each period under 20,
// two rows of cells, each oscillator in its own fixed frame, all stepped together with the shared B2/S0
// engine in lfod.js. Cells are whole device pixels, the same size in every frame. The run is one cycle of them all, after which every
// oscillator is back at its first generation, so the counter starts over.
(function () {
  "use strict";
  const RATE = 10, MIN_COLS = 10, MARGIN = 1;
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");

  function init() {
    const el = document.querySelector(".oscs");
    if (!el || !window.LFoD) return;
    const { parseRLE, step, kx, ky } = window.LFoD;
    const tiles = [...el.querySelectorAll(".osc")].map((t) => {
      const [x0, y0, x1, y1] = t.dataset.ext.split(",").map(Number);
      const canvas = t.querySelector("canvas");
      canvas.setAttribute("aria-label", `${t.dataset.label}, simulated exactly.`);
      const start = parseRLE(t.dataset.rle);
      const w = x1 - x0 + 1, h = y1 - y0 + 1;
      return { canvas, start, live: start, x0, y0, w, h, cols: Math.max(w + 2 * MARGIN, MIN_COLS) };
    });
    const lap = +el.dataset.lap, genEl = el.querySelector(".osc-gen"), playBtn = el.querySelector(".osc-play");
    const ROWS = Math.max(...tiles.map((t) => t.h)) + 2 * MARGIN, COLS = tiles.reduce((n, t) => n + t.cols, 0);
    const r = { gen: 0, cs: 4, timer: null, wanted: !reduced.matches, visible: false };

    function to(g) {
      for (const t of tiles) { t.live = t.start; for (let i = 0; i < g; i++) t.live = step(t.live); }
      r.gen = g;
    }
    function layout() {
      // Equal columns; cells as large as lets the widest frame fit one, up to 12 device pixels. Cells stay
      // at least 2.5 CSS pixels, so on narrow screens the table grows wider than the page and scrolls.
      const dpr = window.devicePixelRatio || 1, table = el.querySelector("table"), box = el.querySelector(".osc");
      const c = getComputedStyle(box), pad = parseFloat(c.paddingLeft) + parseFloat(c.paddingRight) + 1;
      const widest = Math.max(...tiles.map((t) => t.cols)), least = Math.max(2, Math.round(2.5 * dpr));
      table.style.minWidth = `${+el.dataset.cols * (widest * least / dpr + pad)}px`;
      r.cs = Math.max(least, Math.min(12, Math.floor((table.clientWidth / +el.dataset.cols - pad) * dpr / widest)));
      for (const t of tiles) {
        t.canvas.width = t.cols * r.cs; t.canvas.height = ROWS * r.cs;
        t.canvas.style.width = `${t.canvas.width / dpr}px`; t.canvas.style.height = `${t.canvas.height / dpr}px`;
      }
      draw();
    }
    function draw() {
      const cs = r.cs, bg = css("--grid-bg"), ink = css("--cell");
      for (const t of tiles) {
        const c = t.canvas, ctx = c.getContext("2d");
        ctx.fillStyle = bg; ctx.fillRect(0, 0, c.width, c.height);
        // the frame's box centred in the tile
        const ox = (Math.floor((t.cols - t.w) / 2) - t.x0) * cs, oy = (Math.floor((ROWS - t.h) / 2) - t.y0) * cs;
        ctx.fillStyle = ink;
        for (const k of t.live) ctx.fillRect(ox + kx(k) * cs, oy + ky(k) * cs, cs, cs);
      }
      genEl.textContent = `GEN ${r.gen}`;
    }
    function tick() {
      if (r.gen + 1 >= lap) to(0);
      else { for (const t of tiles) t.live = step(t.live); r.gen++; }
      draw();
      r.timer = setTimeout(() => requestAnimationFrame(tick), 1000 / RATE);
    }
    function sync() {
      const on = r.wanted && r.visible;
      if (on && !r.timer) r.timer = setTimeout(tick, 0);
      if (!on && r.timer) { clearTimeout(r.timer); r.timer = null; }
      playBtn.textContent = r.wanted ? "⏸" : "▶";
    }
    const toggle = () => { r.wanted = !r.wanted; sync(); };
    playBtn.addEventListener("click", toggle);
    el.querySelector(".osc-reset").addEventListener("click", () => { to(0); draw(); });
    for (const t of tiles) t.canvas.addEventListener("click", toggle);
    if ("IntersectionObserver" in window) {
      new IntersectionObserver((ents) => { r.visible = ents[0].isIntersecting; sync(); }, { rootMargin: "50px" }).observe(el);
    } else r.visible = true;
    window.addEventListener("resize", layout);
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
    layout(); sync();
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", init) : init();
})();
