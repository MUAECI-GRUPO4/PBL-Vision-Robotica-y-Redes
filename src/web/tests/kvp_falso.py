"""KukaVarProxy falso para probar sin robot.

Habla el mismo protocolo TCP que KukaVarProxy (puerto 7000) y responde a la lectura
de la variable de estado con la secuencia simulada. Otras variables devuelven
estado de error, como hace el proxy real con las variables que no son globales.

  python -m src.web.tests.kvp_falso --escenario ambas
  python -m src.web --modo kvp --kvp-host 127.0.0.1
"""

import argparse
import socketserver
import struct

from ..simulador import ESCENARIOS, SimuladorEscenario, SimuladorProceso

SIM = SimuladorProceso()
VARIABLE = "estado_g4"


class ManejadorKVP(socketserver.BaseRequestHandler):
    def _recibir(self, n):
        buf = b""
        while len(buf) < n:
            trozo = self.request.recv(n - len(buf))
            if not trozo:
                raise ConnectionError
            buf += trozo
        return buf

    def handle(self):
        try:
            while True:
                id_msg, largo = struct.unpack("!HH", self._recibir(4))
                cuerpo = self._recibir(largo)
                modo, largo_nombre = struct.unpack("!BH", cuerpo[:3])
                nombre = cuerpo[3:3 + largo_nombre].decode("ascii", "replace")
                if modo == 0 and nombre.lower() == VARIABLE.lower():
                    valor, estado = str(SIM.leer()).encode(), b"\x00\x01\x01"
                else:
                    valor, estado = b"", b"\x00\x01\x00"
                datos = struct.pack("!BH", modo, len(valor)) + valor + estado
                self.request.sendall(struct.pack("!HH", id_msg, len(datos)) + datos)
        except (ConnectionError, OSError):
            pass


class ServidorKVP(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="KukaVarProxy falso")
    ap.add_argument("--port", type=int, default=7000)
    ap.add_argument("--variable", default=VARIABLE)
    ap.add_argument("--escenario", choices=sorted(ESCENARIOS))
    a = ap.parse_args()
    VARIABLE = a.variable
    if a.escenario:
        SIM = SimuladorEscenario(a.escenario, repetir=True)
    print("KukaVarProxy falso en :%d sirviendo %s" % (a.port, VARIABLE))
    ServidorKVP(("127.0.0.1", a.port), ManejadorKVP).serve_forever()
