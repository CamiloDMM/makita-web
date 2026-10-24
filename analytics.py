"""Indicadores del dashboard de garantías, calculados con Pandas."""
import pandas as pd

from models import engine

SLA_DIAS = 15

CONSULTA = """
SELECT c.numero, c.sucursal, c.fecha_ingreso, c.fecha_cierre, c.resultado, c.costo_gs,
       h.slug AS herramienta, h.modelo, h.nombre AS herramienta_nombre, h.linea,
       k.codigo AS causa_cod, k.titulo AS causa, k.cubre_garantia
FROM caso_garantia c
JOIN herramienta h ON h.id = c.herramienta_id
JOIN causa k ON k.id = c.causa_id
"""


def cargar() -> pd.DataFrame:
    df = pd.read_sql(CONSULTA, engine, parse_dates=["fecha_ingreso", "fecha_cierre"])
    df["dias"] = (df["fecha_cierre"] - df["fecha_ingreso"]).dt.days
    df["mes"] = df["fecha_ingreso"].dt.to_period("M")
    return df


def _filtrar(df, desde=None, hasta=None, sucursal=None, herramienta=None):
    if desde:
        df = df[df["fecha_ingreso"] >= pd.Timestamp(desde + "-01")]
    if hasta:
        df = df[df["mes"] <= pd.Period(hasta, "M")]
    if sucursal:
        df = df[df["sucursal"] == sucursal]
    if herramienta:
        df = df[df["herramienta"] == herramienta]
    return df


def tablero(desde=None, hasta=None, sucursal=None, herramienta=None) -> dict:
    todo = cargar()
    df = _filtrar(todo, desde, hasta, sucursal, herramienta)
    cerrados = df[df["resultado"] != "En proceso"]

    if df.empty:
        return {"vacio": True}

    # --- KPIs ---
    total = len(df)
    rechazo = (cerrados["resultado"] == "Rechazado").mean() * 100 if len(cerrados) else 0
    en_sla = (cerrados["dias"] <= SLA_DIAS).mean() * 100 if len(cerrados) else 0
    reparaciones = cerrados[cerrados["resultado"] != "Rechazado"]
    kpis = {
        "casos": total,
        "abiertos": int((df["resultado"] == "En proceso").sum()),
        "mediana_dias": float(reparaciones["dias"].median()) if len(reparaciones) else 0,
        "p90_dias": float(reparaciones["dias"].quantile(.9)) if len(reparaciones) else 0,
        "en_sla": round(en_sla, 1),
        "rechazo": round(rechazo, 1),
        "costo": int(df["costo_gs"].sum()),
    }

    # --- casos por mes y resultado ---
    por_mes = (df.groupby(["mes", "resultado"]).size().unstack(fill_value=0)
                 .reindex(columns=["Reparado", "Reemplazo", "Rechazado", "En proceso"], fill_value=0))
    meses = pd.period_range(df["mes"].min(), df["mes"].max(), freq="M")
    por_mes = por_mes.reindex(meses, fill_value=0)
    serie_mes = {
        "meses": [p.strftime("%Y-%m") for p in por_mes.index],
        "series": {col: por_mes[col].astype(int).tolist() for col in por_mes.columns},
    }

    # --- fallas por herramienta ---
    por_herr = (df.groupby(["modelo", "herramienta_nombre"]).size()
                  .sort_values(ascending=False).reset_index(name="casos"))
    herr = [{"modelo": r.modelo, "nombre": r.herramienta_nombre, "casos": int(r.casos)}
            for r in por_herr.itertuples()]

    # --- causas más frecuentes ---
    por_causa = df.groupby(["causa_cod", "causa", "cubre_garantia"]).size() \
                  .sort_values(ascending=False).head(10).reset_index(name="casos")
    causas = [{"codigo": r.causa_cod, "titulo": r.causa, "casos": int(r.casos),
               "garantia": bool(r.cubre_garantia)} for r in por_causa.itertuples()]

    # --- tiempo de resolución por sucursal ---
    t_suc = (cerrados[cerrados["resultado"] != "Rechazado"].groupby("sucursal")["dias"]
             .agg(mediana="median", p90=lambda s: s.quantile(.9), casos="count")
             .sort_values("mediana"))
    sucursales = [{"sucursal": i, "mediana": float(r.mediana), "p90": float(r.p90),
                   "casos": int(r.casos)} for i, r in t_suc.iterrows()]

    # --- matriz herramienta × causa (top 8 causas) ---
    top_causas = por_causa["causa_cod"].head(8).tolist()
    m = (df[df["causa_cod"].isin(top_causas)]
         .pivot_table(index="modelo", columns="causa_cod", values="numero",
                      aggfunc="count", fill_value=0)
         .reindex(columns=top_causas, fill_value=0))
    matriz = {"filas": m.index.tolist(), "columnas": top_causas,
              "valores": m.astype(int).values.tolist(),
              "nombres": dict(zip(por_causa["causa_cod"], por_causa["causa"]))}

    return {
        "vacio": False,
        "kpis": kpis,
        "por_mes": serie_mes,
        "herramientas": herr,
        "causas": causas,
        "sucursales": sucursales,
        "matriz": matriz,
        "hallazgos": hallazgos(todo, df, cerrados),
        "sla": SLA_DIAS,
    }


