# Contratos de interfaz de PBL 1: protocolo de aplicación

**Estado:** borrador C0 de DL (tarea 1.1). Se acuerda en el grupo y con Visión y Robótica antes de implementar; después, nadie lo cambia sin avisar y reabrir el apartado en un pull request. Los diagramas llegan en C1.

## 1. Conexiones

```
cámaras ─GigE─ PC visión ─(claro)─ pasarela-V ══TLS, conducto 1══╗
                                                                  ╠═ servidor intermedio ══ interfaz web
robot KUKA ─KukaVarProxy :7000─(claro)─ pasarela-R ══TLS, conducto 2══╝
```

- Ambas pasarelas son **clientes TLS** y el servidor intermedio escucha en dos puertos (conducto 1 para visión, conducto 2 para robot). Así ninguna zona abre un puerto de entrada.
- Una **conexión persistente** por conducto, con latidos: se paga el handshake TLS una vez y no por pieza (se medirá en R4).
- Solo los tramos internos de cada zona van en claro (S5): cámaras a PC de visión y pasarela-R a KukaVarProxy.
- No se usan las funciones de C3 Bridge (control de programas, ficheros): solo variables de KukaVarProxy, para limitar lo que podría hacer un atacante desde la red.

## 2. Delimitación de mensajes (P1)

TCP entrega un flujo de bytes. Cada mensaje va así:

```
+---------------------+----------------------------------+
| longitud: u32 (BE)  | payload: JSON en UTF-8           |
+---------------------+----------------------------------+
```

- `longitud` es el tamaño del payload en bytes, en big-endian, sin contar los 4 bytes de la cabecera.
- Una longitud mayor que `max_message_bytes` cierra la conexión y se registra.
- Se elige longitud delante y no un separador porque el payload puede llevar cualquier carácter y no hay que escapar nada.
- Un mensaje puede llegar fragmentado o junto a otros: el receptor acumula bytes y extrae mensajes completos.

## 3. Sobre común de todos los mensajes

| Campo | Tipo | Significado |
|---|---|---|
| `v` | int | versión del protocolo (P6) |
| `type` | str | tipo de mensaje, ver apartado 4 |
| `id` | int | identificador del mensaje, creciente por emisor |
| `ref` | int | `id` del mensaje al que responde; solo en respuestas |
| `piece` | str | identificador de pieza (P3); en todos los mensajes que la afectan |
| `ts` | str | marca de tiempo ISO 8601 en UTC con milisegundos |
| `body` | objeto | contenido propio de cada tipo |

**Identificador de pieza:** `P<AAAAMMDD>-<HHMMSS>-<nnn>`, lo crea la pasarela de visión al capturar y viaja en todos los mensajes de esa pieza y en todos los logs (R3).

## 4. Tipos de mensaje (P2)

| Tipo | Sentido | Respuesta esperada |
|---|---|---|
| `HELLO` | pasarela a servidor, al conectar | `HELLO_ACK`, o `ERROR` con `VERSION` si la versión no es compatible (P6) |
| `HELLO_ACK` | servidor a pasarela | -- |
| `HEARTBEAT` | ambos sentidos, cada `heartbeat_s` | -- (el extremo se da por caído tras `missed_beats` sin recibir nada, P5) |
| `PIECE_RESULT` | visión a servidor | `ACK` |
| `ORDER` | servidor a pasarela-R | `ORDER_ACK` en menos de `ack_timeout_s` (P4) |
| `ORDER_ACK` | pasarela-R a servidor | -- |
| `ROBOT_STATUS` | pasarela-R a servidor | -- (al cambiar y cada segundo mientras `RUNNING`) |
| `ORDER_DONE` | pasarela-R a servidor | `ACK` |
| `ACK` | cualquiera | -- |
| `ERROR` | cualquiera | -- |

Ejemplos:

```json
{"v":1,"type":"HELLO","id":1,"ts":"2026-12-07T10:15:00.001Z","body":{"role":"vision","node":"pasarela_v"}}
```

```json
{"v":1,"type":"HELLO_ACK","id":1,"ref":1,"ts":"2026-12-07T10:15:00.020Z","body":{"heartbeat_s":1}}
```

