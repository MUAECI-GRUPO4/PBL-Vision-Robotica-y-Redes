"""Esqueleto del servidor intermedio (tarea 1.3).

Estado en C0:
  - escucha en los dos conductos (visión y robot), un cliente por conducto;
  - si un cliente se reconecta, sustituye a la conexión anterior;
  - reenvía en bruto visión -> robot y robot -> visión (provisional);
  - guarda el estado de cada enlace y una lista de eventos.

Pendiente:
  - C2: delimitar mensajes con la librería común de DL (src/proto) en lugar
    de reenviar bytes en bruto (formato en docs/contratos.md, apartado 2).
  - C5: latidos, reconexión y logs con identificador de pieza.
  - H3: TLS mutuo con el módulo de DG (1.2).
"""

import collections
import logging
import socket
import threading
import time

log = logging.getLogger("server")

TAM_BUFFER = 4096
MAX_EVENTOS = 200


class Enlace:
    """Estado de un conducto: quién está conectado y cuándo habló por última vez."""

    def __init__(self, nombre):
        self.nombre = nombre
        self.conectado = False
        self.peer = None
        self.ultimo_rx = None
        self.bytes_rx = 0
        self._sock = None
        self._lock = threading.Lock()

    def conectar(self, sock, peer):
        """Asocia una conexión nueva. Devuelve la anterior (si había) para cerrarla."""
        with self._lock:
            anterior = self._sock
            self._sock = sock
            self.peer = peer
            self.conectado = True
            self.ultimo_rx = time.time()
            return anterior

    def desconectar(self, sock):
        """Marca el enlace como caído, solo si `sock` sigue siendo la conexión actual."""
        with self._lock:
            if self._sock is not sock:
                return False
            self._sock = None
            self.conectado = False
            return True

    def anotar_rx(self, n):
        with self._lock:
            self.ultimo_rx = time.time()
            self.bytes_rx += n

    def enviar(self, datos):
        with self._lock:
            if self._sock is None:
                raise ConnectionError("enlace %s sin conexión" % self.nombre)
            self._sock.sendall(datos)

    def estado(self):
        with self._lock:
            return {
                "nombre": self.nombre,
                "conectado": self.conectado,
                "peer": "%s:%d" % self.peer if self.peer else None,
                "ultimo_rx": self.ultimo_rx,
                "bytes_rx": self.bytes_rx,
            }


class ServidorIntermedio:
    """Servidor con dos conductos: visión (1) y robot (2)."""

    def __init__(self, cfg):
        """`cfg` es un ConfigParser con config/ejemplo.ini: secciones [server], [protocol] y [tls]."""
        s = cfg["server"]
        self.host = s.get("host", "0.0.0.0")
        self.puertos = {
            "vision": s.getint("port_vision"),
            "robot": s.getint("port_robot"),
        }
        # Un extremo se da por caído tras missed_beats latidos sin recibir nada (P5); se usa en C5
        self.timeout_latido = (cfg.getfloat("protocol", "heartbeat_s", fallback=1.0)
                               * cfg.getint("protocol", "missed_beats", fallback=3))
        self.tls = cfg.getboolean("tls", "enabled", fallback=False)

        self.enlaces = {nombre: Enlace(nombre) for nombre in self.puertos}
        self.eventos = collections.deque(maxlen=MAX_EVENTOS)
        self._escucha = {}
        self._parar = threading.Event()

    # ------------------------------------------------------------------ ciclo de vida

    def iniciar(self):
        """Abre los sockets de escucha y lanza un hilo de aceptación por conducto."""
        for nombre, puerto in self.puertos.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, puerto))
            sock.listen(1)
            sock.settimeout(0.5)  # para poder comprobar _parar
            # Con puerto 0 el sistema asigna uno libre (útil en los tests)
            self.puertos[nombre] = sock.getsockname()[1]
            self._escucha[nombre] = sock
            threading.Thread(
                target=self._aceptar, args=(nombre, sock), name="aceptar-" + nombre, daemon=True
            ).start()
            log.info("Conducto %s escuchando en %s:%d", nombre, self.host, self.puertos[nombre])
        self.registrar_evento("arranque", "servidor iniciado (TLS %s)" % ("sí" if self.tls else "no"))

    def detener(self):
        self._parar.set()
        for sock in self._escucha.values():
            sock.close()
        for enlace in self.enlaces.values():
            with enlace._lock:
                if enlace._sock is not None:
                    enlace._sock.close()
        self.registrar_evento("parada", "servidor detenido")

    # ------------------------------------------------------------------ conexiones

    def _envolver(self, sock):
        """Punto de entrada de TLS mutuo. En claro hasta H3."""
        if self.tls:
            # TODO(H3): usar el módulo TLS mutuo de DG (src/pki) con [tls] ca/cert/key
            raise NotImplementedError("TLS mutuo pendiente del módulo de src/pki")
        return sock

    def _aceptar(self, nombre, sock_escucha):
        enlace = self.enlaces[nombre]
        while not self._parar.is_set():
            try:
                conn, peer = sock_escucha.accept()
            except socket.timeout:
                continue
            except OSError:
                break  # socket de escucha cerrado
            conn = self._envolver(conn)
            anterior = enlace.conectar(conn, peer)
            if anterior is not None:
                anterior.close()
                self.registrar_evento("reconexion", "%s: nueva conexión desde %s:%d" % ((nombre,) + peer))
            else:
                self.registrar_evento("enlace_arriba", "%s conectado desde %s:%d" % ((nombre,) + peer))
            threading.Thread(
                target=self._atender, args=(enlace, conn), name="atender-" + nombre, daemon=True
            ).start()

    def _atender(self, enlace, conn):
        try:
            while not self._parar.is_set():
                datos = conn.recv(TAM_BUFFER)
                if not datos:
                    break
                enlace.anotar_rx(len(datos))
                self._al_recibir(enlace.nombre, datos)
        except OSError as e:
            log.debug("Error en %s: %s", enlace.nombre, e)
        finally:
            if enlace.desconectar(conn):
                self.registrar_evento("enlace_abajo", "%s desconectado" % enlace.nombre)
            conn.close()

    # ------------------------------------------------------------------ reenvío

    def _al_recibir(self, origen, datos):
        """Procesa lo recibido por un conducto.

        Provisional: reenvía los bytes tal cual al otro conducto.
        TODO(C2): separar mensajes con src/proto y actuar según el tipo
        (docs/contratos.md, apartado 5): PIECE_RESULT -> ACK y ORDER al robot;
        ORDER_DONE -> ACK. Registrar el identificador de pieza.
        """
        destino = "robot" if origen == "vision" else "vision"
        log.debug("%s -> %s: %d bytes", origen, destino, len(datos))
        try:
            self.enlaces[destino].enviar(datos)
        except (ConnectionError, OSError) as e:
            self.registrar_evento("reenvio_fallido", "%s -> %s: %s" % (origen, destino, e))

    # ------------------------------------------------------------------ estado y eventos

    def registrar_evento(self, tipo, detalle):
        self.eventos.append({"t": time.time(), "tipo": tipo, "detalle": detalle})
        log.info("[%s] %s", tipo, detalle)

    def estado(self):
        """Resumen para la interfaz web (formato pendiente de acordar con Se)."""
        return {
            "enlaces": {n: e.estado() for n, e in self.enlaces.items()},
            "eventos": list(self.eventos),
        }
