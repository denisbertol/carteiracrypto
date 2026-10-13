(() => {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const PALETTE = ["#f7931a", "#fde68a", "#ff8a3d", "#c4b5fd", "#f9a8d4", "#fdba74", "#5eead4", "#fca5a5", "#a5b4fc", "#ffc46b"];

  const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });
  const compactMoney = new Intl.NumberFormat("pt-BR", {
    style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1,
  });

  function svg(tag, attributes = {}) {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, String(value)));
    return node;
  }

  function html(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function niceStep(raw) {
    const exponent = Math.floor(Math.log10(raw));
    const fraction = raw / 10 ** exponent;
    const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
    return nice * 10 ** exponent;
  }

  function niceTicks(min, max, count) {
    if (max === min) max = min + 1;
    const step = niceStep((max - min) / Math.max(1, count - 1));
    const bottom = Math.floor(min / step) * step;
    const top = Math.ceil(max / step) * step;
    const ticks = [];
    for (let value = bottom; value <= top + step / 2; value += step) ticks.push(Math.round(value / step) * step);
    return ticks;
  }

  function tooltipLines(item) {
    const lines = [[item.tooltipLabel, ""]];
    if (item.value === null) {
      lines.push(["Valor aplicado", money.format(item.invested)], ["Patrimônio", "cotação indisponível"]);
    } else {
      lines.push(
        ["Patrimônio", money.format(item.value)],
        ["Valor aplicado", money.format(item.invested)],
        ["Ganho de capital", money.format(item.gain)],
      );
    }
    return lines;
  }

  /**
   * Stacked bars: invested amount from zero, capital gain above it, losses below zero.
   * Series items: { label, tooltipLabel, invested, value|null, gain|null }.
   */
  function renderEvolution(host, series) {
    host.replaceChildren();
    if (!series.length) return;
    const width = Math.max(260, Math.floor(host.clientWidth || 640));
    const compact = width < 520;
    const height = compact ? 220 : 280;
    const pad = { top: 12, right: 8, bottom: 28, left: compact ? 52 : 70 };
    const plotWidth = width - pad.left - pad.right;
    const plotHeight = height - pad.top - pad.bottom;

    const highs = series.map((item) => Math.max(item.invested, 0) + Math.max(item.gain || 0, 0));
    const lows = series.map((item) => Math.min(item.invested, 0, item.gain || 0));
    const ticks = niceTicks(Math.min(0, ...lows), Math.max(0, ...highs), compact ? 4 : 6);
    const top = ticks[ticks.length - 1];
    const bottom = ticks[0];
    const y = (value) => pad.top + ((top - value) / (top - bottom)) * plotHeight;

    const chart = svg("svg", {
      class: "evolution-chart", width, height, viewBox: `0 0 ${width} ${height}`,
      role: "img", "aria-label": "Evolução do patrimônio: valor aplicado e ganho de capital",
    });
    ticks.forEach((tick) => {
      chart.append(svg("line", { class: tick === 0 ? "axis-zero" : "grid-line", x1: pad.left, x2: width - pad.right, y1: y(tick), y2: y(tick) }));
      const label = svg("text", { class: "axis-label", x: pad.left - 8, y: y(tick) + 4, "text-anchor": "end" });
      label.textContent = compactMoney.format(tick);
      chart.append(label);
    });

    const band = plotWidth / series.length;
    const barWidth = Math.max(1, Math.min(44, band * 0.72));
    const highlight = svg("rect", { class: "bar-highlight", y: pad.top, height: plotHeight, width: band, x: pad.left, opacity: 0 });
    chart.append(highlight);

    series.forEach((item, index) => {
      const x = pad.left + index * band + (band - barWidth) / 2;
      const investedTop = y(Math.max(item.invested, 0));
      const investedBottom = y(Math.min(item.invested, 0));
      chart.append(svg("rect", {
        class: item.value === null ? "bar-invested bar-unknown" : "bar-invested",
        x, width: barWidth, y: investedTop, height: Math.max(0, investedBottom - investedTop),
      }));
      if (item.gain > 0) {
        chart.append(svg("rect", {
          class: "bar-gain", x, width: barWidth,
          y: y(Math.max(item.invested, 0) + item.gain), height: Math.max(0, investedTop - y(Math.max(item.invested, 0) + item.gain)),
        }));
      } else if (item.gain < 0) {
        chart.append(svg("rect", {
          class: "bar-loss", x, width: barWidth, y: y(0), height: Math.max(0, y(item.gain) - y(0)),
        }));
      }
    });

    const maxLabels = Math.max(2, Math.floor(plotWidth / (compact ? 52 : 64)));
    const step = Math.ceil(series.length / maxLabels);
    series.forEach((item, index) => {
      if (index % step !== 0 && index !== series.length - 1) return;
      if (index !== series.length - 1 && series.length - 1 - index < step / 2) return;
      const label = svg("text", {
        class: "axis-label", x: pad.left + index * band + band / 2, y: height - 8, "text-anchor": "middle",
      });
      label.textContent = item.label;
      chart.append(label);
    });

    const tooltip = html("div", "chart-tooltip");
    tooltip.hidden = true;
    const overlay = svg("rect", { class: "chart-overlay", x: pad.left, y: pad.top, width: plotWidth, height: plotHeight });
    const show = (event) => {
      const bounds = chart.getBoundingClientRect();
      const index = Math.min(series.length - 1, Math.max(0, Math.floor((event.clientX - bounds.left - pad.left) / band)));
      const item = series[index];
      highlight.setAttribute("x", String(pad.left + index * band));
      highlight.setAttribute("opacity", "1");
      tooltip.replaceChildren(...tooltipLines(item).map(([label, value], line) => {
        const row = html("div", line === 0 ? "tooltip-title" : "tooltip-row");
        row.append(html("span", "", label));
        if (value) row.append(html("strong", "", value));
        return row;
      }));
      tooltip.hidden = false;
      const left = pad.left + index * band + band / 2;
      tooltip.style.left = `${Math.min(Math.max(left, 90), width - 90)}px`;
    };
    overlay.addEventListener("pointermove", show);
    overlay.addEventListener("pointerdown", show);
    overlay.addEventListener("pointerleave", () => {
      tooltip.hidden = true;
      highlight.setAttribute("opacity", "0");
    });
    chart.append(overlay);
    host.append(chart, tooltip);
  }

  function percentLabel(value) {
    return `${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
  }

  /** Donut of current values. Slices: { label, value, recommended }. */
  function renderDonut(host, slices, centerText) {
    host.replaceChildren();
    const total = slices.reduce((sum, slice) => sum + slice.value, 0);
    if (!(total > 0)) return;
    const size = 200;
    const radius = 74;
    const circumference = 2 * Math.PI * radius;
    const chart = svg("svg", {
      class: "donut-chart", viewBox: `0 0 ${size} ${size}`, role: "img",
      "aria-label": "Distribuição atual da carteira por ativo, comparada à alocação recomendada",
    });
    const stroke = 34;
    const ring = svg("g", { transform: `rotate(-90 ${size / 2} ${size / 2})` });
    const frame = html("div", "donut-frame");
    const legend = html("ul", "donut-legend");
    const head = html("li", "legend-head");
    head.append(html("span"), html("span"), html("span", "legend-col", "Real"), html("span", "legend-col", "Recomendada"));
    legend.append(head);
    const entries = [];
    let offset = 0;
    slices.forEach((slice, index) => {
      const color = PALETTE[index % PALETTE.length];
      const share = slice.value / total;
      const real = percentLabel(share * 100);
      const recommended = slice.recommended === null || slice.recommended === undefined ? "—" : percentLabel(slice.recommended);
      const arc = svg("circle", {
        class: "donut-slice", cx: size / 2, cy: size / 2, r: radius, fill: "none", stroke: color,
        "stroke-width": stroke, "stroke-dasharray": `${share * circumference} ${circumference}`,
        "stroke-dashoffset": -offset * circumference,
      });
      ring.append(arc);
      const item = html("li", "legend-item");
      const swatch = html("span", "legend-swatch");
      swatch.style.background = color;
      item.append(
        swatch,
        html("span", "legend-label", slice.label),
        html("span", "legend-share", real),
        html("span", "legend-target", recommended),
      );
      legend.append(item);
      entries.push({ slice, share, start: offset, real, recommended, arc, item });
      offset += share;
    });

    const tooltip = html("div", "chart-tooltip donut-tooltip");
    tooltip.hidden = true;
    const focusEntry = (entry) => {
      chart.classList.toggle("has-focus", Boolean(entry));
      entries.forEach((candidate) => {
        const on = candidate === entry;
        candidate.arc.classList.toggle("is-focused", on);
        candidate.item.classList.toggle("is-focused", on);
      });
    };
    const hideTip = () => {
      tooltip.hidden = true;
      focusEntry(null);
    };
    const showTip = (entry, event) => {
      focusEntry(entry);
      const title = html("div", "tooltip-title");
      title.textContent = entry.slice.label;
      const value = html("div", "tooltip-row");
      value.append(html("span", "", "Valor"), html("strong", "", money.format(entry.slice.value)));
      tooltip.replaceChildren(title, value);
      tooltip.hidden = false;
      const bounds = frame.getBoundingClientRect();
      const tipWidth = tooltip.offsetWidth;
      const tipHeight = tooltip.offsetHeight;
      const left = Math.min(
        Math.max(event.clientX - bounds.left, tipWidth / 2 + 4),
        Math.max(tipWidth / 2 + 4, bounds.width - tipWidth / 2 - 4),
      );
      const top = Math.min(Math.max(event.clientY - bounds.top, tipHeight + 10), bounds.height - 4);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    };
    const entryAt = (event) => {
      const bounds = chart.getBoundingClientRect();
      const dx = event.clientX - (bounds.left + bounds.width / 2);
      const dy = event.clientY - (bounds.top + bounds.height / 2);
      const distance = Math.hypot(dx, dy) / (bounds.width / 2);
      const inner = (radius - stroke / 2) / (size / 2);
      const outer = (radius + stroke / 2) / (size / 2);
      if (distance < inner || distance > outer + 0.05) return null;
      let angle = Math.atan2(dy, dx) + Math.PI / 2;
      if (angle < 0) angle += Math.PI * 2;
      const fraction = angle / (Math.PI * 2);
      return entries.find((entry) => fraction <= entry.start + entry.share + 1e-6) || entries[entries.length - 1];
    };
    chart.addEventListener("pointermove", (event) => {
      const entry = entryAt(event);
      if (entry) showTip(entry, event);
      else hideTip();
    });
    chart.addEventListener("pointerleave", hideTip);
    entries.forEach((entry) => {
      entry.item.addEventListener("pointerenter", () => focusEntry(entry));
      entry.item.addEventListener("pointerleave", () => focusEntry(null));
    });

    chart.append(ring);
    if (centerText) {
      const label = svg("text", { class: "donut-center", x: size / 2, y: size / 2 + 5, "text-anchor": "middle" });
      label.textContent = centerText;
      chart.append(label);
    }
    frame.append(chart, tooltip);
    host.append(frame, legend);
  }

  window.Charts = Object.freeze({ renderEvolution, renderDonut });
})();
