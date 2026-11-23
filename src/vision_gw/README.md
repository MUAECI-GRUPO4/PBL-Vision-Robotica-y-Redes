# Pasarela de visión (pasarela-V)

**Estado:** C0, solo estructura y diseño. Todavía no hay código.

Une el software de visión (HALCON en el PC de visión, o el [simulador](../sims/vision/) mientras no esté listo) con el servidor intermedio por el **conducto 1**. El formato de todos los mensajes es el de [`docs/contratos.md`](../../docs/contratos.md); esta carpeta no lo redefine.

```
HALCON / simulador ──(TCP local, en claro)──▶ pasarela-V ══TLS, conducto 1══▶ servidor intermedio
                                               (cliente)                       server.port_vision
```

## Qué hace

1. **Entrada local.** Escucha en `127.0.0.1` (solo dentro del PC de visión, tramo en claro S5) y recibe de HALCON el resultado de cada pieza: texto, confianza, clase, región y miniatura.
2. **Identifica la pieza.** Crea el identificador `P<AAAAMMDD>-<HHMMSS>-<nnn>` al recibir la captura (contratos, apartado 3) y lo pone en todos sus logs.
3. **Construye el sobre.** Añade `v`, `type`, `id`, `piece` y `ts`, y envía un `PIECE_RESULT`.
4. **Conducto 1.** Es **cliente** del servidor: conexión persistente, `HELLO` al conectar, `HEARTBEAT` cada `heartbeat_s`, espera del `ACK` de cada `PIECE_RESULT` y reconexión automática si el servidor cae.
5. **Seguridad.** En claro hasta el hito H3 (`tls.enabled = no`); después, TLS 1.3 con autenticación mutua y los certificados de [`src/pki`](../pki/).

La pasarela lee cada mensaje, porque tiene que crear el identificador de pieza y responder a `HELLO_ACK`, `ACK` y `ERROR`. La delimitación (longitud u32 + JSON) la da la librería común [`src/proto`](../proto/); aquí no se duplica.

## Estructura prevista

```
src/vision_gw/
├── __init__.py
├── __main__.py      # arranque: python -m src.vision_gw --config config/vision.ini
├── pasarela.py      # PasarelaVision: cliente del conducto 1, latidos, ACK y reconexión
├── entrada.py       # servidor local en claro que recibe los resultados de HALCON
├── pieza.py         # creación del identificador de pieza
└── README.md
```

Mismo patrón que `src/gw_robot` y `src/server`: paquete con `__main__.py` y configuración por `--config`.

## Configuración prevista

Se usarán las secciones comunes `[node]`, `[tls]` y `[protocol]` de `config/ejemplo.ini`. Hará falta una sección propia, que se añadirá a `config/ejemplo.ini` en el pull request del código (no en este):

| Clave propuesta | Para qué |
|---|---|
| `vision.local_host`, `vision.local_port` | dónde escucha la entrada local de HALCON |
| `vision.server_host` | dirección del servidor intermedio vista desde la zona de visión (el puerto es `server.port_vision`) |
| `vision.reconnect_s` | espera entre reintentos de conexión con el servidor |

## Preguntas abiertas

1. ¿Cómo entrega HALCON el resultado? Propuesta: TCP local con el mismo formato que `PIECE_RESULT` (contratos, pregunta 1). Se acuerda con Visión.
2. Si el servidor no está disponible, ¿qué se hace con los resultados que llegan? Propuesta: guardarlos en una cola pendiente de `ACK`, registrarlo y enviarlos al reconectar. Se acuerda en el grupo.
3. ¿Quién decide `REJECT` por confianza baja, HALCON o la pasarela? Si es la pasarela, el umbral irá en la configuración (R5).
