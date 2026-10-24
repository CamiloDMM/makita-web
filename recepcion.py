"""Recepción de equipos: clientes, equipos por número de serie y órdenes de servicio."""
import re
from datetime import datetime

from sqlalchemy import func, or_, select

from models import Cliente, Equipo, Herramienta, OrdenServicio

ACCESORIOS = [
    "Maletín", "Batería", "Cargador", "Mango lateral", "Protector de disco",
    "Llave / llave de mandril", "Disco u hoja", "Broca", "Guía paralela",
    "Bolsa recolectora", "Caja original",
]


# ------------------------------------------------------------------ validaciones
def solo_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def dv_ruc(base: str) -> int:
    """Dígito verificador del RUC paraguayo (módulo 11, pesos 2..11 de derecha a izquierda)."""
    total, peso = 0, 2
    for d in reversed(base):
        total += int(d) * peso
        peso = 2 if peso == 11 else peso + 1
    resto = total % 11
    return 11 - resto if resto > 1 else 0


def normalizar_documento(tipo: str, valor: str) -> tuple[str, str | None]:
    """Devuelve (documento normalizado, aviso). El aviso no bloquea la carga."""
    valor = (valor or "").strip().upper()
    if tipo == "RUC":
        m = re.fullmatch(r"(\d{3,9})\s*-?\s*(\d)", valor.replace(".", ""))
        if not m:
            raise ValueError("El RUC debe tener el formato 1234567-8.")
        base, dv = m.groups()
        aviso = None if dv_ruc(base) == int(dv) else (
            f"El dígito verificador no coincide (debería ser {dv_ruc(base)}). Revisalo con el cliente.")
        return f"{base}-{dv}", aviso
    numero = solo_digitos(valor)
    if not 5 <= len(numero) <= 9:
        raise ValueError("La cédula debe tener entre 5 y 9 números.")
    return numero, None


def normalizar_celular(valor: str) -> tuple[str, str | None]:
    d = solo_digitos(valor)
    if d.startswith("595"):
        d = "0" + d[3:]
    if not d:
        raise ValueError("Falta el número de celular.")
    if re.fullmatch(r"09\d{8}", d):
        return f"{d[:4]} {d[4:7]} {d[7:]}", None
    return valor.strip(), "No parece un celular paraguayo (09XX XXX XXX). Se guardó tal cual."


# ------------------------------------------------------------------ consultas
def orden_a_dict(o: OrdenServicio) -> dict:
    h = o.equipo.herramienta
    return {
        "numero": o.numero,
        "ingreso": o.ingreso.strftime("%d/%m/%Y %H:%M"),
        "estado": o.estado,
        "modelo": h.modelo, "herramienta": h.nombre, "slug": h.slug,
        "serie": o.equipo.serie,
        "cliente": o.cliente.nombre, "documento": o.cliente.documento,
        "tipo_doc": o.cliente.tipo_doc, "celular": o.cliente.celular,
        "sintomas": [s for s in o.sintomas.split(",") if s],
        "cliente_no_sabe": o.cliente_no_sabe,
        "observaciones": o.observaciones,
        "accesorios": [a for a in o.accesorios.split("|") if a],
        "causa": o.causa.titulo if o.causa else None,
    }


def buscar_cliente(s, documento: str):
    doc = documento.strip().upper().replace(".", "")
    c = s.scalar(select(Cliente).where(or_(Cliente.documento == doc,
                                           Cliente.documento == solo_digitos(doc))))
    if not c:
        return None
    equipos = s.scalars(select(Equipo).where(Equipo.cliente_id == c.id)).all()
    return {
        "tipo_doc": c.tipo_doc, "documento": c.documento, "nombre": c.nombre, "celular": c.celular,
        "equipos": [{"modelo": e.herramienta.modelo, "slug": e.herramienta.slug, "serie": e.serie}
                    for e in equipos],
    }


