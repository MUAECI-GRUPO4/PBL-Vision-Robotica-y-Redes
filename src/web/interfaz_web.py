"""Interfaz web de supervisión de la celda (tarea 1.7), boceto C1.

Estado en C1:
  - un hilo sondea la variable de estado del ciclo (estado_g4) y deriva de sus
    transiciones los contadores, los giros por pieza, el tiempo de ciclo y los eventos;
  - fuentes de datos: simulador, escenario fijo o KukaVarProxy directo (solo lectura);
  - servidor HTTP de la biblioteca estándar: ficheros de interfaz/ y GET /api/robot.

Pendiente:
  - Tomar los datos del servidor intermedio (ROBOT_STATUS, ORDER_DONE...) en lugar de
    leer KukaVarProxy directamente. Pregunta abierta 1 del README, con la tarea 1.3.
  - Resto de rutas previstas: /api/estado, /api/piezas, /api/eventos.

    [KukaVarProxy :7000] <-TCP- [hilo de sondeo] -> MonitorCelda (estado, contadores, eventos)
                                                            |
    [navegadores] <-HTTP JSON /api/robot (sondeo)- [ThreadingHTTPServer + interfaz/]

Un único hilo habla con la controladora, haya los navegadores que haya abiertos.
"""

import functools
import json
import logging
import os
import threading
import time
from collections import deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("web")

DIR_INTERFAZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interfaz")
MAX_EVENTOS = 60

NOMBRES_ESTADO = {
    0: "RECOGIENDO PIEZA",
    1: "EN CÁMARA",
    2: "GIRO SOLICITADO",
    3: "PIEZA BUENA",
    4: "PIEZA MALA",
}

# Transiciones del ciclo según docs/variables-krl.md. Cualquier otra se avisa como evento.
TRANSICIONES_VALIDAS = {(0, 1), (1, 2), (2, 1), (1, 3), (1, 4), (3, 0), (4, 0)}


