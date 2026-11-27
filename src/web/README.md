# Interfaz web de supervisión

**Estado:** C1, boceto base. Muestra el ciclo de una pieza a partir de la variable de estado del robot (`estado_g4`), con simulador y escenarios de prueba para trabajar sin robot.

Muestra en el navegador lo que pasa en la celda. Es **solo de lectura**: desde la web no se envían órdenes al robot.

> **Alcance del boceto.** Por ahora **se ignora el protocolo de comunicación cámara–robot** (mensajes de [`docs/contratos.md`](../../docs/contratos.md), conductos, TLS y servidor intermedio). La demo solo sigue los **cambios de estado** de `estado_g4` y dibuja el ciclo a partir de ellos. Cuando el servidor intermedio publique su estado, la web tomará de ahí los datos en lugar de leer KukaVarProxy (ver *Pendiente*).

## Arranque rápido

Desde la raíz del repositorio, con Python 3.7 o superior y sin dependencias externas:

```bat
python -m src.web                                   :: simulador, ciclos al azar sin fin
python -m src.web --escenario buena                 :: una pieza buena: 0→1→2→1→2→1→3→0
python -m src.web --escenario mala                  :: una pieza mala:  0→1→2→1→2→1→4→0
python -m src.web --escenario ambas                 :: pieza 1 buena y pieza 2 mala
python -m src.web --escenario ambas --una-vez       :: se reproduce una vez y se queda quieto
python -m src.web --modo kvp                        :: robot real, [robot] kvp_host / kvp_port
```

Abrir `http://localhost:<puerto>` (por defecto el `[web] port` de `config/ejemplo.ini`). `?movimiento=0` en la URL quita la interpolación del brazo, que entonces salta entre estaciones.

> **Puerto 8080 y LabVIEW.** En los PC con National Instruments LabVIEW, su *Application Web Server* ya ocupa el 8080 y Python falla con `WinError 10013`. Basta con `--port 8090` (o cualquier puerto libre). Para ver quién usa un puerto: `netstat -ano | findstr :8080`.

`--bind` elige la IP de escucha: `0.0.0.0` todas las interfaces, una IP concreta solo esa red, `127.0.0.1` solo este PC. No cambia la IP del equipo, solo dónde escucha la web.

## Qué muestra

- **Vista superior (X/Y) y vista frontal (X/Z)** de un brazo de dos eslabones. Las dos vistas salen de la misma pose 3D, así que juntas dan la posición del robot sin un motor 3D.
- **Ciclo:** el brazo va vacío a la cinta y coge la pieza (0), la lleva delante de la cámara (1), la gira 15° en cada petición de la cámara (2, la cámara parpadea), y la deja en la pila buena (3, verde) o en la de rechazo (4, rojo).
- **Panel:** valor y nombre del estado, tiempo en el estado, pasos 0–4, contadores (ciclos, buenas, malas, rendimiento, tiempo de ciclo, giros de la pieza) y lista de eventos.
- **Avisos:** barra roja si se cae el enlace con el robot o con el servidor web, y evento de aviso ante transiciones que no deberían pasar (p. ej. `0 → 3`) o valores fuera de 0–4.
- Tema oscuro y claro con criterio ISA-101: grises en operación normal y color solo para estados. Sin fuentes web ni frameworks.

## Variable de estado

Según la tabla de la tarea 1.6 (`docs/variables-krl.md`):

| Valor | Significado | En la web |
|---|---|---|
| 0 | Reposo, el robot recoge la pieza | Brazo a la cinta, coge la pieza |
| 1 | Pieza delante de la cámara | Brazo en la cámara, cámara armada (azul) |
| 2 | Girar 15° el eje 6, luego vuelve a 1 | La cámara parpadea y la pieza gira 15° |
| 3 | Pieza buena, luego vuelve a 0 | Pieza verde a la pila OK |
| 4 | Pieza mala, luego vuelve a 0 | Pieza roja a la pila de rechazo |

El nombre sale de `[robot] var_state` si existe y si no, de `estado_g4`. Se puede forzar con `--variable`.

## Fuentes de datos