def hallazgos(todo, df, cerrados) -> list[dict]:
    """Lecturas concretas que sirven para decidir algo (stock, capacitación, logística)."""
    notas = []

    # 1. causa dominante por modelo
    dom = df.groupby(["modelo", "causa"]).size().reset_index(name="n")
    dom["share"] = dom["n"] / dom.groupby("modelo")["n"].transform("sum")
    fila = dom[dom.groupby("modelo")["n"].transform("sum") >= 40].sort_values("share").iloc[-1:]
    if len(fila):
        r = fila.iloc[0]
        notas.append({
            "tag": "Stock",
            "dato": f"{r.share:.0%}",
            "texto": f"de los casos del {r.modelo} son por «{r.causa}». "
                     f"Conviene tener ese repuesto siempre en mostrador.",
        })

    # 2. rechazos por mal uso
    mal_uso = df[df["causa_cod"].isin(["C12", "C11", "C21"])]
    if len(df):
        notas.append({
            "tag": "Capacitación",
            "dato": f"{len(mal_uso) / len(df):.0%}",
            "texto": "de los ingresos son por sobrecarga, polvo o mala instalación eléctrica. "
                     "Una guía de uso en el punto de venta bajaría estos rechazos.",
        })

    # 3. sucursal más lenta vs. la más rápida
    rep = cerrados[cerrados["resultado"] != "Rechazado"]
    if rep["sucursal"].nunique() > 1:
        med = rep.groupby("sucursal")["dias"].median().sort_values()
        notas.append({
            "tag": "Logística",
            "dato": f"+{med.iloc[-1] - med.iloc[0]:.0f} días",
            "texto": f"demora {med.index[-1]} respecto de {med.index[0]} en cerrar una "
                     f"reparación (mediana). La diferencia viene del envío de repuestos.",
        })

    # 4. tendencia últimos 3 meses vs. mismos meses del año anterior
    mensual = todo.groupby("mes").size()
    if len(mensual) >= 15:
        ult = mensual.iloc[-4:-1].sum()
        ant = mensual.iloc[-16:-13].sum()
        if ant:
            var = (ult - ant) / ant
            notas.append({
                "tag": "Tendencia",
                "dato": f"{var:+.0%}",
                "texto": "de ingresos en los últimos tres meses cerrados contra el mismo "
                         "período del año anterior (toda la red).",
            })
    return notas


def opciones() -> dict:
    df = cargar()
    return {
        "sucursales": sorted(df["sucursal"].unique().tolist()),
        "herramientas": (df[["herramienta", "modelo", "herramienta_nombre"]]
                         .drop_duplicates().sort_values("modelo")
                         .rename(columns={"herramienta_nombre": "nombre"})
                         .to_dict("records")),
        "meses": [p.strftime("%Y-%m") for p in sorted(df["mes"].unique())],
    }
