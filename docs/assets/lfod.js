// Live Free or Die (B2/S0) pattern player.
// Any element <div class="pattern" data-rle="..."> becomes an animated canvas.
(function () {
  "use strict";

  const OFF = 1 << 20, SPAN = 1 << 21;
  const key = (x, y) => (x + OFF) * SPAN + (y + OFF);
  const kx = (k) => Math.floor(k / SPAN) - OFF;
  const ky = (k) => (k % SPAN) - OFF;

  function parseRLE(text) {
    const cells = [];
    let x = 0, y = 0, n = "";
    const body = text.split("\n").filter((l) => !/^\s*(#|x\s*=)/.test(l)).join("");
    for (const ch of body) {
      if (ch >= "0" && ch <= "9") { n += ch; continue; }
      const k = n ? parseInt(n, 10) : 1; n = "";
      if (ch === "b" || ch === ".") x += k;
      else if (ch === "$") { y += k; x = 0; }
      else if (ch === "!") break;
      else if (/[a-zA-Z]/.test(ch)) { for (let i = 0; i < k; i++) cells.push(key(x + i, y)); x += k; }
    }
    return new Set(cells);
  }

  // One generation of B2/S0: a live cell survives only with zero neighbours,
  // a dead cell is born with exactly two.
  function step(live) {
    const counts = new Map();
    for (const k of live) {
      const x = kx(k), y = ky(k);
      for (let dx = -1; dx <= 1; dx++)
        for (let dy = -1; dy <= 1; dy++)
          if (dx || dy) { const nk = key(x + dx, y + dy); counts.set(nk, (counts.get(nk) || 0) + 1); }
    }
    const next = new Set();
    for (const k of live) if (!counts.has(k)) next.add(k);
    for (const [k, c] of counts) if (c === 2 && !live.has(k)) next.add(k);
    return next;
  }

  function bounds(live) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const k of live) {
      const x = kx(k), y = ky(k);
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
    return live.size ? { x0, y0, x1, y1 } : { x0: 0, y0: 0, x1: 0, y1: 0 };
  }

  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  class Player {
    constructor(el) {
      this.el = el;
      this.rle = el.dataset.rle;
      this.start = parseRLE(this.rle);
      this.height = parseInt(el.dataset.height || "180", 10);
      this.speed = parseInt(el.dataset.speed || "8", 10);
      this.loop = parseInt(el.dataset.loop || "0", 10);
      // Small ships and puffers start further out, leaving room to move into.
      this.maxCell = el.dataset.moves === "true" ? 7 : 14;
      this.build();
      this.reset();
    }

    build() {
      const el = this.el;
      el.innerHTML = "";
      this.canvas = document.createElement("canvas");
      this.canvas.style.height = this.height + "px";
      this.canvas.setAttribute("role", "img");
      this.canvas.setAttribute("aria-label", el.dataset.label || "Live Free or Die pattern");
      el.appendChild(this.canvas);
      const bar = document.createElement("div");
      bar.className = "pbar";
      const btn = (label, title, fn) => {
        const b = document.createElement("button");
        b.type = "button"; b.textContent = label; b.title = title;
        b.addEventListener("click", fn); bar.appendChild(b); return b;
      };
      this.playBtn = btn("▶", "Play / pause", () => this.toggle());
      btn("⏭", "Step one generation", () => { this.pause(); this.tick(); });
      btn("⟲", "Reset", () => { this.reset(); });
      // The counter sits over the canvas so its changing width never moves the buttons.
      this.info = document.createElement("span");
      this.info.className = "pinfo";
      el.appendChild(this.info);
      const copy = btn("Copy RLE", "Copy RLE to clipboard", () => {
        navigator.clipboard && navigator.clipboard.writeText(this.rle).then(() => {
          copy.textContent = "Copied"; setTimeout(() => (copy.textContent = "Copy RLE"), 1200);
        });
      });
      copy.classList.add("pcopy");
      el.appendChild(bar);
      this.zoom = 1; this.panX = 0; this.panY = 0;
      if (el.dataset.interactive === "true") {
        // Wheel zooms around the cursor; drag pans. Clicking without dragging still toggles play.
        this.canvas.addEventListener("wheel", (ev) => {
          ev.preventDefault();
          const r = this.canvas.getBoundingClientRect();
          const mx = ev.clientX - r.left - r.width / 2 - this.panX, my = ev.clientY - r.top - r.height / 2 - this.panY;
          const f = Math.exp(-ev.deltaY * 0.002);
          this.zoom = Math.min(400, Math.max(0.2, this.zoom * f));
          this.panX -= mx * (f - 1); this.panY -= my * (f - 1);
          this.draw();
        }, { passive: false });
        let drag = null;
        this.canvas.addEventListener("pointerdown", (ev) => { drag = { x: ev.clientX, y: ev.clientY, moved: false }; this.canvas.setPointerCapture(ev.pointerId); });
        this.canvas.addEventListener("pointermove", (ev) => {
          if (!drag) return;
          const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
          if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
          if (drag.moved) { this.panX += dx; this.panY += dy; drag.x = ev.clientX; drag.y = ev.clientY; this.draw(); }
        });
        this.canvas.addEventListener("pointerup", () => { if (drag && !drag.moved) this.toggle(); drag = null; });
      } else {
        this.canvas.addEventListener("click", () => this.toggle());
      }
    }

    reset() {
      this.live = new Set(this.start);
      this.gen = 0;
      const b = bounds(this.live);
      this.view = { x0: b.x0, y0: b.y0, x1: b.x1, y1: b.y1 };
      this.draw();
    }

    tick() {
      if (this.loop && this.gen >= this.loop) { this.reset(); return; }
      this.live = step(this.live);
      this.gen++;
      // Grow the view (never shrink) so moving objects stay in frame.
      const b = bounds(this.live), v = this.view;
      v.x0 = Math.min(v.x0, b.x0); v.y0 = Math.min(v.y0, b.y0);
      v.x1 = Math.max(v.x1, b.x1); v.y1 = Math.max(v.y1, b.y1);
      this.draw();
      if (this.live.size > 60000) this.pause();
    }

    toggle() { this.timer ? this.pause() : this.play(); }
    play() {
      if (this.timer) return;
      this.playBtn.textContent = "⏸";
      const loop = () => { this.tick(); this.timer = setTimeout(() => requestAnimationFrame(loop), 1000 / this.speed); };
      this.timer = setTimeout(loop, 0);
    }
    pause() {
      clearTimeout(this.timer); this.timer = null;
      this.playBtn.textContent = "▶";
    }

    draw() {
      const c = this.canvas, dpr = window.devicePixelRatio || 1;
      const W = c.clientWidth || 300, H = this.height;
      if (c.width !== Math.round(W * dpr) || c.height !== Math.round(H * dpr)) {
        c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
      }
      const ctx = c.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = css("--grid-bg"); ctx.fillRect(0, 0, W, H);
      // Keep the band under the GEN · POP label clear when fitting the pattern.
      const v = this.view, pad = 2, top = 18;
      const cw = v.x1 - v.x0 + 1 + pad * 2, ch = v.y1 - v.y0 + 1 + pad * 2;
      const s0 = Math.min(this.maxCell, (W - 8) / cw, (H - 8 - top) / ch);
      const s = Math.max(0.05, s0 * this.zoom);
      const ox = (W - cw * s) / 2 + pad * s - v.x0 * s + this.panX;
      const oy = top + (H - top - ch * s) / 2 + pad * s - v.y0 * s + this.panY;
      ctx.fillStyle = css("--cell");
      // Draw in device pixels, snapping cell edges so neighbours meet without gaps or seams.
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      const edge = (o, i) => Math.round((o + i * s) * dpr);
      for (const k of this.live) {
        const x = kx(k), y = ky(k);
        const px = edge(ox, x), py = edge(oy, y);
        const w = Math.max(edge(ox, x + 1) - px, 1), h = Math.max(edge(oy, y + 1) - py, 1);
        if (px > -w && py > -h && px < c.width && py < c.height) ctx.fillRect(px, py, w, h);
      }
      this.info.textContent = `GEN ${this.gen} · POP ${this.live.size}`;
    }
  }

  window.LFoD = { parseRLE, step, Player };

  function init() {
    const players = [];
    const io = "IntersectionObserver" in window ? new IntersectionObserver((ents) => {
      for (const e of ents) {
        const p = e.target._player;
        if (!p) continue;
        if (e.isIntersecting && e.target.dataset.autoplay !== "false") p.play();
        else p.pause();
      }
    }, { rootMargin: "50px" }) : null;
    document.querySelectorAll(".pattern[data-rle]").forEach((el) => {
      const p = new Player(el);
      el._player = p; players.push(p);
      if (io) io.observe(el);
    });
    window.addEventListener("resize", () => players.forEach((p) => p.draw()));
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => players.forEach((p) => p.draw()));
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", init) : init();
})();