| Modo | Para qué | Red |
|---|---|---|
| `sim` (por defecto) | demostración, ciclos con giros y resultado al azar | ninguna |
| `--escenario buena / mala / ambas` | prueba visual de un ciclo fijo | ninguna |
| `--modo kvp` | robot real por KukaVarProxy, **solo lectura** | controladora, TCP 7000 |

Un único hilo sondea la variable (cada `[robot] poll_ms`), haya los navegadores que haya, así que la carga sobre la controladora es constante.

## Rutas

| Ruta | Respuesta |
|---|---|
| `GET /`, `/estilos.css`, `/app.js` | ficheros de `interfaz/` |
| `GET /api/robot` | estado del ciclo, contadores y últimos eventos (JSON) |
| `POST /api/contadores/reiniciar` | pone a cero los contadores de la web (no toca el robot) |

## Pruebas

```bat
python -m unittest src.web.tests.test_ciclo -v
```

Comprueban las secuencias de pieza buena y mala, los contadores, el conteo de giros y los avisos sin usar la red. Las pruebas del protocolo de KukaVarProxy usan un proxy falso en `127.0.0.1`.

Para probar el camino completo del modo `kvp` sin robot, en dos terminales:

```bat
python -m src.web.tests.kvp_falso --escenario ambas
python -m src.web --modo kvp --kvp-host 127.0.0.1
```

Para leer la variable del robot real a mano: `python -m src.web.kvp_lectura <ip> estado_g4`.

## Estructura

```
src/web/
├── __init__.py
├── __main__.py        # arranque: python -m src.web --config config/ejemplo.ini
├── interfaz_web.py    # MonitorCelda (sondeo y transiciones) y servidor HTTP
├── kvp_lectura.py     # cliente de KukaVarProxy, solo lectura
├── simulador.py       # simulador de proceso y escenarios fijos
├── interfaz/          # página estática
│   ├── index.html
│   ├── estilos.css
│   └── app.js
├── tests/
│   ├── test_ciclo.py
│   └── kvp_falso.py   # KukaVarProxy falso
└── README.md
```

Usa las secciones que ya existen en `config/ejemplo.ini`: `[web]` (`bind`, `port`) y `[robot]` (`kvp_host`, `kvp_port`, `poll_ms`). No añade claves nuevas.

## Pendiente

1. **Datos desde el servidor intermedio.** Hoy la web lee `estado_g4` directamente por KukaVarProxy (solo lectura) para la demo. El diseño final toma los datos del servidor intermedio (`ROBOT_STATUS`, `ORDER_DONE`...), que es el único que ve los dos conductos. Se acuerda con la tarea 1.3 si la web va dentro de su proceso o aparte.
2. **Posición real del robot.** La pose del dibujo se deduce del estado (una estación por estado). Con el campo `position` de `ROBOT_STATUS` las vistas pueden mostrar la posición real. Solo cambia `ponerDestino()` en `app.js`.
3. **Geometría de la celda.** Las estaciones y las longitudes del brazo (`G` y `EST` en `app.js`) son provisionales. Hay que medirlas en el laboratorio.
4. **Pestañas previstas** (Estado de los conductos, Piezas, Métricas) y rutas `/api/estado`, `/api/piezas`, `/api/eventos`, cuando exista el protocolo.
5. **Contadores del robot.** Si `p_good_cnt` y `p_bad_cnt` pasan a ser globales (tarea 1.6), la web puede mostrarlos en lugar de contar ella las piezas.

## Preguntas abiertas

1. `web.bind = 0.0.0.0` publica la web en toda la red. Es solo de lectura, pero muestra datos de producción. ¿`127.0.0.1` por defecto, o acceso desde la red con algún control? Ojo: los PC del laboratorio tienen también interfaces en las redes de máquinas (192.168.x); con `--bind <IP del PC>` la web solo responde en la red de oficina.
2. ¿Cambiamos `[web] port` de `config/ejemplo.ini` a otro puerto (p. ej. 8090) para evitar el choque con LabVIEW en todos los PC?
3. ¿Cuántas piezas y eventos se guardan para la web, y se guardan en disco o solo en memoria? Hoy, 60 eventos en memoria.
