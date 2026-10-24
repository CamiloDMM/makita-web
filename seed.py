"""Carga la base de conocimiento y genera casos de garantía SIMULADOS.

    python seed.py

Borra y vuelve a crear todas las tablas. Ningún dato proviene de clientes reales:
los casos se generan con una semilla fija a partir de frecuencias plausibles.
"""
import math
import random
import sys
from datetime import date, timedelta

from models import (
    Base, Causa, CasoGarantia, Herramienta, Regla, SessionLocal, Sintoma, engine,
)

# --------------------------------------------------------------------------
# Herramientas
# --------------------------------------------------------------------------
HERRAMIENTAS = [
    # slug, nombre, modelo, línea, potencia, rasgos, volumen relativo, precio Gs
    ("taladro-percutor", "Taladro percutor 13 mm", "HP1630", "Cable 220V", "710 W",
     "cable,carbones,golpe,portabrocas", 1.3, 690_000),
    ("amoladora-115", "Amoladora angular 115 mm", "GA4530", "Cable 220V", "720 W",
     "cable,carbones,disco", 1.6, 560_000),
    ("amoladora-230", "Amoladora angular 230 mm", "GA9020", "Cable 220V", "2200 W",
     "cable,carbones,disco", 0.9, 1_250_000),
    ("rotomartillo", "Rotomartillo SDS-Plus", "HR2470", "Cable 220V", "780 W",
     "cable,carbones,golpe,rotomartillo", 1.2, 1_480_000),
    ("sierra-circular", "Sierra circular 185 mm", "5007N", "Cable 220V", "1800 W",
     "cable,carbones,disco", 0.6, 1_150_000),
    ("caladora", "Sierra caladora", "4329", "Cable 220V", "450 W",
     "cable,carbones,vaiven", 0.5, 620_000),
    ("lijadora", "Lijadora roto-orbital 125 mm", "BO5031", "Cable 220V", "300 W",
     "cable,carbones,orbital", 0.4, 590_000),
    ("taladro-lxt", "Taladro percutor inalámbrico", "DHP485", "LXT 18V", "Brushless",
     "bateria,brushless,golpe,portabrocas", 0.9, 1_390_000),
    ("impacto-lxt", "Atornillador de impacto", "DTD153", "LXT 18V", "Brushless",
     "bateria,brushless,golpe", 0.8, 1_290_000),
    ("amoladora-lxt", "Amoladora angular inalámbrica", "DGA404", "LXT 18V", "Brushless",
     "bateria,brushless,disco,freno", 0.6, 1_690_000),
    ("amoladora-9557", "Amoladora angular 115 mm", "9557HNG", "Cable 220V", "840 W",
     "cable,carbones,disco", 1.5, 520_000),
    ("taladro-hp1640", "Taladro percutor 13 mm", "HP1640", "Cable 220V", "680 W",
     "cable,carbones,golpe,portabrocas", 1.2, 560_000),
    ("taladro-dhp453", "Taladro percutor inalámbrico", "DHP453", "LXT 18V", "Con carbones",
     "bateria,carbones,golpe,portabrocas", 0.8, 990_000),
    ("sierra-5902b", "Sierra circular 235 mm", "5902B", "Cable 220V", "2000 W",
     "cable,carbones,disco", 0.5, 1_450_000),
    ("cepillo-kp0800", "Cepillo eléctrico 82 mm", "KP0800", "Cable 220V", "620 W",
     "cable,carbones,cepillo,correa", 0.5, 790_000),
    ("cepillo-1805n", "Cepillo eléctrico 155 mm", "1805N", "Cable 220V", "1140 W",
     "cable,carbones,cepillo,correa", 0.3, 2_900_000),
]