```json
{"v":1,"type":"HEARTBEAT","id":2,"ts":"2026-12-07T10:15:01.001Z","body":{}}
```

```json
{"v":1,"type":"PIECE_RESULT","id":3,"piece":"P20261207-101530-001","ts":"2026-12-07T10:15:30.512Z","body":{"text":"AB-1234","confidence":0.97,"class":"B","region":[120,80,200,60],"thumb":"<JPEG en base64>"}}
```

```json
{"v":1,"type":"ACK","id":2,"ref":3,"piece":"P20261207-101530-001","ts":"2026-12-07T10:15:30.530Z","body":{}}
```

```json
{"v":1,"type":"ORDER","id":4,"piece":"P20261207-101530-001","ts":"2026-12-07T10:15:30.540Z","body":{"routine":"B"}}
```

```json
{"v":1,"type":"ORDER_ACK","id":5,"ref":4,"piece":"P20261207-101530-001","ts":"2026-12-07T10:15:30.700Z","body":{"accepted":true}}
```

```json
{"v":1,"type":"ROBOT_STATUS","id":6,"piece":"P20261207-101530-001","ts":"2026-12-07T10:15:31.700Z","body":{"state":"RUNNING","step":3,"position":[410.2,-35.0,220.5,0.0,90.0,0.0],"elapsed_ms":1000}}
```

```json
{"v":1,"type":"ORDER_DONE","id":7,"piece":"P20261207-101530-001","ts":"2026-12-07T10:15:42.100Z","body":{"result":"OK"}}
```

```json
{"v":1,"type":"ERROR","id":8,"ref":4,"piece":"P20261207-101530-001","ts":"2026-12-07T10:15:32.540Z","body":{"code":"TIMEOUT","msg":"el robot no confirmó la orden"}}
```

Contenido de `PIECE_RESULT`: `class` es `A`, `B` o `REJECT`. Si el OCR no lee el código o la confianza es baja, la pieza va a `REJECT` (R2). `thumb` es una miniatura (la imagen completa no viaja por el conducto 1; se medirá su coste en la latencia).

## 5. Ciclo de una pieza

```
Visión        pasarela-V          servidor           pasarela-R        Robot
  │ resultado ──▶│                    │                   │              │
  │              │── PIECE_RESULT ───▶│                   │              │
  │              │◀──── ACK ──────────│                   │              │
  │              │                    │──── ORDER ───────▶│              │
  │              │                    │◀── ORDER_ACK ─────│── variables ▶│
  │              │                    │◀── ROBOT_STATUS ──│◀─ sondeo ────│
  │              │                    │◀── ORDER_DONE ────│◀─ fin rutina─│
  │              │                    │──── ACK ─────────▶│              │
```

Si `ORDER_ACK` no llega en `ack_timeout_s`, el servidor lo registra como error de la pieza, lo muestra en la interfaz y no reenvía la orden en silencio (P4). Si pasa `order_timeout_s` sin `ORDER_DONE`, igual.

## 6. Tiempos (todos en la configuración, R5)

| Parámetro | Valor de partida | Sección de `config/ejemplo.ini` |
|---|---|---|
| Latido | 1 s | `protocol.heartbeat_s` |
| Latidos perdidos para dar el extremo por caído | 3 | `protocol.missed_beats` |
| Espera de confirmación de una orden | 2 s | `protocol.ack_timeout_s` |
| Duración máxima de una rutina | 60 s | `protocol.order_timeout_s` |
| Sondeo de variables del robot | 200 ms | `robot.poll_ms` |

## 7. Preguntas abiertas

1. ¿Cómo entrega HALCON el resultado a la pasarela de visión? Propuesta: por TCP local en claro, con el mismo formato de mensaje `PIECE_RESULT`. Se acuerda con Visión.
2. ¿Qué variables globales de KRL usa la pasarela-R para la orden y para el fin de rutina? Lo cierra Diego con Robótica en C1.
3. ¿Qué clases hay y qué rutina corresponde a cada una? Lo fija Robótica.
4. ¿Miniatura o imagen comprimida? Se decide con la medida de latencia (R4).
