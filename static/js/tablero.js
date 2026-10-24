(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const num = (n, d = 0) => n.toLocaleString("es-PY", { minimumFractionDigits: d, maximumFractionDigits: d });
  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const etiquetaMes = (ym) => { const [y, m] = ym.split("-"); return `${MESES[m - 1]} ${y.slice(2)}`; };

  // Paleta categórica validada (orden fijo, sigue a la entidad)
  const SERIES = [
    { clave: "Reparado", color: "#008e9e" },
    { clave: "Reemplazo", color: "#c98400" },
    { clave: "Rechazado", color: "#5a4fa8" },
  ];

  const form = $("#filtros");
  const tip = $("#tip");
  let ultimo = null;

  // ------------------------------------------------------------ datos
  async function cargar() {
    const q = new URLSearchParams(new FormData(form));
    document.body.classList.add("cargando");
    const datos = await fetch(`/api/tablero?${q}`).then((r) => r.json());
    document.body.classList.remove("cargando");
    if (datos.vacio) { alert("No hay casos con esos filtros."); return; }
    ultimo = datos;
    pintar(datos);
  }
  form.addEventListener("change", cargar);
  form.addEventListener("reset", () => setTimeout(cargar));

  function pintar(d) {
    const k = d.kpis;
    contar($("#k-casos"), k.casos);
    $("#k-abiertos").textContent = `${num(k.abiertos)} todavía en proceso`;
    contar($("#k-mediana"), k.mediana_dias, { sufijo: " d" });
    $("#k-p90").textContent = `mediana de reparación · 90 % en ≤ ${num(k.p90_dias)} días`;
    contar($("#k-sla"), k.en_sla, { dec: 1, sufijo: " %" });
    $("#k-sla-sub").textContent = `objetivo: ≤ ${d.sla} días`;
    contar($("#k-rechazo"), k.rechazo, { dec: 1, sufijo: " %" });
    contar($("#k-costo"), k.costo / 1e6, { dec: 1, sufijo: " M" });

    graficoMes(d.por_mes);
    barras($("#g-herr"), d.herramientas.map((h) => ({ et: `<em>${esc(h.modelo)}</em>${esc(h.nombre)}`, v: h.casos, tip: `${h.modelo} · ${h.nombre}` })));
    barras($("#g-causas"), d.causas.map((c) => ({ et: `<em>${c.codigo}</em>${esc(c.titulo)}`, v: c.casos, no: !c.garantia, tip: `${c.titulo}${c.garantia ? "" : " · no cubre garantía"}` })));
    sucursales(d.sucursales, d.sla);
    matriz(d.matriz);
    hallazgos(d.hallazgos);
  }

  // ------------------------------------------------------------ tooltip
  function verTip(e, html) {
    tip.innerHTML = html;
    tip.classList.add("ver");
    tip.style.left = `${e.clientX}px`;
    tip.style.top = `${e.clientY}px`;
  }
  const ocultarTip = () => tip.classList.remove("ver");

  // ------------------------------------------------------------ columnas apiladas por mes
  function graficoMes({ meses, series }) {
    const cont = $("#g-mes");
    const W = cont.clientWidth, H = 280, m = { l: 38, r: 8, t: 12, b: 28 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const totales = meses.map((_, i) => SERIES.reduce((a, s) => a + (series[s.clave]?.[i] || 0), 0));
    const max = Math.max(...totales, 1);
    const crudo = max / 4, mag = Math.pow(10, Math.floor(Math.log10(crudo)));
    const paso = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((p) => p >= crudo);
    const tope = Math.ceil(max / paso) * paso;
    const y = (v) => m.t + ih - (v / tope) * ih;
    const banda = iw / meses.length;
    const ancho = Math.max(4, Math.min(28, banda * .62));
    const cadaN = Math.ceil(meses.length / (W < 600 ? 5 : 12));

    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Casos por mes según resultado"><g class="eje">`;
    for (let v = 0; v <= tope; v += paso) {
      svg += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${m.l - 8}" y="${y(v) + 3}" text-anchor="end">${num(v)}</text>`;
    }
    meses.forEach((ym, i) => {
      if (i % cadaN === 0) svg += `<text x="${m.l + banda * i + banda / 2}" y="${H - 8}" text-anchor="middle">${etiquetaMes(ym)}</text>`;
    });
    svg += `</g>`;

    meses.forEach((ym, i) => {
      const x = m.l + banda * i + (banda - ancho) / 2;
      let base = 0;
      svg += `<g class="col" data-i="${i}">`;
      SERIES.forEach((s, si) => {
        const v = series[s.clave]?.[i] || 0;
        if (!v) return;
        const y0 = y(base), y1 = y(base + v);
        const alto = Math.max(0, y0 - y1 - (base > 0 ? 2 : 0));      // 2px de separación entre segmentos
        svg += `<rect class="seg" x="${x}" y="${y1}" width="${ancho}" height="${alto}" fill="${s.color}" style="animation-delay:${i * 18 + si * 60}ms"/>`;
        base += v;
      });
      svg += `<rect x="${m.l + banda * i}" y="${m.t}" width="${banda}" height="${ih}" fill="transparent"/></g>`;
    });

    // promedio móvil de 3 meses
    const pm = totales.map((_, i) => i < 2 ? null : (totales[i] + totales[i - 1] + totales[i - 2]) / 3);
    const pts = pm.map((v, i) => v == null ? null : `${m.l + banda * i + banda / 2},${y(v)}`).filter(Boolean);
    svg += `<polyline class="tendencia" points="${pts.join(" ")}"/>`;
    svg += `</svg>`;
    cont.innerHTML = svg;

    const linea = cont.querySelector(".tendencia");
    const largo = linea.getTotalLength();
    linea.animate([{ strokeDashoffset: largo, strokeDasharray: `${largo} ${largo}` }, { strokeDashoffset: 0, strokeDasharray: `${largo} ${largo}` }],
      { duration: 1400, delay: 500, easing: "cubic-bezier(.2,.8,.15,1)", fill: "backwards" });

    cont.querySelectorAll(".col").forEach((g) => {
      const i = +g.dataset.i;
      g.addEventListener("pointermove", (e) => {
        cont.querySelectorAll(".col.foco").forEach((x) => x.classList.remove("foco"));
        g.classList.add("foco");
        verTip(e, `<b>${etiquetaMes(meses[i])}</b>` +
          SERIES.map((s) => `<div><span><i style="background:${s.color}"></i>${s.clave}</span><span>${series[s.clave]?.[i] || 0}</span></div>`).join("") +
          `<div style="border-top:1px solid #444;margin-top:4px;padding-top:4px"><span>Total</span><span>${totales[i]}</span></div>`);
      });
      g.addEventListener("pointerleave", () => { g.classList.remove("foco"); ocultarTip(); });
    });

    $("#ley-mes").innerHTML = SERIES.map((s) => `<span><i style="background:${s.color}"></i>${s.clave}</span>`).join("") +
      `<span><i style="background:none;border-top:2px dashed var(--tinta);height:0;width:14px;border-radius:0"></i>Prom. 3 meses</span>`;

    $("#t-mes").innerHTML = `<table><thead><tr><th>Mes</th>${SERIES.map((s) => `<th>${s.clave}</th>`).join("")}<th>En proceso</th><th>Total</th></tr></thead><tbody>` +
      meses.map((ym, i) => `<tr><td>${ym}</td>${SERIES.map((s) => `<td>${series[s.clave]?.[i] || 0}</td>`).join("")}<td>${series["En proceso"]?.[i] || 0}</td><td>${totales[i] + (series["En proceso"]?.[i] || 0)}</td></tr>`).join("") +
      `</tbody></table>`;
  }

  // ------------------------------------------------------------ barras horizontales (HTML, transicionan entre filtros)
  function barras(cont, filas) {
    const max = Math.max(...filas.map((f) => f.v), 1);
    const previas = new Map([...cont.children].map((el) => [el.dataset.k, el]));
    cont.innerHTML = filas.map((f) => `
      <div class="barra" data-k="${esc(f.et)}">
        <span class="et">${f.et}</span>
        <span class="riel"><span class="b ${f.no ? "no" : ""}" style="width:${previas.get(f.et)?.querySelector(".b").style.width || "0%"}"></span></span>
        <span class="val">${num(f.v)}</span>
      </div>`).join("");
    [...cont.children].forEach((el, i) => {
      const b = el.querySelector(".b");
      const f = filas[i];
      setTimeout(() => (b.style.width = `${(f.v / max) * 100}%`), 40 + i * 45);
      el.addEventListener("pointermove", (e) => verTip(e, `<b>${esc(f.tip)}</b><div><span>Casos</span><span>${num(f.v)}</span></div>`));
      el.addEventListener("pointerleave", ocultarTip);
    });
  }

  // ------------------------------------------------------------ mediana + p90 por sucursal
  function sucursales(filas, sla) {
    const cont = $("#g-suc");
    const max = Math.ceil((Math.max(sla, ...filas.map((f) => f.p90)) + 2) / 5) * 5;
    const pct = (v) => `${(v / max) * 100}%`;
    cont.innerHTML = filas.map((f) => `
      <div class="barra">
        <span class="et">${esc(f.sucursal)}</span>
        <span class="riel">
          <span class="sla" style="left:${pct(sla)}"></span>
          <span class="tramo"></span><span class="p90"></span><span class="punto"></span>
        </span>
        <span class="val">${num(f.mediana)} d</span>
      </div>`).join("") +
      `<div class="escala"><span></span><div>${Array.from({ length: max / 5 + 1 }, (_, k) => `<span>${k * 5}</span>`).join("")}</div><span>días</span></div>`;
    [...cont.querySelectorAll(".barra")].forEach((el, i) => {
      const f = filas[i];
      setTimeout(() => {
        el.querySelector(".tramo").style.width = pct(f.p90);
        el.querySelector(".p90").style.left = pct(f.p90);
        el.querySelector(".punto").style.left = pct(f.mediana);
      }, 60 + i * 70);
      el.addEventListener("pointermove", (e) => verTip(e, `<b>${esc(f.sucursal)}</b><div><span>Mediana</span><span>${num(f.mediana)} días</span></div><div><span>Percentil 90</span><span>${num(f.p90, 0)} días</span></div><div><span>Casos</span><span>${f.casos}</span></div>`));
      el.addEventListener("pointerleave", ocultarTip);
    });
  }

  // ------------------------------------------------------------ matriz (escala secuencial de un solo tono)
  function matriz({ filas, columnas, valores, nombres }) {
    const max = Math.max(...valores.flat(), 1);
    const color = (v) => {
      const t = Math.sqrt(v / max);
      const a = [232, 244, 245], b = [0, 142, 158], c = [0, 59, 66];
      const mix = (p, q, k) => p.map((x, j) => Math.round(x + (q[j] - x) * k));
      const rgb = t < .6 ? mix(a, b, t / .6) : mix(b, c, (t - .6) / .4);
      return { fondo: `rgb(${rgb})`, texto: t > .45 ? "#fff" : "#131516" };
    };
    $("#g-matriz").innerHTML = `<table><thead><tr><th></th>${columnas.map((c) => `<th title="${esc(nombres[c])}">${c}</th>`).join("")}</tr></thead><tbody>` +
      filas.map((f, i) => `<tr><th>${esc(f)}</th>${valores[i].map((v, j) => {
        const c = color(v);
        return `<td style="background:${c.fondo};color:${c.texto};animation-delay:${(i + j) * 28}ms" data-t="${esc(f)} · ${esc(nombres[columnas[j]])}" data-v="${v}">${v || ""}</td>`;
      }).join("")}</tr>`).join("") + `</tbody></table>`;
    $("#g-matriz").querySelectorAll("td").forEach((td) => {
      td.addEventListener("pointermove", (e) => verTip(e, `<b>${td.dataset.t}</b><div><span>Casos</span><span>${td.dataset.v}</span></div>`));
      td.addEventListener("pointerleave", ocultarTip);
    });
  }

  // ------------------------------------------------------------ hallazgos
  function hallazgos(notas) {
    $("#hallazgos").innerHTML = notas.map((n, i) => `
      <div class="hallazgo revela" style="transition-delay:${i * 90}ms">
        <span class="chapa">${esc(n.tag)}</span><b>${esc(n.dato)}</b><p>${esc(n.texto)}</p>
      </div>`).join("");
    requestAnimationFrame(() => document.querySelectorAll(".hallazgo").forEach((h) => h.classList.add("visto")));
  }

  // ------------------------------------------------------------ tablas accesibles
  document.querySelectorAll(".ver-tabla").forEach((b) => b.addEventListener("click", () => {
    const t = document.getElementById(b.dataset.tabla);
    t.hidden = !t.hidden;
    b.textContent = t.hidden ? "ver tabla" : "ocultar tabla";
  }));

  let espera;
  window.addEventListener("resize", () => { clearTimeout(espera); espera = setTimeout(() => ultimo && graficoMes(ultimo.por_mes), 200); });

  cargar();
})();
