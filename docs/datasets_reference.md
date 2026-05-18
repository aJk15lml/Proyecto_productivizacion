# Referencia de datasets — NUMBAT y PTSP Oasis (TfL)

> Documento fuente para NotebookLM. Resume la información clave extraída
> de los archivos oficiales de TfL que acompañan al proyecto.
> Última actualización: 18 de mayo de 2026.

---

## Descripción oficial del dataset (palabras de TfL)

> *Transport for London (TfL) produces the NUMBAT dataset to provide statistics on usage and travel patterns on TfL railway services (since 2016). This detailed dataset can be used to assess train service provision, demand profiles and customer experience, as well as service planning and performance measurement.*

### Cobertura

> *The dataset represents the travel demand on a typical autumn Monday, Tuesday to Thursday, Friday, Saturday and Sunday at all stations and lines of the London Underground, London Overground, Docklands Light Railway and Elizabeth Line. Data covers every 15-minute period throughout the traffic day and assumes a full train service operated as scheduled.*

> *A typical day represents 0500-0459 for each daytype in autumn each year. Data is collected for each weekday, Saturday and Sunday in each autumn, with days affected by major disruptions, events and closures excluded.*

### Método

> *NUMBAT uses ticketing data from smartcards and gateline entry/exit totals for each station. It estimates the route choice of each journey and then assigns flows to lines and trains.*

### Confianza de los datos por hoja (según TfL)

- **`Station_Entries` / `Station_Exits`**: alta confianza, son flujos directos de las puertas con torniquete.
- **`Station_Boarders` / `Station_Alighters`**: alta en estaciones no-intercambio, media en intercambio.
- **`Station_Flows`**: media en intercambio (es estimado), precaución con flujos a/desde servicios no-TfL.
- **`Link_Loads`** (demanda dentro de los trenes entre andenes): alta en líneas sin intercambios; media en rutas que comparten servicio con líneas no-TfL.
- **`Link_Frequencies`**: alta confianza, viene directamente del horario.
- **`Line_Boarders`**: suma de boarders por línea.

---

## Estructura de cada archivo NUMBAT (`NBT<año><día_tipo>_outputs.xlsx`)

Cada Excel contiene **10 hojas**:

| Hoja | Contenido |
|------|-----------|
| `_Cover` | Documentación, contacto, fechas, notas de confianza. |
| `LineLookUp` | Mapeo de códigos de línea antiguos a nuevos (Overground rebrand 2024). |
| `Link_Loads` | Pasajeros dentro de los trenes entre cada par de estaciones adyacentes. |
| `Link_Frequencies` | Trenes por hora en cada tramo. |
| `Line_Boarders` | Pasajeros que abordan por línea. |
| `Station_Flows` | Flujos internos en cada estación (entre andenes / accesos). |
| `Station_Entries` | **Hoja usada por el proyecto.** Pasajeros entrando por las puertas en cada franja de 15 min. |
| `Station_Exits` | Pasajeros saliendo por las puertas. |
| `Station_Boarders` | Pasajeros que suben a trenes en esa estación (incluye intercambios). |
| `Station_Alighters` | Pasajeros que se bajan de trenes en esa estación. |

### Estructura interna de `Station_Entries`

Tres filas de cabecera apiladas:

- Fila 0: etiquetas-paraguas (`Station Entries`, `hour (hr)`).
- Fila 1: sub-etiquetas con número de hora (5..28) e índice de quarter-hour (21..116).
- Fila 2: **nombres reales** de columna.

**Columnas reales** (107 en total):

- 10 columnas de metadatos: `NLC`, `ASC`, `Station`, `Fare Zone`, `Total`, `Early`, `AM Peak`, `Midday`, `PM Peak`, `Evening`, `Late`.
- 96 columnas de franjas de 15 min en formato `HHMM-HHMM`: desde `0500-0515` hasta `0445-0500` (ciclo operativo 05:00 → 04:59 del día siguiente).

Una fila por estación. Hay 471 filas por archivo, de las cuales 39 son estaciones de Tramlink u otras no medidas (todas a cero), y 432 son válidas.

---

## Modos (hoja `Modes` del PTSP Oasis)

Nueve modos catalogados; solo cuatro son rail y TfL:

| Código | Sigla | Nombre | TfL | Rail | Medido en NUMBAT |
|--------|-------|--------|-----|------|------------------|
| `u` | LU | London Underground | Sí | Sí | Sí |
| `o` | LO | London Overground | Sí | Sí | Sí |
| `e` | EZL | Elizabeth Line | Sí | Sí | Sí |
| `d` | DLR | Docklands Light Railway | Sí | Sí | Sí |
| `r` | NR | National Rail | **No** | Sí | No |
| `t` | TRM | London Trams (Tramlink) | Sí | Sí | **No** (listado pero a cero) |
| `b` | BUS | London Buses | Sí | No | No |
| `c` | EAL | Emirates Air Line | Sí | No | No |
| `f` | FRY | Ferry | No | No | No |

---

## Líneas (hoja `Lines` del PTSP Oasis)

44 líneas catalogadas. Las relevantes para el modelo (TfL rail):

### Tube (London Underground)

| Código nuevo | Nombre | Mode |
|--------------|--------|------|
| `BAK` | Bakerloo | u |
| `CEN` | Central | u |
| `DIS` | District | u |
| `HAM` | Hammersmith & City / Circle (combinadas) | u |
| `JUB` | Jubilee | u |
| `MET` | Metropolitan | u |
| `NOR` | Northern | u |
| `PIC` | Piccadilly | u |
| `VIC` | Victoria | u |
| `WAC` | Waterloo & City (antes `WAT`) | u |

### London Overground (rebautizado en 2024)