def buscar_serie(s, serie: str):
    serie = serie.strip().upper()
    if len(serie) < 3:
        return []
    equipos = s.scalars(select(Equipo).where(func.upper(Equipo.serie) == serie)).all()
    salida = []
    for e in equipos:
        ordenes = s.scalars(select(OrdenServicio).where(OrdenServicio.equipo_id == e.id)
                            .order_by(OrdenServicio.ingreso.desc())).all()
        salida.append({
            "modelo": e.herramienta.modelo, "slug": e.herramienta.slug, "serie": e.serie,
            "cliente": e.cliente.nombre, "documento": e.cliente.documento,
            "ordenes": [{"numero": o.numero, "ingreso": o.ingreso.strftime("%d/%m/%Y"),
                         "estado": o.estado} for o in ordenes],
        })
    return salida


def listar_ordenes(s, q: str = "", limite: int = 60):
    consulta = (select(OrdenServicio).join(Cliente).join(Equipo)
                .join(Herramienta, Herramienta.id == Equipo.herramienta_id)
                .order_by(OrdenServicio.ingreso.desc()).limit(limite))
    if q:
        patron = f"%{q.strip()}%"
        consulta = consulta.where(or_(
            OrdenServicio.numero.ilike(patron), Equipo.serie.ilike(patron),
            Cliente.documento.ilike(patron), Cliente.nombre.ilike(patron),
            Herramienta.modelo.ilike(patron),
        ))
    return [orden_a_dict(o) for o in s.scalars(consulta).all()]


# ------------------------------------------------------------------ alta
def crear_orden(s, datos: dict) -> tuple[OrdenServicio, list[str]]:
    avisos = []
    tipo = datos.get("tipo_doc") if datos.get("tipo_doc") in ("CI", "RUC") else "CI"
    documento, aviso = normalizar_documento(tipo, datos.get("documento", ""))
    avisos += [aviso] if aviso else []

    nombre = " ".join((datos.get("nombre") or "").split())
    if len(nombre) < 3:
        raise ValueError("Falta el nombre del cliente.")
    celular, aviso = normalizar_celular(datos.get("celular", ""))
    avisos += [aviso] if aviso else []

    h = s.scalar(select(Herramienta).where(Herramienta.slug == datos.get("herramienta")))
    if not h:
        raise ValueError("Elegí el modelo de la herramienta.")
    serie = (datos.get("serie") or "").strip().upper()
    if len(serie) < 3:
        raise ValueError("Falta el número de serie (está en la etiqueta plateada del equipo).")

    cliente = s.scalar(select(Cliente).where(Cliente.documento == documento))
    if cliente:
        cliente.nombre, cliente.celular = nombre, celular
    else:
        cliente = Cliente(tipo_doc=tipo, documento=documento, nombre=nombre, celular=celular)
        s.add(cliente)
    s.flush()

    equipo = s.scalar(select(Equipo).where(Equipo.herramienta_id == h.id, Equipo.serie == serie))
    if equipo and equipo.cliente_id != cliente.id:
        avisos.append(f"Este equipo figuraba a nombre de {equipo.cliente.nombre}. "
                      f"Quedó asignado a {nombre}.")
        equipo.cliente_id = cliente.id
    elif not equipo:
        equipo = Equipo(herramienta_id=h.id, serie=serie, cliente_id=cliente.id)
        s.add(equipo)
    s.flush()

    no_sabe = bool(datos.get("cliente_no_sabe"))
    orden = OrdenServicio(
        cliente_id=cliente.id, equipo_id=equipo.id, ingreso=datetime.now(),
        sintomas="" if no_sabe else ",".join(datos.get("sintomas") or []),
        cliente_no_sabe=no_sabe,
        observaciones=(datos.get("observaciones") or "").strip(),
        accesorios="|".join(a.strip() for a in (datos.get("accesorios") or []) if a.strip()),
        numero="pendiente",
    )
    s.add(orden)
    s.flush()
    orden.numero = f"OS-{orden.ingreso:%y}-{orden.id:05d}"
    s.commit()
    return orden, avisos
