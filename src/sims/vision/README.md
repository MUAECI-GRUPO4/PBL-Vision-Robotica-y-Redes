# Simulador de visión

**Estado:** C0, solo estructura y diseño. Todavía no hay código.

Sustituye a HALCON mientras el software de visión definitivo no esté listo, igual que el servidor de eco sustituía al robot en la práctica 3. Envía resultados de pieza a la [pasarela de visión](../../vision_gw/) con el mismo formato que usará HALCON, así que la pasarela no distingue si habla con el simulador o con el software real.

```
simulador de visión ──(TCP local, en claro)──▶ pasarela-V ══conducto 1══▶ servidor intermedio
```

## Qué hace

- Se conecta a la entrada local de la pasarela (`vision.local_host`, `vision.local_port`).
- Envía resultados (`text`, `confidence`, `class`, `region`, `thumb`) según el formato de `PIECE_RESULT` de [`docs/contratos.md`](../../../docs/contratos.md).
- Modos previstos:
  - **Periódico:** una pieza cada N segundos, con clases al azar.
  - **Manual:** una pieza cada vez que se pulsa una tecla, eligiendo la clase.
  - **Casos:** recorre una lista de casos de prueba y termina.

## Casos que debe poder generar

| Caso | Para probar |
|---|---|
| Clase `A` y `B` con confianza alta | el ciclo normal de una pieza |
| Confianza baja o texto vacío | que la pieza acaba en `REJECT` (R2) |
| Ráfaga de piezas seguidas | que no se pierden ni se mezclan identificadores |
| Mensaje mal formado (JSON no válido, campos que faltan) | que la pasarela lo registra y no se cae |
| Mensaje mayor que `max_message_bytes` | que se cierra la conexión y se registra (P1) |
| Cierre brusco de la conexión | que la pasarela detecta la caída y sigue aceptando |

## Estructura prevista

```
src/sims/vision/
├── __init__.py
├── __main__.py           # arranque: python -m src.sims.vision --config config/vision.ini
├── simulador.py          # SimuladorVision: conexión con la pasarela y modos de envío
└── README.md
```

La lista de casos y las miniaturas de ejemplo (imágenes JPEG pequeñas) se añadirán junto con el código; no se versionan imágenes reales del laboratorio.

## Preguntas abiertas

1. Si el formato de entrega de HALCON cambia (pregunta 1 de los contratos), el simulador cambia con él: debe imitar siempre lo que hará el software real.
2. ¿Hace falta un modo que hable directamente con el servidor por el conducto 1, saltándose la pasarela, para probar el servidor antes de que la pasarela esté lista?
