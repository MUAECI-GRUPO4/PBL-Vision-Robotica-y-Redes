"""Cliente mínimo de KukaVarProxy, solo lectura y sin dependencias.

KukaVarProxy corre en la controladora (lado Windows) y escucha en TCP 7000.
Formato (enteros en orden de red, big-endian):

  Petición de lectura:
    uint16  id del mensaje
    uint16  longitud del cuerpo  -> bytes que siguen
    uint8   modo                 -> 0 = leer, 1 = escribir
    uint16  longitud del nombre
    bytes   nombre de la variable (ASCII, p. ej. b"estado_g4")

  Respuesta:
    uint16  id del mensaje (eco)
    uint16  longitud del cuerpo
    uint8   modo
    uint16  longitud del valor
    bytes   valor (texto ASCII, p. ej. b"2")
    3 bytes estado (termina en 0x01 si la lectura fue correcta)

La interfaz web es solo de lectura: este cliente no tiene método de escritura a
propósito. Escribir en el robot es cosa de la pasarela-R (tarea 1.4).
"""

import socket
import struct
import threading


class ErrorKVP(Exception):
    """Error del protocolo o de la controladora."""


class LectorKVP:
    def __init__(self, host, puerto=7000, timeout=1.0):
        self.host = host
        self.puerto = int(puerto)
        self.timeout = float(timeout)
        self._sock = None
        self._id = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ conexión

    def conectar(self):
        self.cerrar()
        sock = socket.create_connection((self.host, self.puerto), timeout=self.timeout)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(self.timeout)
        self._sock = sock

    def cerrar(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

    # ------------------------------------------------------------------ protocolo

    def _recibir(self, n):
        buf = bytearray()
        while len(buf) < n:
            trozo = self._sock.recv(n - len(buf))
            if not trozo:
                raise ErrorKVP("KukaVarProxy cerró la conexión")
            buf.extend(trozo)
        return bytes(buf)

    def _peticion_lectura(self, variable):
        nombre = variable.encode("ascii")
        cuerpo = struct.pack("!BH", 0, len(nombre)) + nombre
        id_msg = self._id
        self._id = (self._id + 1) & 0xFFFF

        self._sock.sendall(struct.pack("!HH", id_msg, len(cuerpo)) + cuerpo)

        id_rsp, largo = struct.unpack("!HH", self._recibir(4))
        datos = self._recibir(largo)
        if id_rsp != id_msg:
            raise ErrorKVP("id de mensaje distinto (enviado %d, recibido %d)" % (id_msg, id_rsp))
        if len(datos) < 3:
            raise ErrorKVP("respuesta demasiado corta")

        _modo, largo_valor = struct.unpack("!BH", datos[:3])
        valor = datos[3:3 + largo_valor]
        estado = datos[3 + largo_valor:]
        if not estado.endswith(b"\x01"):
            raise ErrorKVP("la controladora rechazó la lectura de %r (¿variable no global?)" % variable)
        return valor.decode("ascii", errors="replace").strip()

    def leer(self, variable):
        """Devuelve el valor de la variable tal como lo envía la controladora (texto)."""
        with self._lock:
            if self._sock is None:
                self.conectar()
            try:
                return self._peticion_lectura(variable)
            except (OSError, ErrorKVP, struct.error):
                self.cerrar()  # se reconecta limpio en la siguiente lectura
                raise


if __name__ == "__main__":
    # Prueba a mano:  python -m src.web.kvp_lectura 10.172.21.201 estado_g4
    import sys
    import time

    if len(sys.argv) < 3:
        print("uso: python -m src.web.kvp_lectura <ip> <variable> [puerto]")
        sys.exit(1)
    lector = LectorKVP(sys.argv[1], int(sys.argv[3]) if len(sys.argv) > 3 else 7000)
    while True:
        t0 = time.perf_counter()
        v = lector.leer(sys.argv[2])
        print("%s = %r   (%.1f ms)" % (sys.argv[2], v, (time.perf_counter() - t0) * 1000))
        time.sleep(0.5)