class MonitorCelda:
    """Sondea la variable de estado y deriva contadores y eventos de sus transiciones.

    `fuente` es cualquier objeto con leer() -> valor: LectorKVP (con `variable`),
    SimuladorProceso o SimuladorEscenario.
    """

    def __init__(self, fuente, variable, modo, periodo_s=0.2, info=None):
        self.fuente = fuente
        self.variable = variable
        self.modo = modo
        self.periodo_s = max(0.02, periodo_s)
        self.info = info or {}

        self._lock = threading.Lock()
        self._parar = threading.Event()
        self.conectado = False
        self.ultimo_error = ""
        self.valor_bruto = None
        self.estado = None
        self.desde = time.time()
        self.ms_lectura = None
        self.giros = 0
        self.inicio_ciclo = None
        self.ultimo_ciclo_s = None
        self.contadores = {"ciclos": 0, "buenas": 0, "malas": 0}
        self.eventos = deque(maxlen=MAX_EVENTOS)
        self._evento("info", "Interfaz iniciada: %s" % modo)

    # ------------------------------------------------------------------ eventos

    def _evento(self, nivel, texto):
        self.eventos.appendleft({"t": time.time(), "nivel": nivel, "texto": texto})
        log.info("[%s] %s", nivel, texto)

    # ------------------------------------------------------------------ transiciones

    def aplicar(self, bruto):
        """Procesa un valor leído. Se llama con el lock tomado (o desde las pruebas)."""
        ahora = time.time()
        self.valor_bruto = bruto
        try:
            nuevo = int(float(bruto))
        except ValueError:
            nuevo = None
        if nuevo not in NOMBRES_ESTADO:
            if self.estado is not None or not self.ultimo_error:
                self._evento("aviso", "Valor inesperado %r en %s" % (bruto, self.variable))
            self.ultimo_error = "valor inesperado %r" % bruto
            self.estado = None
            return
        self.ultimo_error = ""
        if nuevo == self.estado:
            return

        anterior = self.estado
        if anterior is not None and (anterior, nuevo) not in TRANSICIONES_VALIDAS:
            self._evento("aviso", "Transición inesperada %s -> %s" % (anterior, nuevo))

        if nuevo == 0:
            if anterior in (3, 4) and self.inicio_ciclo is not None:
                self.contadores["ciclos"] += 1
                self.ultimo_ciclo_s = ahora - self.inicio_ciclo
            self.inicio_ciclo = ahora
            self.giros = 0
        elif nuevo == 2 and anterior == 1:
            self.giros += 1
        elif nuevo == 3:
            self.contadores["buenas"] += 1
        elif nuevo == 4:
            self.contadores["malas"] += 1

        nivel = "buena" if nuevo == 3 else "mala" if nuevo == 4 else "info"
        self._evento(nivel, "Estado %d  %s" % (nuevo, NOMBRES_ESTADO[nuevo]))
        self.estado = nuevo
        self.desde = ahora

    # ------------------------------------------------------------------ hilo de sondeo

    def _leer(self):
        if hasattr(self.fuente, "cerrar"):  # LectorKVP
            return self.fuente.leer(self.variable)
        return str(self.fuente.leer())

    def _sondear(self):
        espera = 0.5
        while not self._parar.is_set():
            t0 = time.perf_counter()
            try:
                bruto = self._leer()
                ms = (time.perf_counter() - t0) * 1000.0
                with self._lock:
                    if not self.conectado:
                        self._evento("info", "Enlace con el robot establecido")
                    self.conectado = True
                    self.ms_lectura = round(ms, 1)
                    self.aplicar(bruto)
                espera = 0.5
                self._parar.wait(max(0.0, self.periodo_s - (time.perf_counter() - t0)))
            except Exception as e:  # red, KukaVarProxy...
                with self._lock:
                    if self.conectado or self.ultimo_error != str(e):
                        self._evento("error", "Enlace con el robot: %s" % e)
                    self.conectado = False
                    self.ultimo_error = str(e)
                    self.estado = None
                self._parar.wait(espera)
                espera = min(espera * 2, 5.0)

    def iniciar(self):
        threading.Thread(target=self._sondear, name="sondeo-robot", daemon=True).start()

    def detener(self):
        self._parar.set()
        if hasattr(self.fuente, "cerrar"):
            self.fuente.cerrar()

    # ------------------------------------------------------------------ API

    def resumen(self):
        """Respuesta de GET /api/robot."""
        ahora = time.time()
        with self._lock:
            return {
                "hora_servidor": ahora,
                "celda": self.info.get("celda", "Celda robot"),
                "robot": self.info.get("robot", ""),
                "modo": self.modo,
                "origen": self.info.get("origen", ""),
                "variable": self.variable,
                "periodo_ms": int(self.periodo_s * 1000),
                "conectado": self.conectado,
                "ultimo_error": self.ultimo_error,
                "ms_lectura": self.ms_lectura,
                "valor_bruto": self.valor_bruto,
                "estado": self.estado,
                "nombre_estado": NOMBRES_ESTADO.get(self.estado, "SIN DATOS"),
                "segundos_en_estado": round(ahora - self.desde, 2),
                "giros": self.giros,
                "segundos_ciclo": round(ahora - self.inicio_ciclo, 2) if self.inicio_ciclo else None,
                "ultimo_ciclo_s": round(self.ultimo_ciclo_s, 2) if self.ultimo_ciclo_s else None,
                "contadores": dict(self.contadores),
                "eventos": list(self.eventos)[:25],
            }

    def reiniciar_contadores(self):
        with self._lock:
            self.contadores = {"ciclos": 0, "buenas": 0, "malas": 0}
            self.ultimo_ciclo_s = None
            self._evento("info", "Contadores reiniciados por el operador")


class ManejadorWeb(SimpleHTTPRequestHandler):
    monitor = None  # se asigna en crear_servidor()

    def _json(self, obj, codigo=200):
        cuerpo = json.dumps(obj).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/robot":
            return self._json(self.monitor.resumen())
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if self.path == "/api/contadores/reiniciar":
            self.monitor.reiniciar_contadores()
            return self._json({"ok": True})
        self._json({"error": "no existe"}, 404)

    def log_message(self, fmt, *args):  # el sondeo genera muchas peticiones: sin log por petición
        pass


def crear_servidor(monitor, bind, puerto):
    """Crea el servidor HTTP (sin arrancarlo). Lanza OSError si el puerto está ocupado."""
    clase = type("Manejador", (ManejadorWeb,), {"monitor": monitor})
    manejador = functools.partial(clase, directory=DIR_INTERFAZ)
    httpd = ThreadingHTTPServer((bind, puerto), manejador)
    httpd.daemon_threads = True
    return httpd