# --------------------------------------------------------------------------
# Síntomas
# --------------------------------------------------------------------------
SINTOMAS = [
    ("S01", "No enciende, no hace nada", "eléctrico", None),
    ("S02", "Funciona a ratos: corta y vuelve", "eléctrico", None),
    ("S03", "Chispea mucho por las rejillas (anillo de fuego)", "eléctrico", "carbones"),
    ("S07", "Pierde fuerza cuando se le exige", "eléctrico", None),
    ("S08", "Hace saltar la térmica o el disyuntor", "eléctrico", "cable"),
    ("S09", "No regula la velocidad con el gatillo", "eléctrico", None),
    ("S15", "El gatillo queda trabado o está duro", "eléctrico", None),
    ("S04", "Olor a quemado", "térmico", None),
    ("S05", "Se calienta demasiado en pocos minutos", "térmico", None),
    ("S06", "Sale humo", "térmico", None),
    ("S10", "Ruido metálico o chirrido", "mecánico", None),
    ("S11", "Vibra más de lo normal", "mecánico", None),
    ("S12", "Gira pero no golpea en modo percusión / impacto", "mecánico", "golpe"),
    ("S13", "La broca patina o el mandril no sujeta", "mecánico", "portabrocas"),
    ("S14", "Pierde grasa por la caja de engranajes", "mecánico", None),
    ("S20", "Se frena al apoyar el disco sobre el material", "mecánico", "disco"),
    ("S16", "Tarda en frenar al soltar el gatillo", "mecánico", "freno"),
    ("S21", "La base no oscila o tiene juego", "mecánico", "orbital"),
    ("S22", "La hoja se suelta o el vaivén golpea", "mecánico", "vaiven"),
    ("S23", "El motor gira pero el tambor no", "mecánico", "correa"),
    ("S24", "Deja la madera escalonada o con marcas", "mecánico", "cepillo"),
    ("S25", "No mantiene la profundidad de corte", "mecánico", "cepillo"),
    ("S17", "La batería dura mucho menos que antes", "batería", "bateria"),
    ("S18", "El cargador parpadea y no carga", "batería", "bateria"),
    ("S19", "Se apaga sola cuando trabaja con carga", "batería", "bateria"),
]

