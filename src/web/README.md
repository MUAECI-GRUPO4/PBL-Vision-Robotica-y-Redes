# Interfaz web de supervisión

**Estado:** C0, solo estructura y diseño. Todavía no hay código.

Muestra en el navegador lo que pasa en el sistema: estado de los conductos, piezas clasificadas, estado del robot y errores. Es **solo de lectura**: desde la web no se envían órdenes al robot. Toma los datos del servidor intermedio, que es el único que ve los dos conductos.

```
pasarela-V ══conducto 1══╗
                          ╠═ servidor intermedio ── interfaz web ── navegador
pasarela-R ══conducto 2══╝
```

## Pestañas previstas

| Pestaña | Qué muestra | De qué mensajes sale |
|---|---|---|
| Estado | conducto 1 y 2 conectados o caídos, último latido, TLS sí o no | `HELLO`, `HEARTBEAT` |
| Piezas | tabla por identificador de pieza: texto, confianza, clase, rutina, resultado, miniatura | `PIECE_RESULT`, `ORDER`, `ORDER_DONE` |
| Robot | estado, paso, posición y tiempo transcurrido de la rutina en curso | `ROBOT_STATUS` |
| Eventos | errores y avisos con su pieza (`TIMEOUT`, `VERSION`...) | `ERROR` y eventos del servidor |
| Métricas | latencia de cada pieza por tramo y coste del handshake (R4) | marcas `ts` de los mensajes |

## Rutas previstas

| Ruta | Respuesta |
|---|---|
| `GET /` , `/estilos.css`, `/app.js` | ficheros de `interfaz/` |
| `GET /api/estado` | estado de los dos conductos |
| `GET /api/piezas` | últimas piezas con su resultado |
| `GET /api/piezas/<id>` | detalle de una pieza, con miniatura |
| `GET /api/robot` | último `ROBOT_STATUS` |
| `GET /api/eventos` | últimos eventos |

## Estructura prevista

```
src/web/
├── __init__.py
├── __main__.py        # arranque: python -m src.web --config config/ejemplo.ini
├── interfaz_web.py    # servidor HTTP y rutas /api
├── interfaz/          # página estática
│   ├── index.html
│   ├── estilos.css
│   └── app.js
└── README.md
```

Usa la sección `[web]` que ya existe en `config/ejemplo.ini` (`bind`, `port`).

## Preguntas abiertas

1. ¿La web corre dentro del proceso del servidor intermedio (lee directamente su estado y su lista de eventos) o como proceso aparte que se los pide? Se acuerda con el responsable de la tarea 1.3.
2. `web.bind = 0.0.0.0` publica la web en toda la red. Es solo de lectura, pero muestra datos de producción. ¿`127.0.0.1` por defecto, o acceso desde la red con algún control?
3. ¿Cuántas piezas y eventos se guardan para la web, y se guardan en disco o solo en memoria?
