// Transiciones compartidas: cortina entre páginas, revelado al hacer scroll,
// títulos palabra por palabra y contadores.
(() => {
  const cortina = document.querySelector(".cortina");

  // Al salir hacia otra página interna, la cortina entra y luego navega.
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href]");
    if (!a || a.target || e.metaKey || e.ctrlKey || e.shiftKey) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || url.pathname === location.pathname) return;
    e.preventDefault();
    cortina.classList.add("entra");
    setTimeout(() => (location.href = url.href), 480);
  });
  // volver con el botón "atrás" no debe dejar la cortina puesta
  window.addEventListener("pageshow", (e) => { if (e.persisted) cortina.classList.remove("entra"); });

  // Títulos: cada palabra sube desde una máscara.
  document.querySelectorAll(".palabras").forEach((el) => {
    let i = 0;
    const partir = (nodo) => {
      [...nodo.childNodes].forEach((n) => {
        if (n.nodeType === 3) {
          const frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach((w) => {
            if (!w.trim()) { frag.append(w); return; }
            const p = document.createElement("span");
            p.className = "p";
            p.innerHTML = `<span style="--i:${i++}"></span>`;
            p.firstChild.textContent = w;
            frag.append(p);
          });
          n.replaceWith(frag);
        } else if (n.nodeType === 1 && n.tagName !== "BR") partir(n);
      });
    };
    partir(el);
  });

  // Contadores que suben hasta su valor.
  window.contar = (el, hasta, { dur = 1100, dec = 0, sufijo = "" } = {}) => {
    const desde = parseFloat(el.dataset.actual || 0);
    const t0 = performance.now();
    const fmt = new Intl.NumberFormat("es-PY", { minimumFractionDigits: dec, maximumFractionDigits: dec });
    const paso = (t) => {
      const k = Math.min(1, (t - t0) / dur);
      const e = 1 - Math.pow(1 - k, 4);
      el.textContent = fmt.format(desde + (hasta - desde) * e) + sufijo;
      if (k < 1) requestAnimationFrame(paso);
    };
    el.dataset.actual = hasta;
    requestAnimationFrame(paso);
  };

  const obs = new IntersectionObserver((entradas) => {
    entradas.forEach((en) => {
      if (!en.isIntersecting) return;
      en.target.classList.add("visto");
      if (en.target.dataset.cuenta) contar(en.target, +en.target.dataset.cuenta);
      obs.unobserve(en.target);
    });
  }, { threshold: .2 });
  document.querySelectorAll(".revela, [data-cuenta]").forEach((el, i) => {
    if (el.classList.contains("revela")) el.style.transitionDelay = `${(i % 4) * 80}ms`;
    obs.observe(el);
  });
  // lo que ya está en pantalla al cargar se muestra sin esperar al observador
  setTimeout(() => document.querySelectorAll(".revela:not(.visto)").forEach((el) => {
    if (el.getBoundingClientRect().top < innerHeight) el.classList.add("visto");
  }), 600);
})();
