# Banco de Pruebas

Asistente de diagnóstico de fallas y tablero de garantías para herramientas eléctricas
de la línea Makita. Proyecto de portafolio. No está afiliado a Makita Corporation, y
todos los casos de garantía son **simulados**.

## Módulos

| Ruta | Qué hace |
|---|---|
| `/` | Portada |
| `/recepcion` | Ingreso de equipos: cliente (CI/RUC), modelo + serie, celular, relato del cliente y accesorios. Genera la orden `OS-AA-NNNNN` con sticker y código de barras |
| `/recepcion/<numero>` | Ficha de la orden: estado, historial del equipo, imprimir sticker, diagnosticar |
| `/diagnostico` | Elegís la herramienta, marcás síntomas y recibís las causas probables con pasos de revisión |
| `/tablero` | KPIs, casos por mes, fallas por modelo, causas, tiempos por sucursal, matriz herramienta × causa y hallazgos |
| `/api/herramientas/<slug>/sintomas` | Síntomas que aplican a esa herramienta (JSON) |
| `POST /api/diagnostico` | `{"herramienta": "amoladora-115", "sintomas": ["S03","S04"]}` |
| `/api/tablero?desde=2025-01&hasta=2025-12&sucursal=Luque&herramienta=rotomartillo` | Indicadores calculados con Pandas |

## Stack

- **Python + Flask** para las rutas y la API
- **SQLAlchemy 2** sobre **PostgreSQL** (o SQLite para probar sin instalar nada)
- **Pandas** para el análisis del tablero (`analytics.py`)
- HTML/CSS/JS sin frameworks; los gráficos son SVG/HTML propios, con animaciones CSS

## Cómo decide el diagnóstico (`diagnostico.py`)

1. Cada regla une un síntoma con una causa y tiene un peso de 0 a 1 (`seed.py → REGLAS`).
2. Los pesos de los síntomas marcados se combinan con un O ruidoso: `1 − Π(1 − peso)`.
3. Ese valor se ajusta con la frecuencia de la causa en los casos de garantía de la
   misma herramienta (25 % del puntaje).
4. Solo se usan síntomas y causas que aplican a la herramienta (rasgos como `carbones`,
   `bateria`, `golpe`, `freno`…). Así, una herramienta brushless nunca sugiere carbones.

Cada consulta queda guardada en la tabla `consulta`.

## Instalación

```bash
pip install -r requirements.txt
python seed.py      # crea las tablas y carga la base de conocimiento + datos simulados
python app.py       # http://localhost:5000
```

`seed.py` borra y recrea todo, por eso **no corre si ya hay órdenes de recepción cargadas**
(hay que pasarle `--forzar` a propósito).

Sin `DATABASE_URL` usa `banco.db` (SQLite). Para usar PostgreSQL:

```bash
createdb banco_pruebas
set DATABASE_URL=postgresql+psycopg://postgres:TU_CLAVE@localhost:5432/banco_pruebas
python seed.py
python app.py
```

(En PowerShell: `$env:DATABASE_URL = "postgresql+psycopg://..."`.)

## Modelo de datos

```
herramienta ─┐
             ├─< caso_garantia >── causa ──< regla >── sintoma
             └─< consulta
```

## Ideas para seguir

- Login para técnicos y carga de casos reales anonimizados
- Exportar el informe de diagnóstico a PDF
- Pronóstico de demanda de repuestos por mes
