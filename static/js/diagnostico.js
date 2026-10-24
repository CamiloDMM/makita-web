(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const espera = (ms) => new Promise((r) => setTimeout(r, ms));

  const estado = { herramienta: null, marcados: new Set(), sintomas: [] };

  // ------------------------------------------------------------ etapas
  function irA(n) {
    $$(".etapa").forEach((e, i) => {
      const ver = i + 1 === n;
      e.hidden = !ver;
      e.classList.remove("entra");
      if (ver) { void e.offsetWidth; e.classList.add("entra"); }
    });
    $$("#pasador div").forEach((d, i) => {
      d.classList.toggle("hecho", i + 1 < n);
      d.classList.toggle("actual", i + 1 === n);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ------------------------------------------------------------ 01 herramienta
  $$(".filtro-linea button").forEach((b) => b.addEventListener("click", () => {
    $$(".filtro-linea button").forEach((x) => x.classList.toggle("activo", x === b));
    $$(".herr").forEach((h, i) => {
      const ver = !b.dataset.linea || h.dataset.linea === b.dataset.linea;
      h.classList.toggle("oculta", !ver);
      if (ver) { h.style.animation = "none"; void h.offsetWidth; h.style.animation = `etapa-entra .5s var(--ease) ${i * 30}ms backwards`; }
    });
  }));

  $$(".herr").forEach((h) => {
    h.addEventListener("pointermove", (e) => {
      const r = h.getBoundingClientRect();
      h.style.setProperty("--x", `${e.clientX - r.left}px`);
      h.style.setProperty("--y", `${e.clientY - r.top}px`);
    });
    h.addEventListener("click", () => elegir(h.dataset.slug));
  });

  async function elegir(slug) {
    const datos = await fetch(`/api/herramientas/${slug}/sintomas`).then((r) => r.json());
    if (estado.herramienta?.slug !== slug) estado.marcados.clear();
    estado.herramienta = datos.herramienta;
    estado.sintomas = datos.sintomas;

    const h = datos.herramienta;
    $("#f-modelo").textContent = h.modelo;
    $("#f-linea").textContent = h.linea.toUpperCase();
    $("#f-nombre").textContent = h.nombre;
    $("#f-casos").textContent = `${h.casos.toLocaleString("es-PY")} casos de garantía en el historial`;

    const grupos = {};
    datos.sintomas.forEach((s) => (grupos[s.grupo] ??= []).push(s));
    $("#grupos").innerHTML = Object.entries(grupos).map(([g, lista]) => `
      <div class="grupo">
        <h4><span>${esc(g)}</span><span>${lista.length}</span></h4>
        ${lista.map((s) => `
          <button class="sintoma" data-cod="${s.codigo}" aria-pressed="${estado.marcados.has(s.codigo)}">
            <span class="casilla" aria-hidden="true"></span>
            <span class="txt">${esc(s.texto)}</span>
            <span class="cod">${s.codigo}</span>
          </button>`).join("")}
      </div>`).join("");

    $$(".sintoma").forEach((b) => b.addEventListener("click", () => {
      const cod = b.dataset.cod;
      estado.marcados.has(cod) ? estado.marcados.delete(cod) : estado.marcados.add(cod);
      b.setAttribute("aria-pressed", estado.marcados.has(cod));
      actualizarContador();
    }));
    actualizarContador(false);
    irA(2);
  }

  function actualizarContador(saltar = true) {
    const c = $("#contador");
    c.textContent = estado.marcados.size;
    if (saltar) { c.classList.remove("salta"); void c.offsetWidth; c.classList.add("salta"); }
    $("#diagnosticar").disabled = estado.marcados.size === 0;
  }

  $("#cambiar").addEventListener("click", () => irA(1));

  // ------------------------------------------------------------ 03 análisis + informe
  $("#diagnosticar").addEventListener("click", async () => {
    irA(3);
    const h = estado.herramienta;
    const analisis = $("#analisis");
    const bit = $("#bitacora");
    analisis.hidden = false;
    analisis.style.opacity = 1;
    $("#informe").innerHTML = "";
    bit.innerHTML = "";

    const rpm = $("#rpm");
    rpm.dataset.actual = 0;
    contar(rpm, 13300, { dur: 1600 });

    const peticion = fetch("/api/diagnostico", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ herramienta: h.slug, sintomas: [...estado.marcados], orden: window.ORDEN?.numero }),
    }).then((r) => r.json());

    const lineas = [
      `ficha ${h.modelo} · ${h.linea}`,
      `${estado.marcados.size} síntoma${estado.marcados.size > 1 ? "s" : ""} marcado${estado.marcados.size > 1 ? "s" : ""}`,
      `cruzando con ${window.TOTAL_REGLAS} reglas síntoma → causa`,
      `ponderando con ${h.casos.toLocaleString("es-PY")} casos del ${h.modelo}`,
      "ordenando causas probables",
    ];
    for (const [i, t] of lineas.entries()) {
      const li = document.createElement("li");
      li.textContent = t;
      bit.append(li);
      setTimeout(() => li.classList.add("ok"), 260);
      await espera(i === lineas.length - 1 ? 450 : 330);
    }
    const datos = await peticion;

    analisis.animate([{ opacity: 1 }, { opacity: 0, transform: "translateY(-12px)" }], { duration: 350, easing: "ease-in" });
    await espera(330);
    analisis.hidden = true;
    pintarInforme(datos);
  });

  const DIFICULTAD = {
    1: "Lo puede resolver el usuario",
    2: "Técnico de taller",
    3: "Servicio técnico oficial",
  };

  function pintarInforme({ causas, orden, orden_servicio }) {
    const h = estado.herramienta;
    const marcados = estado.sintomas.filter((s) => estado.marcados.has(s.codigo));
    const hoy = new Date().toLocaleDateString("es-PY", { day: "2-digit", month: "short", year: "numeric" });

    const cuerpo = causas.length ? causas.map((c, i) => `
      <article class="causa ${i === 0 ? "abierta" : ""}" style="animation-delay:${i * 110}ms">
        <button class="causa-cab" aria-expanded="${i === 0}">
          <span class="pos">${String(i + 1).padStart(2, "0")}</span>
          <span><span class="tit">${esc(c.titulo)}</span><span class="comp">${c.codigo} · ${esc(c.componente)}</span></span>
          <span class="medidor">
            <span class="fila"><span>probabilidad</span><b>${c.probabilidad}%</b></span>
            <span class="riel"><span class="relleno" data-p="${c.probabilidad}"></span></span>
          </span>
          <span class="giro" aria-hidden="true"><span>+</span></span>
        </button>
        <div class="causa-cuerpo"><div>
          <div class="causa-int">
            <div>
              <p>${esc(c.explicacion)}</p>
              <div class="datos-causa">
                <span class="chapa">${DIFICULTAD[c.dificultad]}</span>
                <span class="chapa ${c.cubre_garantia ? "si" : "no"}">${c.cubre_garantia ? "Cubre garantía" : "No cubre garantía"}</span>
              </div>
              <p class="explica">Explica: <b>${c.explica.map(esc).join("</b>, <b>")}</b>.<br>
                Visto en ${c.casos} casos de garantía de este modelo (${c.casos_pct.toLocaleString("es-PY")} %).</p>
            </div>
            <ol>${c.pasos.map((p) => `<li>${esc(p)}</li>`).join("")}</ol>
          </div>
        </div></div>
      </article>`).join("")
      : `<p style="padding:26px">Ninguna regla coincide con esa combinación. Probá marcando otros síntomas.</p>`;

    $("#informe").innerHTML = `
      <div class="informe">
        <div class="informe-cab">
          <div><span class="rotulo">Informe de diagnóstico</span><h3>${esc(h.modelo)} — ${esc(h.nombre)}</h3></div>
          <dl><dt>Orden</dt><dd>BP-${String(orden).padStart(6, "0")}</dd>
              <dt>Fecha</dt><dd>${hoy}</dd>
              <dt>Línea</dt><dd>${esc(h.linea)}</dd></dl>
        </div>
        <div class="marcados"><span class="mono">SÍNTOMAS ·</span>
          ${marcados.map((s) => `<span class="chapa">${esc(s.texto)}</span>`).join("")}</div>
        ${cuerpo}
      </div>
      <div class="informe-pie">
        ${orden_servicio ? `<p class="nota"><b>Guardado en la orden <a href="/recepcion/${orden_servicio}">${orden_servicio}</a></b> como causa más probable.</p>` : ""}
        <p class="nota">Orientativo: ordena las causas según reglas de taller y el historial simulado.
          Antes de abrir una herramienta, desenchufarla o quitarle la batería.</p>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <button class="boton claro" id="ajustar">Ajustar síntomas</button>
          <button class="boton" id="nuevo">Nuevo diagnóstico <span class="flecha">→</span></button>
        </div>
      </div>`;

    requestAnimationFrame(() => setTimeout(() => {
      $$(".relleno").forEach((r, i) => setTimeout(() => (r.style.transform = `scaleX(${r.dataset.p / 100})`), i * 110));
    }, 120));

    $$(".causa-cab").forEach((b) => b.addEventListener("click", () => {
      const art = b.closest(".causa");
      art.classList.toggle("abierta");
      b.setAttribute("aria-expanded", art.classList.contains("abierta"));
    }));
    $("#ajustar").addEventListener("click", () => irA(2));
    $("#nuevo").addEventListener("click", () => { estado.marcados.clear(); irA(1); });
  }

  // Si se llega desde una orden de recepción, se precarga el equipo y lo que contó el cliente.
  if (window.ORDEN) {
    (async () => {
      await elegir(window.ORDEN.slug);
      window.ORDEN.sintomas.forEach((c) => {
        const b = $(`.sintoma[data-cod="${c}"]`);
        if (!b) return;
        estado.marcados.add(c);
        b.setAttribute("aria-pressed", "true");
      });
      actualizarContador(false);
    })();
  }
})();
