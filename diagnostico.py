"""Motor de diagnóstico.

Para cada causa posible se combinan los pesos de los síntomas marcados con un
"O ruidoso" (noisy-OR): p = 1 - Π(1 - peso). Así, dos síntomas que apuntan a la
misma causa la refuerzan sin pasar nunca de 1.

Después se ajusta con la frecuencia histórica de esa causa en los casos de
garantía de la misma herramienta: entre dos causas con evidencia parecida,
gana la que más se ve en el taller.
"""
from collections import defaultdict

from sqlalchemy import func, select

from models import CasoGarantia, Causa, Consulta, Herramienta, Regla, Sintoma

PESO_HISTORICO = 0.25


def sintomas_para(session, herramienta: Herramienta):
    todos = session.scalars(select(Sintoma).order_by(Sintoma.id)).all()
    return [s for s in todos if herramienta.tiene(s.requiere)]


def diagnosticar(session, herramienta: Herramienta, codigos: list[str], top: int = 4, orden=None):
    sintomas = [s for s in sintomas_para(session, herramienta) if s.codigo in codigos]
    if not sintomas:
        return []

    reglas = session.scalars(
        select(Regla).where(Regla.sintoma_id.in_([s.id for s in sintomas]))
    ).all()

    no_explica = defaultdict(lambda: 1.0)
    explica = defaultdict(list)
    for r in reglas:
        if not herramienta.tiene(r.causa.requiere):
            continue
        no_explica[r.causa_id] *= 1 - r.peso
        explica[r.causa_id].append(r.sintoma.texto)

    # historial de la misma herramienta
    filas = session.execute(
        select(CasoGarantia.causa_id, func.count())
        .where(CasoGarantia.herramienta_id == herramienta.id)
        .group_by(CasoGarantia.causa_id)
    ).all()
    historial = dict(filas)
    total_hist = sum(historial.values()) or 1
    max_hist = max(historial.values(), default=1)

    resultados = []
    for causa_id, resto in no_explica.items():
        evidencia = 1 - resto
        frecuencia = historial.get(causa_id, 0) / max_hist
        puntaje = evidencia * ((1 - PESO_HISTORICO) + PESO_HISTORICO * frecuencia)
        resultados.append((causa_id, puntaje, evidencia))

    resultados.sort(key=lambda t: t[1], reverse=True)
    resultados = resultados[:top]
    suma = sum(p for _, p, _ in resultados) or 1

    salida = []
    for causa_id, puntaje, evidencia in resultados:
        c = session.get(Causa, causa_id)
        salida.append({
            "codigo": c.codigo,
            "titulo": c.titulo,
            "componente": c.componente,
            "explicacion": c.explicacion,
            "pasos": c.solucion.split("|"),
            "dificultad": c.dificultad,
            "cubre_garantia": c.cubre_garantia,
            "probabilidad": round(100 * puntaje / suma),
            "coincidencia": round(100 * evidencia),
            "explica": explica[causa_id],
            "casos": historial.get(causa_id, 0),
            "casos_pct": round(100 * historial.get(causa_id, 0) / total_hist, 1),
        })

    session.add(Consulta(
        herramienta_id=herramienta.id,
        sintomas=",".join(s.codigo for s in sintomas),
        causa_principal_id=resultados[0][0] if resultados else None,
        orden_id=orden.id if orden else None,
    ))
    # si el diagnóstico viene de una orden del mismo equipo, queda anotado en ella
    if orden and resultados and orden.equipo.herramienta_id == herramienta.id:
        orden.causa_id = resultados[0][0]
        if orden.estado == "Recibido":
            orden.estado = "Diagnosticado"
    session.commit()
    return salida
