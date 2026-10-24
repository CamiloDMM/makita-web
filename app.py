from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func, select

import analytics
import recepcion
from diagnostico import diagnosticar, sintomas_para
from models import (
    ESTADOS, Base, CasoGarantia, Causa, Consulta, Herramienta, OrdenServicio, Regla,
    SessionLocal, Sintoma, engine,
)

app = Flask(__name__)
Base.metadata.create_all(engine)   # crea las tablas nuevas si la base es anterior


def _herramienta(session, slug):
    h = session.scalar(select(Herramienta).where(Herramienta.slug == slug))
    if not h:
        abort(404)
    return h


@app.get("/")
def inicio():
    with SessionLocal() as s:
        cifras = {
            "herramientas": s.scalar(select(func.count(Herramienta.id))),
            "causas": s.scalar(select(func.count(Causa.id))),
            "reglas": s.scalar(select(func.count(Regla.id))),
            "casos": s.scalar(select(func.count(CasoGarantia.id))),
            "consultas": s.scalar(select(func.count(Consulta.id))),
            "ordenes": s.scalar(select(func.count(OrdenServicio.id))),
        }
        modelos = s.scalars(select(Herramienta.modelo)).all()
    return render_template("inicio.html", cifras=cifras, modelos=modelos)


def _herramientas(s):
    return s.scalars(select(Herramienta).order_by(Herramienta.linea, Herramienta.modelo)).all()


@app.get("/diagnostico")
def diagnostico():
    orden = None
    with SessionLocal() as s:
        herramientas = _herramientas(s)
        total_reglas = s.scalar(select(func.count(Regla.id)))
        if request.args.get("orden"):
            o = s.scalar(select(OrdenServicio).where(OrdenServicio.numero == request.args["orden"]))
            orden = recepcion.orden_a_dict(o) if o else None
    return render_template("diagnostico.html", herramientas=herramientas,
                           total_reglas=total_reglas, orden=orden)


# ---------------------------------------------------------------- recepción
@app.get("/recepcion")
def recepcion_inicio():
    q = request.args.get("q", "")
    with SessionLocal() as s:
        herramientas = _herramientas(s)
        ordenes = recepcion.listar_ordenes(s, q)
        abiertas = s.scalar(select(func.count(OrdenServicio.id))
                            .where(OrdenServicio.estado != "Entregado"))
    return render_template("recepcion.html", herramientas=herramientas, ordenes=ordenes, q=q,
                           accesorios=recepcion.ACCESORIOS, abiertas=abiertas, estados=ESTADOS)


@app.get("/recepcion/<numero>")
def recepcion_ficha(numero):
    with SessionLocal() as s:
        o = s.scalar(select(OrdenServicio).where(OrdenServicio.numero == numero))
        if not o:
            abort(404)
        orden = recepcion.orden_a_dict(o)
        textos = {x.codigo: x.texto for x in s.scalars(select(Sintoma)).all()}
        historial = [h for h in recepcion.buscar_serie(s, o.equipo.serie)
                     if h["modelo"] == orden["modelo"]]
    return render_template("orden.html", o=orden, textos=textos, estados=ESTADOS,
                           historial=historial[0]["ordenes"] if historial else [],
                           nueva=request.args.get("nueva"))


@app.post("/recepcion/<numero>/estado")
def recepcion_estado(numero):
    with SessionLocal() as s:
        o = s.scalar(select(OrdenServicio).where(OrdenServicio.numero == numero))
        if not o:
            abort(404)
        if request.form.get("estado") in ESTADOS:
            o.estado = request.form["estado"]
            s.commit()
    return redirect(url_for("recepcion_ficha", numero=numero))


@app.post("/api/ordenes")
def api_crear_orden():
    with SessionLocal() as s:
        try:
            orden, avisos = recepcion.crear_orden(s, request.get_json(force=True))
        except ValueError as e:
            s.rollback()
            return jsonify({"error": str(e)}), 400
        return jsonify({"numero": orden.numero, "avisos": avisos,
                        "url": url_for("recepcion_ficha", numero=orden.numero, nueva=1)})


@app.get("/api/clientes/<path:documento>")
def api_cliente(documento):
    with SessionLocal() as s:
        c = recepcion.buscar_cliente(s, documento)
    return (jsonify(c), 200) if c else (jsonify({}), 404)


@app.get("/api/equipos")
def api_equipos():
    with SessionLocal() as s:
        return jsonify(recepcion.buscar_serie(s, request.args.get("serie", "")))


@app.get("/tablero")
def tablero():
    return render_template("tablero.html", opciones=analytics.opciones())


# ---------------------------------------------------------------- API
@app.get("/api/herramientas/<slug>/sintomas")
def api_sintomas(slug):
    with SessionLocal() as s:
        h = _herramienta(s, slug)
        casos = s.scalar(select(func.count(CasoGarantia.id))
                         .where(CasoGarantia.herramienta_id == h.id))
        return jsonify({
            "herramienta": {"slug": h.slug, "modelo": h.modelo, "nombre": h.nombre,
                            "linea": h.linea, "casos": casos},
            "sintomas": [{"codigo": x.codigo, "texto": x.texto, "grupo": x.grupo}
                         for x in sintomas_para(s, h)],
        })


@app.post("/api/diagnostico")
def api_diagnostico():
    datos = request.get_json(force=True)
    codigos = datos.get("sintomas") or []
    with SessionLocal() as s:
        h = _herramienta(s, datos.get("herramienta"))
        orden = None
        if datos.get("orden"):
            orden = s.scalar(select(OrdenServicio).where(OrdenServicio.numero == datos["orden"]))
        resultado = diagnosticar(s, h, codigos, orden=orden)
        n_reglas = s.scalar(select(func.count(Regla.id)))
        consulta = s.scalar(select(func.max(Consulta.id)))
    return jsonify({"causas": resultado, "reglas": n_reglas, "orden": consulta,
                    "orden_servicio": orden.numero if orden else None})


@app.get("/api/tablero")
def api_tablero():
    a = request.args
    return jsonify(analytics.tablero(
        desde=a.get("desde") or None, hasta=a.get("hasta") or None,
        sucursal=a.get("sucursal") or None, herramienta=a.get("herramienta") or None,
    ))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