# --------------------------------------------------------------------------
# Causas  (pasos de solución separados por "|")
# --------------------------------------------------------------------------
CAUSAS = [
    ("C01", "Carbones gastados", "Escobillas de carbón",
     "Los carbones de Makita tienen auto-corte: cuando llegan al límite, un perno aislante "
     "separa el contacto y la máquina se detiene sola para no dañar el colector. Es "
     "desgaste normal de uso.",
     "Desenchufar y retirar las tapas de carbones (o la carcasa trasera)."
     "|Medir el largo: por debajo de 5–6 mm hay que cambiarlos."
     "|Reemplazar siempre el par completo, con carbones originales del código indicado en el manual."
     "|Hacer girar en vacío 10–15 minutos para que asienten antes de usar con carga.",
     1, False, "carbones", 2.6),
    ("C02", "Colector desgastado u ovalado", "Inducido",
     "Con carbones agotados por mucho tiempo, o con carbones no originales, el colector se "
     "marca y se ovala. El contacto deja de ser parejo y aparecen chispas fuertes.",
     "Revisar el colector: surcos profundos, delgas levantadas o color azulado indican daño."
     "|Si el daño es leve, rectificar en torno y limpiar las micas."
     "|Si hay delgas sueltas o quemadas, reemplazar el inducido completo."
     "|Instalar carbones nuevos junto con la reparación.",
     3, True, "carbones", 0.7),
    ("C03", "Inducido en cortocircuito", "Inducido",
     "Espiras del rotor que se tocan por aislación dañada (calor, polvo metálico). Típico "
     "anillo de fuego alrededor del colector, olor a barniz quemado y pérdida de fuerza.",
     "Probar el inducido con growler o medir resistencia entre delgas contiguas."
     "|Verificar si hay limaduras metálicas dentro de la carcasa (frecuente en amoladoras)."
     "|Reemplazar el inducido; no se recomienda rebobinar en herramientas de esta gama."
     "|Revisar rodamientos y carbones antes de cerrar.",
     3, True, "carbones", 1.4),
    ("C04", "Campo (estator) quemado", "Estator",
     "El bobinado fijo se recalentó por sobrecarga sostenida o por tensión baja. Suele "
     "presentarse con humo y salto de la térmica.",
     "Medir continuidad y aislación a masa de ambas bobinas del campo."
     "|Observar el barniz: oscuro o quebradizo indica sobrecalentamiento."
     "|Reemplazar el campo y revisar el inducido, que suele quedar afectado."
     "|Consultar al usuario sobre extensiones largas o generadores (posible causa de fondo).",
     3, True, "cable", 0.8),
    ("C05", "Interruptor (gatillo) defectuoso", "Interruptor",
     "Contactos internos carbonizados por chispa o polvo dentro del interruptor. Provoca "
     "cortes, gatillo duro o que la máquina directamente no arranque.",
     "Medir continuidad del interruptor con el gatillo presionado."
     "|Inspeccionar si entró polvo fino (yeso, cemento) en la zona del gatillo."
     "|Reemplazar el interruptor completo; no se repara por dentro."
     "|Verificar el ajuste de los cables en los bornes al montar.",
     2, True, None, 1.2),
    ("C06", "Cable de alimentación cortado por dentro", "Cable / protector",
     "El cable se quiebra internamente justo donde sale de la empuñadura, por doblarlo o "
     "colgar la herramienta del cable. Funciona según cómo se mueva.",
     "Con el equipo enchufado a un tester (no a la red), mover el cable cerca del protector."
     "|Revisar también la ficha: tornillos flojos o pernos quemados."
     "|Reemplazar el cable completo; no empalmar."
     "|Colocar el protector de goma en su lugar para que vuelva a aliviar la tensión.",
     2, False, "cable", 1.0),
    ("C07", "Rodamientos dañados", "Rodamientos",
     "Rodamientos con juego o resecos por calor y polvo. Hacen ruido, vibran y aumentan la "
     "temperatura del motor.",
     "Girar el eje a mano: si raspa o tiene juego radial, el rodamiento está dañado."
     "|Reemplazar los rodamientos del inducido (delantero y trasero) juntos."
     "|Verificar que el asiento del rodamiento en la carcasa no esté ovalado."
     "|Limpiar el polvo acumulado alrededor del motor.",
     2, True, None, 1.1),
    ("C08", "Engranajes gastados o sin grasa", "Caja de engranajes",
     "Los dientes del piñón o la corona se desgastan por falta de grasa o golpes de "
     "trabado. El ruido cambia con la carga.",
     "Abrir la caja y revisar dientes desgastados, picados o rotos."
     "|Limpiar toda la grasa vieja: si sale negra con partículas metálicas, revisar todo el tren."
     "|Reemplazar piñón y corona en conjunto."
     "|Engrasar con la cantidad y tipo de grasa indicados para el modelo.",
     3, True, None, 0.9),
    ("C09", "Mecanismo de percusión gastado", "Percusión",
     "En rotomartillos: juntas tóricas del pistón y del percutor resecas, por lo que no "
     "se genera el colchón de aire. En taladros percutores e impacto: trinquetes o "
     "martillo gastados.",
     "Verificar que el selector de modo esté realmente en percusión."
     "|Rotomartillo: revisar juntas tóricas del pistón y del percutor y la grasa del cilindro."
     "|Taladro percutor: inspeccionar los platos de percusión (trinquetes)."
     "|Impacto: revisar martillo, yunque y resorte; reemplazar el conjunto si están redondeados.",
     3, True, "golpe", 1.1),
    ("C10", "Portabrocas desgastado", "Portabrocas",
     "Las mordazas del mandril están gastadas o tienen suciedad, y la broca gira en falso "
     "con poco esfuerzo.",
     "Limpiar las mordazas y verificar que cierren parejo."
     "|Probar con otra broca de cabo cilíndrico en buen estado."
     "|Reemplazar el portabrocas (ojo: suele tener tornillo de rosca izquierda adentro).",
     1, False, "portabrocas", 0.7),
    ("C11", "Ventilación obstruida por polvo", "Ventilación",
     "Las rejillas tapadas no dejan pasar aire y el motor no se enfría. Muy común en "
     "trabajos con cemento, yeso o madera.",
     "Soplar las rejillas con aire comprimido con la máquina en marcha y en vacío."
     "|Revisar que no haya polvo compactado dentro de la carcasa."
     "|Dejar enfriar en vacío 1–2 minutos después de trabajos pesados.",
     1, False, None, 1.0),
    ("C12", "Sobrecarga o uso fuera de especificación", "Uso",
     "Discos o brocas más grandes de lo indicado, presión excesiva o trabajo continuo sin "
     "descanso. No es un defecto de fábrica.",
     "Revisar el accesorio usado contra el máximo que indica la placa del equipo."
     "|Explicar al usuario el ciclo de trabajo: dejar que la herramienta haga el esfuerzo."
     "|Si el motor ya se dañó, cotizar la reparación fuera de garantía.",
     1, False, None, 1.3),
    ("C13", "Celdas de batería degradadas", "Batería LXT",
     "Con los ciclos las celdas pierden capacidad o quedan desbalanceadas. El sistema "
     "Star Protection corta para protegerlas.",
     "Ver el diagnóstico del cargador DC18RC: luz roja/verde parpadeando indica error de batería."
     "|Probar la herramienta con otra batería en buen estado."
     "|Verificar la cantidad de ciclos y la fecha de compra para la garantía."
     "|Reemplazar la batería; no abrir ni intentar 'despertar' celdas.",
     2, True, "bateria", 2.2),
    ("C14", "Terminales sucios o flojos", "Contactos",
     "Polvo, humedad u óxido en los terminales de la batería o de la herramienta. La "
     "conexión se pierde con la vibración.",
     "Revisar los terminales: deformados, oscuros o con restos de suciedad."
     "|Limpiar con aire y un paño seco; no usar líquidos."
     "|Verificar que la traba de la batería ajuste firme.",
     1, False, "bateria", 0.8),
    ("C15", "Controlador electrónico (motor BL) dañado", "Placa controladora",
     "En motores sin carbones la placa controla las bobinas. Humedad, golpes o sobrecargas "
     "repetidas dañan los transistores (MOSFET).",
     "Probar con una batería conocida y en buen estado."
     "|Inspeccionar la placa: componentes hinchados, quemados o con humedad."
     "|Reemplazar el conjunto controlador (no se reparan componentes)."
     "|Confirmar que los sensores del motor estén bien conectados.",
     3, True, "brushless", 1.0),
    ("C16", "Regulador electrónico de velocidad", "Regulador",
     "El circuito que regula la velocidad (dentro o junto al gatillo) dejó de funcionar: "
     "la máquina va a fondo o no sube de vueltas.",
     "Verificar la rueda o dial de velocidad, si el modelo la tiene."
     "|Medir la salida del regulador con el gatillo en distintas posiciones."
     "|Reemplazar interruptor/regulador como conjunto.",
     2, True, "carbones", 0.5),
    ("C17", "Freno electrónico sin funcionar", "Freno",
     "El freno detiene el disco en segundos al soltar el gatillo. Si falla, el disco "
     "sigue girando, lo cual es un riesgo de seguridad.",
     "Comprobar el tiempo de frenado: debería quedar detenido en 2–3 segundos."
     "|Probar con batería cargada; con poca carga el freno puede actuar más lento."
     "|Enviar a servicio oficial: el freno depende del controlador."
     "|No usar la herramienta hasta resolverlo.",
     3, True, "freno", 0.4),
    ("C18", "Retén o junta de caja dañada", "Retén",
     "La junta entre la caja de engranajes y la carcasa, o el retén del eje, dejó de "
     "sellar. La grasa sale y la caja queda seca.",
     "Limpiar la grasa externa y ubicar el punto de fuga."
     "|Reemplazar juntas y retenes."
     "|Rellenar con grasa nueva y verificar el estado de los engranajes.",
     2, True, None, 0.5),
    ("C19", "Sujeción de hoja o guía gastada", "Mecanismo de vaivén",
     "La palanca de cambio rápido y el rodillo guía se desgastan, y la hoja trabaja con juego.",
     "Probar con una hoja nueva de vástago tipo T."
     "|Revisar el rodillo guía y la sujeción de la hoja."
     "|Reemplazar el conjunto de sujeción y el rodillo.",
     2, True, "vaiven", 0.6),
    ("C20", "Base orbital o su rodamiento gastado", "Base orbital",
     "La base o el rodamiento del excéntrico tienen juego. La lija deja marcas y la "
     "herramienta vibra.",
     "Verificar el freno de la base (la goma que evita que gire libre)."
     "|Revisar el rodamiento del excéntrico."
     "|Reemplazar la base si el velcro está gastado o deformado por calor.",
     2, True, "orbital", 0.7),
    ("C21", "Tensión baja o extensión inadecuada", "Instalación",
     "Extensiones largas o finas, o generadores chicos, entregan menos tensión. El motor "
     "pierde fuerza, se calienta y puede quemar el campo.",
     "Medir la tensión en el tomacorriente con la máquina trabajando."
     "|Usar extensiones de al menos 2,5 mm² y lo más cortas posible."
     "|En obra con generador, verificar que la potencia sea suficiente.",
     1, False, "cable", 0.6),
    ("C22", "Correa de transmisión cortada o gastada", "Correa",
     "En los cepillos el motor mueve el tambor de cuchillas con una correa dentada. Con el "
     "uso se estira, pierde dientes o se corta, y el motor gira en vacío.",
     "Retirar la tapa lateral de la correa."
     "|Revisar dientes faltantes, grietas o fibras sueltas."
     "|Limpiar las poleas de viruta y resina antes de colocar la nueva."
     "|Reemplazar por correa original del modelo y verificar que no quede floja.",
     1, False, "correa", 1.8),
    ("C23", "Cuchillas desafiladas o mal calibradas", "Cuchillas",
     "Cuchillas con filo gastado, mordidas por clavos o colocadas a distinta altura. El "
     "cepillo arranca la fibra y deja escalones.",
     "Desenchufar y revisar el filo de ambas cuchillas."
     "|Usar el calibre de ajuste para dejarlas a la misma altura respecto de la base trasera."
     "|Reemplazar o afilar siempre el par completo."
     "|Ajustar los tornillos de la placa de sujeción en forma pareja.",
     1, False, "cepillo", 1.6),
    ("C24", "Mecanismo de profundidad gastado", "Base delantera",
     "La perilla de profundidad y la base delantera tienen juego o el resorte perdió "
     "fuerza, y la medida cambia mientras se trabaja.",
     "Comprobar si la base delantera se mueve sin girar la perilla."
     "|Revisar resorte, rosca de la perilla y guías de la base."
     "|Reemplazar las piezas gastadas y recalibrar la escala.",
     2, True, "cepillo", 0.6),
]

