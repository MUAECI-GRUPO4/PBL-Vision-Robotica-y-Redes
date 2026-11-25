"""Cliente de KukaVarProxy (esqueleto, se implementa en C4).

KukaVarProxy escucha por TCP (puerto 7000 por defecto) en la controladora y
permite leer y escribir variables globales de KRL. Formato de trama previsto
(big-endian, a verificar contra el simulador de robot en C4):

  Petición:
    id_mensaje      uint16
    longitud        uint16   bytes que siguen a este campo
    modo            uint8    0 = leer, 1 = escribir
    long_nombre     uint16
    nombre          ASCII
    [long_valor     uint16   solo al escribir
     valor          ASCII]

  Respuesta:
    id_mensaje      uint16
    longitud        uint16
    modo            uint8
    long_valor      uint16
    valor           ASCII
    estado          3 bytes  (el último indica éxito)
"""

import socket


class ClienteKukaVarProxy:
    def __init__(self, host, puerto=7000, timeout=2.0):
        self.host = host
        self.puerto = puerto
        self.timeout = timeout
        self._sock = None
        self._id = 0

    def conectar(self):
        self._sock = socket.create_connection((self.host, self.puerto), timeout=self.timeout)

    def cerrar(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def leer(self, variable):
        """Devuelve el valor de `variable` como texto."""
        # TODO(C4): construir la trama de lectura con struct.pack(">HHBH", ...) y leer la respuesta completa
        raise NotImplementedError

    def escribir(self, variable, valor):
        """Escribe `valor` (texto KRL) en `variable` y comprueba el estado de la respuesta."""
        # TODO(C4): construir la trama de escritura y comprobar el byte de estado
        raise NotImplementedError

    def _siguiente_id(self):
        self._id = (self._id + 1) % 0x10000
        return self._id