| Código nuevo | Nombre nuevo | Código antiguo | Mode |
|--------------|--------------|----------------|------|
| `ELL` | Windrush | `LOE` | o |
| `GOB` | Suffragette | `LOG` | o |
| `NLL` | Mildmay | `LON` | o |
| `URL` | Liberty | `LOR` | o |
| `WEL` | Lioness | `LOW` | o |
| `WAG` | Weaver | `LOA` | o |

### Otros TfL rail

| Código | Nombre | Mode |
|--------|--------|------|
| `EZL` | Elizabeth Line | e |
| `DLR` | DLR | d |
| `TRM` | London Trams (Tramlink) | t |

### National Rail (no TfL)

19 líneas con prefijo `R*` (Chiltern, Great Eastern, Great Western, South Western, Southeastern, Southern, etc.). El proyecto las **ignora** para el cálculo de `num_lines`.

---

## Hojas de metadata por estación (PTSP Oasis)

### `Stations` (970 filas)

Catálogo maestro con metadatos por estación. Columnas usadas por el proyecto:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `MasterNLC` | int | National Location Code (identificador nacional). |
| `MasterASC` | str | Código interno TfL (sufijo indica modo). |
| `UniqueStationName` | str | Nombre legible canónico. |
| `InnerFareZone` | int | Zona tarifaria interior (1 = centro, 9 = extrarradio). |
| `OuterFareZone` | int | Zona tarifaria exterior (igual o mayor que la interior; difiere en estaciones frontera). |
| `FullyGated` | str | `Yes` / `No` / `<año>` — indica si la estación tiene torniquetes completos. |
| `Hub` | str | Si forma parte de un hub. |
| `Active` | bool | Si está operativa. |
| `TfL` | bool | Si está gestionada por TfL. |
| `Latitude`, `Longitude` | float | Geolocalización. |

### `Stn-Line` (970 filas × 48 columnas)

Matriz booleana **estación × línea**. Cada fila es una estación, cada columna una de las 44 líneas + identificadores. `True` si la línea sirve a esa estación.

Permite calcular `num_lines` por estación: suma de columnas True para las líneas TfL.

### `Stn-Mode` (970 filas, con 1 duplicado que se deduplica)

Matriz booleana **estación × modo**. Una columna por modo (`u`, `d`, `t`, `o`, `e`, `r`, `rr`, `or`, `er`).

Permite calcular `num_modes` por estación: suma de columnas True para los modos TfL rail (`u`, `d`, `o`, `e`).

**Detalle conocido:** NLC 866 (West India Quay) aparece duplicado en esta hoja. El script de preprocesado del proyecto lo elimina con `drop_duplicates`.

### `OSIs` (161 filas)

*Out of Station Interchanges*. Define los **complejos de transbordo** entre estaciones físicamente separadas pero vinculadas funcionalmente (sin salir del sistema). Ejemplo: el complejo `10601` agrupa Aldgate + Fenchurch Street + Tower Hill + Tower Gateway.

Útil para análisis avanzado de aglomeración en complejos completos. **No se usa en el MVP**, pero está disponible para Nivel 4.

### `Stn-Naptan` (717 filas)

Mapeo `MasterNLC` ↔ `PrimaryNaptanStopArea` (identificador estándar nacional UK). Útil para cruzar con datos de buses u otros datasets del transporte público británico.

---

## Glosario de columnas y campos clave

| Término | Definición |
|---------|------------|
| **NLC** | *National Location Code.* Identificador numérico nacional de cada estación de raíles en Reino Unido. Ejemplo: 502 = Aldgate. |
| **ASC** | Código interno de TfL. String corto con sufijo indicando modo: `u` = Underground, `d` = DLR, `r` = Rail (Overground / EZL / NR), `t` = Tram. Ejemplo: `ALDu` = Aldgate Underground. |
| **MASC / MNLC** | "Master" ASC / NLC. Identificadores canónicos cuando una estación tiene varias representaciones. |
| **NAPTAN** | Identificador nacional estándar de paradas/estaciones de transporte público en Reino Unido. |
| **Fare Zone** | Zona tarifaria de TfL. 1 = centro, 9 = extrarradio. Algunas estaciones son frontera y aparecen como `"2/3"`, `"3/4"`. |
| **MTT** | *Monday-Thursday Typical.* Categoría de día tipo usada hasta 2019. |
| **MON** | *Monday Typical.* Desde 2023, el lunes se separa por ser atípico post-COVID (más teletrabajo). |
| **TWT** | *Tuesday-Wednesday-Thursday Typical.* Desde 2023, el laborable "puro". |
| **FRI** | *Friday Typical.* Patrón distinto: menos commuting matinal, más ocio nocturno. |
| **SAT / SUN** | Sábado / Domingo. |
| **AM Peak** | Aprox. 07:00–10:00. |
| **PM Peak** | Aprox. 16:00–19:00. |
| **Midday / Inter-peak** | Aprox. 10:00–16:00. |
| **Quarter-hour slot / qhr** | Franja de 15 minutos. NUMBAT tiene 96 al día. Formato: `HHMM-HHMM`. |
| **OSI** | *Out of Station Interchange.* Transbordo entre estaciones físicamente separadas pero vinculadas. |
| **FullyGated** | Estación con torniquetes completos. En las no-fully-gated, los conteos de entry/exit son menos precisos. |
| **Hub** | Estación clasificada como concentrador (King's Cross, Waterloo, etc.). |
| **Boarder** | Pasajero que sube a un tren en esa estación (incluye los que ya estaban dentro y cambian de línea). |
| **Alighter** | Pasajero que baja de un tren en esa estación. |
| **Entry** | Pasajero que **entra** desde la calle a la estación. Lo que usa el proyecto. |
| **Exit** | Pasajero que sale de la estación a la calle. |