# --------------------------------------------------------------------------
# Reglas síntoma → causa (peso 0–1)
# --------------------------------------------------------------------------
REGLAS = {
    "S01": {"C01": .9, "C05": .7, "C06": .7, "C04": .35, "C03": .3, "C14": .65, "C13": .55, "C15": .6},
    "S02": {"C06": .9, "C01": .6, "C05": .6, "C14": .75, "C02": .3},
    "S03": {"C03": .9, "C02": .8, "C01": .55},
    "S04": {"C03": .8, "C04": .8, "C12": .6, "C11": .5, "C15": .45},
    "S05": {"C11": .8, "C12": .8, "C07": .5, "C03": .5, "C08": .35, "C21": .55},
    "S06": {"C04": .9, "C03": .8, "C12": .5, "C15": .55},
    "S07": {"C21": .8, "C01": .5, "C03": .6, "C04": .5, "C12": .4, "C13": .65, "C02": .4},
    "S08": {"C04": .9, "C03": .7, "C06": .5},
    "S09": {"C16": .9, "C05": .6, "C15": .55},
    "S10": {"C07": .9, "C08": .8, "C22": .35},
    "S11": {"C07": .8, "C08": .4, "C20": .6, "C10": .4},
    "S12": {"C09": .95, "C08": .3},
    "S13": {"C10": .95},
    "S14": {"C18": .9, "C12": .3, "C08": .3},
    "S15": {"C05": .9, "C11": .4},
    "S16": {"C17": .95, "C15": .3},
    "S17": {"C13": .95, "C12": .25},
    "S18": {"C13": .8, "C14": .7},
    "S19": {"C13": .7, "C12": .7, "C15": .4},
    "S20": {"C12": .6, "C21": .5, "C01": .5, "C08": .3, "C15": .3},
    "S21": {"C20": .95, "C07": .4},
    "S22": {"C19": .95, "C07": .3},
    "S23": {"C22": .95, "C08": .25},
    "S24": {"C23": .9, "C24": .35, "C07": .35},
    "S25": {"C24": .9, "C23": .2},
}

