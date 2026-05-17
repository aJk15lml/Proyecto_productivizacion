"""
Descarga de datos NUMBAT (TfL) para el proyecto de aglomeración.

Estrategia N1:
- Años objetivo: 2017, 2019, 2023, 2024.
- Tipos de día publicados (varían por año, ver TIPOS_DIA_POR_ANIO):
  · 2017: MTT, SAT, SUN (3 archivos)
  · 2019: MTT, FRI, SAT, SUN (4 archivos)
  · 2023, 2024: MON, TWT, FRI, SAT, SUN (5 archivos cada uno)
- Además bajamos los archivos de definiciones disponibles para 2019
  y 2024, que sirven como diccionario de columnas y mapeo de estaciones.
- Los archivos se guardan en data/raw/<año>/.
- El script es idempotente: si un archivo ya existe y es válido, lo salta.

Notas:
- TfL cambió la capitalización del sufijo a partir de 2023:
    2017, 2019 → "_Outputs.xlsx" (O mayúscula)
    2023, 2024 → "_outputs.xlsx" (o minúscula)
- TfL separa el lunes (MON) de Tue-Wed-Thu (TWT) desde 2023 para
  reflejar que el lunes se comporta como un "día semi-festivo" en
  la era post-COVID. En el preprocesado habrá que decidir si:
    a) Tratamos MON y TWT como categorías distintas (más granularidad).
    b) Las fusionamos en un MTT común (consistencia con 2017/2019).

Uso:
    python src/descarga.py

Si alguna URL falla con 404, abrir https://crowding.data.tfl.gov.uk/ en el
navegador, buscar el archivo del año correspondiente, copiar su URL y
actualizar el diccionario URLS de abajo.
"""

from __future__ import annotations

import sys
import time
import urllib.parse
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# Carpeta base del proyecto (un nivel por encima de src/).
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_DATOS = RAIZ_PROYECTO / "data" / "raw"

# Patrón de URL de NUMBAT (verificado mayo 2026 con capturas del portal):
#
#   https://crowding.data.tfl.gov.uk/NUMBAT/NUMBAT <AÑO>/NBT<AA><TIPO><SUFIJO>
#
# OJO con dos detalles que cambian con el tiempo:
#
# 1) Tipos de día publicados por año:
#    - 2017: solo MTT, SAT, SUN (no hay FRI separado).
#    - 2019: MTT, FRI, SAT, SUN.
#    - 2023+: MON, TWT (Tue-Wed-Thu), FRI, SAT, SUN — separan el
#      lunes post-COVID por su patrón distinto (más WFH).
#
# 2) Capitalización del sufijo:
#    - 2017, 2019: "_Outputs.xlsx" (O MAYÚSCULA)
#    - 2023, 2024: "_outputs.xlsx" (o minúscula)
#
# Si TfL vuelve a cambiar la convención, ajustar TIPOS_DIA_POR_ANIO,
# SUFIJO_POR_ANIO o DEFINICIONES_POR_ANIO según corresponda.

ANIOS_OBJETIVO = [2017, 2019, 2023, 2024]

TIPOS_DIA_POR_ANIO: dict[int, list[str]] = {
    2017: ["MTT", "SAT", "SUN"],
    2019: ["MTT", "FRI", "SAT", "SUN"],
    2023: ["MON", "TWT", "FRI", "SAT", "SUN"],
    2024: ["MON", "TWT", "FRI", "SAT", "SUN"],
}

SUFIJO_POR_ANIO: dict[int, str] = {
    2017: "_Outputs.xlsx",
    2019: "_Outputs.xlsx",
    2023: "_outputs.xlsx",
    2024: "_outputs.xlsx",
}

# Archivos de definiciones / metadatos por año (opcionales pero útiles
# para entender qué significa cada columna y código de estación).
# Si fallan, el script lo registra como [OPCIONAL FALLIDO] y sigue.
DEFINICIONES_POR_ANIO: dict[int, str] = {
    2019: "NBT19_Definitions_Published.xlsx",
    2024: "PTSP Oasis for NUMBAT definitions.xlsx",
}

BASE_NUMBAT = "https://crowding.data.tfl.gov.uk/NUMBAT"


def url_numbat(anio: int, nombre_archivo: str) -> str:
    """Construye la URL canónica de un archivo dentro de NUMBAT <año>/."""
    carpeta = urllib.parse.quote(f"NUMBAT {anio}")
    archivo = urllib.parse.quote(nombre_archivo)
    return f"{BASE_NUMBAT}/{carpeta}/{archivo}"


def construir_urls_dia() -> dict[int, dict[str, tuple[str, str]]]:
    """
    Devuelve {año: {tipo_dia: (nombre_archivo, url)}} con los tipos de
    día que efectivamente se publican ese año.
    """
    resultado: dict[int, dict[str, tuple[str, str]]] = {}
    for anio in ANIOS_OBJETIVO:
        resultado[anio] = {}
        for tipo in TIPOS_DIA_POR_ANIO[anio]:
            nombre = f"NBT{str(anio)[2:]}{tipo}{SUFIJO_POR_ANIO[anio]}"
            resultado[anio][tipo] = (nombre, url_numbat(anio, nombre))
    return resultado


