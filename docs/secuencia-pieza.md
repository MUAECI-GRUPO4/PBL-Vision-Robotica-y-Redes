# Secuencia de una pieza (PBL 1)

**Estado:** C1 de Di (tarea 1.3). Parte del ciclo del apartado 5 de [`contratos.md`](contratos.md) y lo concreta con la variable `estado_g4` del robot (tabla en [`variables-krl.md`](variables-krl.md)). Lo marcado *por confirmar* se cierra con Robótica y Visión.

GitHub dibuja los diagramas a partir del texto Mermaid; para editarlos basta con cambiar el texto.

## 1. Ciclo normal

La pasarela del robot (pasarela-R) sondea `estado_g4` cada `robot.poll_ms` (200 ms) por KukaVarProxy. Solo escribe en `estado_g4` cuando vale 1 (robot esperando a la cámara).

```mermaid
sequenceDiagram
    autonumber
    participant V as Visión (HALCON)
    participant PV as Pasarela-V
    participant S as Servidor
    participant PR as Pasarela-R
    participant R as Robot (KRL)

    Note over R: estado_g4 = 0 (reposo)
    R->>R: estado_g4 = 1 (espera a la cámara)
    PR->>R: sondeo estado_g4 (KukaVarProxy)
    R-->>PR: 1
    PR->>S: ROBOT_STATUS state=WAITING_CAMERA
    V->>PV: resultado OCR (texto, clase, confianza)
    PV->>S: PIECE_RESULT piece=P…-001 class=GOOD
    S-->>PV: ACK
    S->>PR: ORDER piece=P…-001 routine=GOOD
    PR->>R: escribe estado_g4 = 3
    PR->>R: lee estado_g4 para comprobar la escritura
    R-->>PR: 3
    PR-->>S: ORDER_ACK accepted=true
    loop cada poll_ms mientras estado_g4 = 3
        PR->>R: sondeo estado_g4
        PR->>S: ROBOT_STATUS state=RUNNING (cada segundo)
    end
    R->>R: rutina de pieza buena y estado_g4 = 0
    PR->>R: sondeo estado_g4
    R-->>PR: 0
    PR->>S: ORDER_DONE result=OK
    S-->>PR: ACK
```

La pieza mala es igual con `routine=BAD` y `estado_g4 = 4`.

## 2. El OCR no lee la pieza: giro del eje 6

Si Visión no consigue leer el código, el robot gira la pieza 15° en el eje 6 y se vuelve a capturar. Se repite hasta 23 giros (345° en total), lo que basta para ver la pieza entera. La pieza conserva su identificador.

```mermaid
sequenceDiagram
    participant V as Visión (HALCON)
    participant PV as Pasarela-V
    participant S as Servidor
    participant PR as Pasarela-R
    participant R as Robot (KRL)

    Note over R: estado_g4 = 1
    V->>PV: OCR sin lectura o confianza baja
    PV->>S: PIECE_RESULT piece=P…-002 class=ROTATE
    S-->>PV: ACK
    S->>PR: ORDER piece=P…-002 routine=ROTATE
    PR->>R: escribe estado_g4 = 2
    PR-->>S: ORDER_ACK accepted=true
    R->>R: gira 15° el eje 6 y estado_g4 = 1
    PR->>R: sondeo estado_g4
    R-->>PR: 1
    PR->>S: ORDER_DONE result=OK
    Note over V,R: nueva captura de la misma pieza, vuelve al ciclo normal
    alt tras 23 giros (345°) sigue sin leerse (por confirmar)
        S->>PR: ORDER piece=P…-002 routine=BAD
        PR->>R: escribe estado_g4 = 4
    end
```

## 3. Casos de error

El programa del robot no tiene estados de error propios en `estado_g4`. Los casos de esta sección son fallos de comunicación entre los nodos y de tiempos del protocolo.

```mermaid
sequenceDiagram
    participant PV as Pasarela-V
    participant S as Servidor
    participant PR as Pasarela-R
    participant R as Robot (KRL)

    alt E1. El robot no está esperando (estado_g4 distinto de 1)
        S->>PR: ORDER piece=P…-003
        PR->>R: sondeo estado_g4
        R-->>PR: 3 (todavía con la pieza anterior)
        PR-->>S: ORDER_ACK accepted=false, ERROR code=ROBOT_BUSY
        Note over S: no escribe nada, registra el evento y avisa en la web
    else E2. No llega ORDER_ACK en ack_timeout_s (2 s)
        S->>PR: ORDER piece=P…-004
        Note over S: vence ack_timeout_s
        S->>S: ERROR code=TIMEOUT en la pieza, sin reenvío automático (P4)
    else E3. No llega ORDER_DONE en order_timeout_s (60 s)
        PR->>S: ROBOT_STATUS state=RUNNING
        Note over S: vence order_timeout_s
        S->>S: ERROR code=TIMEOUT, alarma en la web
    else E4. KukaVarProxy no responde (robot apagado o cable)
        PR-xR: conexión TCP 7000 rechazada o sin respuesta
        PR->>S: ERROR code=KVP_DOWN
        PR->>PR: reintenta cada reconnect_s
    else E5. Se cae el conducto 2 a mitad de pieza
        PR-xS: conexión perdida
        Note over S: missed_beats latidos sin recibir nada, enlace robot caído
        S->>S: pieza en curso marcada como error, evento en la web
        PR->>S: reconexión y HELLO
        PR->>S: ROBOT_STATUS con el estado_g4 actual
    else E6. Se cae el conducto 1 (visión)
        PV-xS: conexión perdida
        Note over S: enlace visión caído, no se envían órdenes nuevas
        Note over R: el robot se queda en estado_g4 = 1 esperando
    end
```

## 4. Confirmado con la prueba real

Con HALCON, el robot y el servidor básico:

- Al terminar la rutina de pieza buena o mala, el robot vuelve a `estado_g4 = 0`; tras girar, a `estado_g4 = 1`.
- La cámara captura cuando el robot está en `estado_g4 = 1`.
- El giro llega hasta 345° (23 giros de 15°).

## 5. Pendiente

1. **Clases del protocolo (para DL).** `contratos.md` usa `class` = `A`, `B` o `REJECT`; el robot trabaja con pieza buena, mala o girar. Propuesta: `class` = `GOOD`, `BAD` o `ROTATE` y `ORDER.body.routine` con los mismos valores (3, 4 y 2 en `estado_g4`).
2. **Aviso a Visión (para DL).** Como la cámara captura cuando el robot espera, el servidor tiene que avisar a la pasarela-V de que el robot está en `estado_g4 = 1` (por ejemplo, reenviándole `ROBOT_STATUS`). Ese mensaje del servidor a la pasarela-V no está todavía en `contratos.md`.
3. **Pieza sin leer tras 345°.** Con la prueba no ha pasado; propuesta: se trata como pieza mala (`routine=BAD`).