SUCURSALES = {
    # nombre: (peso de volumen, días extra por logística de repuestos)
    "Asunción": (1.0, 0),
    "San Lorenzo": (0.55, 1),
    "Luque": (0.4, 1),
    "Ciudad del Este": (0.6, 4),
    "Encarnación": (0.45, 3),
}

INICIO = date(2024, 11, 1)
HOY = date(2026, 10, 23)


def _casos_simulados(herramientas, causas, rng: random.Random):
    tiene = lambda h, r: (not r) or r in h.rasgos.split(",")
    sucursales = list(SUCURSALES)
    pesos_suc = [SUCURSALES[s][0] for s in sucursales]
    casos, n = [], 0

    mes = INICIO
    while mes <= HOY:
        idx = (mes.year - INICIO.year) * 12 + mes.month - INICIO.month
        # temporada fuerte de obra marzo–mayo y septiembre–noviembre + crecimiento
        temporada = 1 + 0.22 * math.sin((mes.month - 1.5) / 12 * 4 * math.pi)
        base = 58 * temporada * (1 + 0.013 * idx)
        sig = date(mes.year + mes.month // 12, mes.month % 12 + 1, 1)
        dias_mes = (min(sig, HOY + timedelta(days=1)) - mes).days

        for h, vol, precio in herramientas:
            cantidad = max(0, int(rng.gauss(base * vol / 9.0, 2) * dias_mes / 30))
            aplicables = [c for c in causas if tiene(h, c[0].requiere)]
            pesos = [c[1] for c in aplicables]
            for _ in range(cantidad):
                causa = rng.choices(aplicables, pesos)[0][0]
                suc = rng.choices(sucursales, pesos_suc)[0]
                ingreso = mes + timedelta(days=rng.randrange(dias_mes))
                n += 1

                if not causa.cubre_garantia:
                    resultado = "Rechazado" if rng.random() < .82 else "Reparado"
                elif causa.dificultad == 3 and rng.random() < .22:
                    resultado = "Reemplazo"
                elif causa.codigo == "C13" and rng.random() < .55:
                    resultado = "Reemplazo"
                else:
                    resultado = "Reparado"

                if resultado == "Rechazado":
                    dias = rng.randint(1, 4)
                    costo = 0
                elif resultado == "Reemplazo":
                    dias = rng.randint(3, 9) + SUCURSALES[suc][1]
                    costo = precio if causa.codigo != "C13" else 640_000
                else:
                    mediana = {1: 3, 2: 6, 3: 11}[causa.dificultad]
                    dias = int(rng.lognormvariate(math.log(mediana), .45)) + SUCURSALES[suc][1]
                    if causa.dificultad == 3 and rng.random() < .12:
                        dias += rng.randint(15, 35)          # repuesto importado
                    costo = {1: 70_000, 2: 210_000, 3: 520_000}[causa.dificultad]
                    costo = int(costo * rng.uniform(.75, 1.4) / 1000) * 1000

                cierre = ingreso + timedelta(days=max(1, dias))
                if cierre > HOY:
                    cierre, resultado = None, "En proceso"

                casos.append(CasoGarantia(
                    numero=f"GT-{ingreso:%y%m}-{n:05d}",
                    herramienta_id=h.id, causa_id=causa.id, sucursal=suc,
                    fecha_ingreso=ingreso, fecha_cierre=cierre,
                    resultado=resultado, costo_gs=costo,
                ))
        mes = sig
    return casos


def hay_datos_reales() -> bool:
    """True si ya se cargaron recepciones: en ese caso no se borra nada."""
    from sqlalchemy import inspect, text
    if "orden_servicio" not in inspect(engine).get_table_names():
        return False
    with engine.connect() as c:
        return c.execute(text("SELECT COUNT(*) FROM orden_servicio")).scalar() > 0


def seed():
    if hay_datos_reales() and "--forzar" not in sys.argv:
        print("Hay órdenes de recepción cargadas. seed.py borraría todo, así que no se hizo nada.\n"
              "Si de verdad querés empezar de cero: python seed.py --forzar")
        return
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rng = random.Random(1958)

    with SessionLocal() as s:
        herr = []
        for slug, nombre, modelo, linea, pot, rasgos, vol, precio in HERRAMIENTAS:
            h = Herramienta(slug=slug, nombre=nombre, modelo=modelo, linea=linea,
                            potencia=pot, rasgos=rasgos)
            s.add(h)
            herr.append((h, vol, precio))

        sint = {}
        for cod, texto, grupo, req in SINTOMAS:
            sint[cod] = Sintoma(codigo=cod, texto=texto, grupo=grupo, requiere=req)
            s.add(sint[cod])

        caus = {}
        frec = []
        for cod, tit, comp, expl, sol, dif, cubre, req, f in CAUSAS:
            caus[cod] = Causa(codigo=cod, titulo=tit, componente=comp, explicacion=expl,
                              solucion=sol, dificultad=dif, cubre_garantia=cubre, requiere=req)
            s.add(caus[cod])
            frec.append((caus[cod], f))
        s.flush()

        for scod, causas in REGLAS.items():
            for ccod, peso in causas.items():
                s.add(Regla(sintoma_id=sint[scod].id, causa_id=caus[ccod].id, peso=peso))

        casos = _casos_simulados(herr, frec, rng)
        s.add_all(casos)
        s.commit()
        print(f"OK: {len(herr)} herramientas, {len(sint)} síntomas, {len(caus)} causas, "
              f"{sum(len(v) for v in REGLAS.values())} reglas, {len(casos)} casos simulados.")


if __name__ == "__main__":
    seed()
