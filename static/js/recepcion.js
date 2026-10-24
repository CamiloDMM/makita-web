(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const form = $("#planilla");
  const sintomasMarcados = new Set();

  $("#st-fecha").textContent = new Date().toLocaleDateString("es-PY");

  // ------------------------------------------------------------ sticker en vivo
  function pulso(el) { el.classList.remove("late"); void el.offsetWidth; el.classList.add("late"); }
  function actualizarSticker() {
    const h = $("input[name=herramienta]:checked");
    const set = (id, v) => { const el = $(id); if (el.textContent !== v) { el.textContent = v; pulso(el); } };
    set("#st-modelo", h ? h.dataset.modelo : "MODELO");
    set("#st-serie", form.serie.value.trim().toUpperCase() || "—");
    set("#st-cliente", form.nombre.value.trim() || "—");
    set("#st-cel", form.celular.value.trim() || "—");
    const acc = $$("input[name=accesorios]:checked").map((a) => a.value);
    if (form.acc_otros.value.trim()) acc.push(form.acc_otros.value.trim());
    $("#st-acc").textContent = acc.length ? `+ ${acc.join(" · ")}` : "";
  }
  form.addEventListener("input", actualizarSticker);
  form.addEventListener("change", actualizarSticker);

  // ------------------------------------------------------------ documento
  $$("input[name=tipo_doc]").forEach((r) => r.addEventListener("change", () => {
    const ruc = form.tipo_doc.value === "RUC";
    $("#et-doc").textContent = ruc ? "RUC (con dígito verificador)" : "Número de cédula";
    form.documento.placeholder = ruc ? "80012345-6" : "4567890";
    form.documento.inputMode = ruc ? "text" : "numeric";
  }));

  let docBuscado = "";
  form.documento.addEventListener("blur", async () => {
    const doc = form.documento.value.trim();
    if (doc.length < 5 || doc === docBuscado) return;
    docBuscado = doc;
    const r = await fetch(`/api/clientes/${encodeURIComponent(doc)}`);
    const caja = $("#equipos-cliente");
    if (!r.ok) {
      $("#ayuda-doc").textContent = "Cliente nuevo: se registra al guardar.";
      caja.hidden = true;
      return;
    }
    const c = await r.json();
    form.nombre.value = c.nombre;
    form.celular.value = c.celular;
    $$(`input[name=tipo_doc]`).forEach((x) => (x.checked = x.value === c.tipo_doc));
    $("#ayuda-doc").innerHTML = `<b class="ok">Cliente registrado.</b> Se completaron sus datos.`;
    [form.nombre, form.celular].forEach(pulso);
    if (c.equipos.length) {
      caja.innerHTML = `<span class="et-campo">Equipos de este cliente · tocá uno para cargarlo</span>` +
        c.equipos.map((e) => `<button type="button" class="equipo-previo" data-slug="${e.slug}" data-serie="${esc(e.serie)}"><b>${esc(e.modelo)}</b> ${esc(e.serie)}</button>`).join("");
      caja.hidden = false;
      $$(".equipo-previo", caja).forEach((b) => b.addEventListener("click", () => {
        elegirModelo(b.dataset.slug);
        form.serie.value = b.dataset.serie;
        buscarSerie();
        actualizarSticker();
      }));
    } else caja.hidden = true;
    actualizarSticker();
  });

  // ------------------------------------------------------------ modelos
  $("#buscar-modelo").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    $$(".modelo-op").forEach((m) => (m.hidden = q && !m.dataset.busca.includes(q)));
  });

  function elegirModelo(slug) {
    const r = $(`input[name=herramienta][value="${slug}"]`);
    if (!r) return;
    r.checked = true;
    r.closest(".modelo-op").hidden = false;
    cargarSintomas(slug);
  }
  $$("input[name=herramienta]").forEach((r) => r.addEventListener("change", () => cargarSintomas(r.value)));

  async function cargarSintomas(slug) {
    const datos = await fetch(`/api/herramientas/${slug}/sintomas`).then((r) => r.json());
    const caja = $("#sintomas-rapidos");
    const validos = new Set(datos.sintomas.map((s) => s.codigo));
    [...sintomasMarcados].forEach((c) => validos.has(c) || sintomasMarcados.delete(c));
    caja.innerHTML = datos.sintomas.map((s, i) => `
      <button type="button" class="chip-sintoma" data-cod="${s.codigo}" aria-pressed="${sintomasMarcados.has(s.codigo)}" style="animation-delay:${i * 18}ms">${esc(s.texto)}</button>`).join("");
    $$(".chip-sintoma", caja).forEach((b) => b.addEventListener("click", () => {
      const c = b.dataset.cod;
      sintomasMarcados.has(c) ? sintomasMarcados.delete(c) : sintomasMarcados.add(c);
      b.setAttribute("aria-pressed", sintomasMarcados.has(c));
    }));
    caja.classList.toggle("apagado", $("#no-sabe").checked);
    if (form.serie.value) buscarSerie();
  }
  $("#no-sabe").addEventListener("change", (e) => $("#sintomas-rapidos").classList.toggle("apagado", e.target.checked));

  // ------------------------------------------------------------ serie: ¿ya lo conocemos?
  let espera;
  form.serie.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(buscarSerie, 350); });
  async function buscarSerie() {
    const serie = form.serie.value.trim();
    const caja = $("#aviso-serie");
    if (serie.length < 3) { caja.hidden = true; return; }
    const lista = await fetch(`/api/equipos?serie=${encodeURIComponent(serie)}`).then((r) => r.json());
    if (!lista.length) { caja.hidden = true; return; }
    caja.innerHTML = lista.map((e) => `
      <div><b>Equipo conocido · ${esc(e.modelo)} ${esc(e.serie)}</b>
        <span>A nombre de ${esc(e.cliente)} (${esc(e.documento)}). Ingresos anteriores:</span>
        <ul>${e.ordenes.map((o) => `<li><a href="/recepcion/${o.numero}" target="_blank">${o.numero}</a> · ${o.ingreso} · ${esc(o.estado)}</li>`).join("")}</ul>
        ${$("input[name=herramienta]:checked")?.value === e.slug ? "" : `<button type="button" class="usar" data-slug="${e.slug}">Usar este modelo</button>`}
      </div>`).join("");
    caja.hidden = false;
    $$(".usar", caja).forEach((b) => b.addEventListener("click", () => { elegirModelo(b.dataset.slug); actualizarSticker(); buscarSerie(); }));
  }

  // ------------------------------------------------------------ enviar
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("#error-form");
    err.textContent = "";
    const accesorios = $$("input[name=accesorios]:checked").map((a) => a.value);
    if (form.acc_otros.value.trim()) accesorios.push(form.acc_otros.value.trim());
    const cuerpo = {
      tipo_doc: form.tipo_doc.value,
      documento: form.documento.value,
      nombre: form.nombre.value,
      herramienta: $("input[name=herramienta]:checked")?.value,
      serie: form.serie.value,
      celular: form.celular.value,
      cliente_no_sabe: $("#no-sabe").checked,
      sintomas: [...sintomasMarcados],
      observaciones: form.observaciones.value,
      accesorios,
    };
    const boton = $("#registrar");
    boton.disabled = true;
    const r = await fetch("/api/ordenes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
    const datos = await r.json();
    if (!r.ok) {
      boton.disabled = false;
      err.textContent = datos.error;
      err.animate([{ transform: "translateX(-6px)" }, { transform: "translateX(6px)" }, { transform: "none" }], { duration: 260 });
      return;
    }
    try { sessionStorage.setItem("avisos", JSON.stringify(datos.avisos)); } catch {}
    $(".cortina").classList.add("entra");
    setTimeout(() => (location.href = datos.url), 480);
  });

  actualizarSticker();
})();