URLS: dict[int, dict[str, tuple[str, str]]] = construir_urls_dia()

# Tamaño mínimo razonable de un .xlsx de NUMBAT (en bytes).
# Sirve como sanity-check: si lo descargado es mucho más pequeño,
# probablemente sea un HTML de error, no un Excel.
TAMANO_MINIMO_VALIDO = 100_000  # 100 KB

# Cabeceras educadas: identificarse como navegador genérico evita algunos
# WAF demasiado celosos. NO scraping; solo descarga directa pública.
CABECERAS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ProyectoProductivizacion/1.0; "
        "+contacto: estudiante)"
    ),
}

REINTENTOS_MAX = 3
SEGUNDOS_ENTRE_REINTENTOS = 5


# ---------------------------------------------------------------------------
# Lógica
# ---------------------------------------------------------------------------


def es_archivo_valido(ruta: Path) -> bool:
    """Comprueba que un archivo existe y tiene tamaño razonable."""
    if not ruta.is_file():
        return False
    return ruta.stat().st_size >= TAMANO_MINIMO_VALIDO


def descargar_archivo(url: str, destino: Path) -> bool:
    """
    Descarga `url` a `destino`. Devuelve True si éxito, False si falla.
    Idempotente: si el archivo ya existe y es válido, no descarga.
    """
    if es_archivo_valido(destino):
        print(f"  [OK ya existe]  {destino.name}")
        return True

    destino.parent.mkdir(parents=True, exist_ok=True)

    for intento in range(1, REINTENTOS_MAX + 1):
        try:
            print(f"  Descargando    {destino.name}  (intento {intento})")
            respuesta = requests.get(
                url,
                headers=CABECERAS,
                stream=True,
                timeout=60,
            )
            if respuesta.status_code == 404:
                print(f"  [404 NO EXISTE] {url}")
                return False
            respuesta.raise_for_status()

            with open(destino, "wb") as f:
                for chunk in respuesta.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)

            if es_archivo_valido(destino):
                tam_mb = destino.stat().st_size / (1024 * 1024)
                print(f"  [OK descargado] {destino.name}  ({tam_mb:.1f} MB)")
                return True

            # Tamaño sospechosamente bajo: probable página de error
            print(
                f"  [SOSPECHOSO] {destino.name} pesa solo "
                f"{destino.stat().st_size} bytes. Borrando."
            )
            destino.unlink(missing_ok=True)

        except requests.RequestException as exc:
            print(f"  [ERROR red] {exc}")

        if intento < REINTENTOS_MAX:
            time.sleep(SEGUNDOS_ENTRE_REINTENTOS)

    return False


def main() -> int:
    print(f"Carpeta destino: {CARPETA_DATOS}")
    print(f"Años a descargar: {sorted(URLS.keys())}\n")

    descargados = 0
    fallidos: list[str] = []
    opcionales_fallidos: list[str] = []

    for anio, tipos in URLS.items():
        print(f"\n=== AÑO {anio} ===")
        carpeta_anio = CARPETA_DATOS / str(anio)

        # 1) Archivos principales (tipos de día)
        for tipo_dia, (nombre_archivo, url) in tipos.items():
            destino = carpeta_anio / nombre_archivo
            if descargar_archivo(url, destino):
                descargados += 1
            else:
                fallidos.append(f"{anio}/{tipo_dia} -> {url}")

        # 2) Archivo de definiciones (si existe ese año)
        if anio in DEFINICIONES_POR_ANIO:
            nombre_def = DEFINICIONES_POR_ANIO[anio]
            url_def = url_numbat(anio, nombre_def)
            destino_def = carpeta_anio / nombre_def
            print(f"  [OPCIONAL] Definiciones {anio}: {nombre_def}")
            if descargar_archivo(url_def, destino_def):
                descargados += 1
            else:
                opcionales_fallidos.append(f"{anio}/definiciones -> {url_def}")

    print("\n" + "=" * 60)
    print(
        f"Resumen: {descargados} archivos OK, {len(fallidos)} fallidos "
        f"(+ {len(opcionales_fallidos)} opcionales fallidos)."
    )
    if fallidos:
        print("\nArchivos PRINCIPALES fallidos (hay que arreglarlos):")
        for f in fallidos:
            print(f"  - {f}")
        print(
            "\nQué hacer: abrir https://crowding.data.tfl.gov.uk/ "
            "en el navegador, localizar el archivo correspondiente,\n"
            "copiar su URL real y actualizar el diccionario URLS en "
            "src/descarga.py."
        )
        return 1

    if opcionales_fallidos:
        print("\nArchivos OPCIONALES fallidos (no bloquean, solo info):")
        for f in opcionales_fallidos:
            print(f"  - {f}")

    print("\nTodo OK. Datos disponibles en data/raw/<año>/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
