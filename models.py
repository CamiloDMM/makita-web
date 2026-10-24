"""Modelo de datos.

Funciona con PostgreSQL (DATABASE_URL=postgresql+psycopg://...) y cae a SQLite
si la variable no está definida, para poder correr la demo sin instalar nada.
"""
import os
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "banco.db")
)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Herramienta(Base):
    __tablename__ = "herramienta"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    modelo: Mapped[str] = mapped_column(String(20))
    linea: Mapped[str] = mapped_column(String(20))        # "Cable 220V" | "LXT 18V"
    potencia: Mapped[str] = mapped_column(String(30))
    # rasgos que habilitan síntomas/causas: cable, bateria, carbones, brushless,
    # percusion, rotomartillo, impacto, portabrocas, disco, freno, orbital, vaiven
    rasgos: Mapped[str] = mapped_column(String(200))

    def tiene(self, rasgo: str | None) -> bool:
        return not rasgo or rasgo in self.rasgos.split(",")


class Sintoma(Base):
    __tablename__ = "sintoma"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True)
    texto: Mapped[str] = mapped_column(String(120))
    grupo: Mapped[str] = mapped_column(String(20))        # eléctrico, térmico, mecánico, batería
    requiere: Mapped[str | None] = mapped_column(String(30), nullable=True)


class Causa(Base):
    __tablename__ = "causa"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True)
    titulo: Mapped[str] = mapped_column(String(120))
    componente: Mapped[str] = mapped_column(String(60))
    explicacion: Mapped[str] = mapped_column(Text)
    solucion: Mapped[str] = mapped_column(Text)            # pasos separados por "|"
    dificultad: Mapped[int] = mapped_column(Integer)       # 1 usuario · 2 técnico · 3 servicio oficial
    cubre_garantia: Mapped[bool] = mapped_column(Boolean, default=True)
    requiere: Mapped[str | None] = mapped_column(String(30), nullable=True)


class Regla(Base):
    """Relación síntoma → causa con un peso (qué tan fuerte la sugiere)."""
    __tablename__ = "regla"

    id: Mapped[int] = mapped_column(primary_key=True)
    sintoma_id: Mapped[int] = mapped_column(ForeignKey("sintoma.id"))
    causa_id: Mapped[int] = mapped_column(ForeignKey("causa.id"))
    peso: Mapped[float] = mapped_column(Float)

    sintoma: Mapped[Sintoma] = relationship()
    causa: Mapped[Causa] = relationship()


class CasoGarantia(Base):
    """Datos SIMULADOS de casos de garantía."""
    __tablename__ = "caso_garantia"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(14), unique=True)
    herramienta_id: Mapped[int] = mapped_column(ForeignKey("herramienta.id"))
    causa_id: Mapped[int] = mapped_column(ForeignKey("causa.id"))
    sucursal: Mapped[str] = mapped_column(String(40))
    fecha_ingreso: Mapped[date] = mapped_column(Date)
    fecha_cierre: Mapped[date | None] = mapped_column(Date, nullable=True)
    resultado: Mapped[str] = mapped_column(String(20))    # Reparado, Reemplazo, Rechazado, En proceso
    costo_gs: Mapped[int] = mapped_column(Integer)         # costo de repuestos+MO en guaraníes

    herramienta: Mapped[Herramienta] = relationship()
    causa: Mapped[Causa] = relationship()


class Consulta(Base):
    """Cada diagnóstico hecho en la web queda registrado."""
    __tablename__ = "consulta"

    id: Mapped[int] = mapped_column(primary_key=True)
    creada: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    herramienta_id: Mapped[int] = mapped_column(ForeignKey("herramienta.id"))
    sintomas: Mapped[str] = mapped_column(String(200))     # códigos separados por coma
    causa_principal_id: Mapped[int | None] = mapped_column(ForeignKey("causa.id"), nullable=True)
    orden_id: Mapped[int | None] = mapped_column(ForeignKey("orden_servicio.id"), nullable=True)


# --------------------------------------------------------------------------
# Recepción de equipos (datos reales que carga el taller)
# --------------------------------------------------------------------------
class Cliente(Base):
    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_doc: Mapped[str] = mapped_column(String(4))       # CI | RUC
    documento: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    celular: Mapped[str] = mapped_column(String(20))
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Equipo(Base):
    """Una herramienta física, identificada por modelo + número de serie."""
    __tablename__ = "equipo"
    __table_args__ = (UniqueConstraint("herramienta_id", "serie"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    herramienta_id: Mapped[int] = mapped_column(ForeignKey("herramienta.id"))
    serie: Mapped[str] = mapped_column(String(40), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))

    herramienta: Mapped[Herramienta] = relationship()
    cliente: Mapped[Cliente] = relationship()


ESTADOS = ["Recibido", "Diagnosticado", "En reparación", "Esperando repuesto", "Listo para retirar", "Entregado"]


class OrdenServicio(Base):
    __tablename__ = "orden_servicio"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(14), unique=True)   # el número del sticker
    ingreso: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipo.id"))
    sintomas: Mapped[str] = mapped_column(String(200), default="")  # lo que relata el cliente
    cliente_no_sabe: Mapped[bool] = mapped_column(Boolean, default=False)
    observaciones: Mapped[str] = mapped_column(Text, default="")
    accesorios: Mapped[str] = mapped_column(Text, default="")        # separados por "|"
    estado: Mapped[str] = mapped_column(String(30), default="Recibido")
    causa_id: Mapped[int | None] = mapped_column(ForeignKey("causa.id"), nullable=True)

    cliente: Mapped[Cliente] = relationship()
    equipo: Mapped[Equipo] = relationship()
    causa: Mapped[Causa | None] = relationship()
