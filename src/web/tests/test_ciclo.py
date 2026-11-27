"""Pruebas sin robot de un ciclo completo de pieza.

  python -m unittest src.web.tests.test_ciclo -v

Secuencias (variable estado_g4):
  pieza buena: 0 -> 1 -> 2 -> 1 -> 2 -> 1 -> 3 -> 0
  pieza mala:  0 -> 1 -> 2 -> 1 -> 2 -> 1 -> 4 -> 0

Las pruebas del ciclo no usan red. Las del protocolo usan solo 127.0.0.1.
"""

import socket
import threading
import unittest

from ..interfaz_web import MonitorCelda
from ..kvp_lectura import ErrorKVP, LectorKVP
from ..simulador import SimuladorEscenario, ciclo_pieza
from . import kvp_falso


class RelojFalso:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def secuencia(sim, reloj, paso=0.05):
    """Recorre el simulador entero y devuelve la lista de valores distintos seguidos."""
    vistos = []
    while reloj.t <= sim.duracion + paso:
        v = sim.leer()
        if not vistos or vistos[-1] != v:
            vistos.append(v)
        reloj.t += paso
    return vistos


def monitor_nuevo():
    return MonitorCelda(fuente=None, variable="estado_g4", modo="prueba")


def pasar_por_monitor(pasos):
    """Pasa cada valor del escenario por MonitorCelda igual que el hilo de sondeo."""
    mon = monitor_nuevo()
    reloj = RelojFalso()
    sim = SimuladorEscenario(pasos, repetir=False, reloj=reloj)
    for v in secuencia(sim, reloj):
        mon.aplicar(str(v))
    return mon


def avisos(mon):
    return [e for e in mon.eventos if e["nivel"] == "aviso"]


class TestEscenarios(unittest.TestCase):
    def test_pieza_buena(self):
        reloj = RelojFalso()
        sim = SimuladorEscenario("buena", repetir=False, reloj=reloj)
        self.assertEqual(secuencia(sim, reloj), [0, 1, 2, 1, 2, 1, 3, 0])
        self.assertTrue(sim.terminado)

    def test_pieza_mala(self):
        reloj = RelojFalso()
        sim = SimuladorEscenario("mala", repetir=False, reloj=reloj)
        self.assertEqual(secuencia(sim, reloj), [0, 1, 2, 1, 2, 1, 4, 0])

    def test_se_queda_en_el_ultimo_valor(self):
        reloj = RelojFalso()
        sim = SimuladorEscenario(ciclo_pieza(3), repetir=False, reloj=reloj)
        reloj.t = sim.duracion + 100
        self.assertEqual(sim.leer(), 3)


class TestMonitor(unittest.TestCase):
    def test_ciclo_pieza_buena(self):
        r = pasar_por_monitor("buena").resumen()
        self.assertEqual(r["contadores"], {"ciclos": 1, "buenas": 1, "malas": 0})
        self.assertEqual(r["estado"], 0)

    def test_ciclo_pieza_mala(self):
        mon = pasar_por_monitor("mala")
        self.assertEqual(mon.resumen()["contadores"], {"ciclos": 1, "buenas": 0, "malas": 1})
        self.assertFalse(avisos(mon))

    def test_cuenta_giros(self):
        mon = monitor_nuevo()
        for v in [0, 1, 2, 1, 2, 1, 2, 1]:
            mon.aplicar(str(v))
        self.assertEqual(mon.giros, 3)

    def test_transicion_inesperada(self):
        mon = monitor_nuevo()
        for v in [0, 3]:  # sin pasar por la cámara
            mon.aplicar(str(v))
        self.assertTrue(avisos(mon))

    def test_valor_no_valido(self):
        mon = monitor_nuevo()
        mon.aplicar("7")
        self.assertIsNone(mon.estado)
        self.assertIn("valor inesperado", mon.ultimo_error)


class TestProtocoloKVP(unittest.TestCase):
    """Cliente de KukaVarProxy contra el proxy falso en 127.0.0.1."""

    @classmethod
    def setUpClass(cls):
        cls.reloj = RelojFalso()
        kvp_falso.SIM = SimuladorEscenario("mala", repetir=False, reloj=cls.reloj)
        kvp_falso.VARIABLE = "estado_g4"
        cls.srv = kvp_falso.ServidorKVP(("127.0.0.1", 0), kvp_falso.ManejadorKVP)
        cls.puerto = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_ciclo_completo_por_tcp(self):
        lector = LectorKVP("127.0.0.1", self.puerto, timeout=1.0)
        sim = SimuladorEscenario("mala", repetir=False, reloj=self.reloj)
        vistos = []
        self.reloj.t = 0.0
        while self.reloj.t <= sim.duracion + 0.05:
            v = int(lector.leer("estado_g4"))
            if not vistos or vistos[-1] != v:
                vistos.append(v)
            self.reloj.t += 0.05
        lector.cerrar()
        self.assertEqual(vistos, [0, 1, 2, 1, 2, 1, 4, 0])

    def test_variable_desconocida(self):
        lector = LectorKVP("127.0.0.1", self.puerto, timeout=1.0)
        with self.assertRaises(ErrorKVP):
            lector.leer("NO_EXISTE")
        lector.cerrar()

    def test_robot_inalcanzable(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        libre = s.getsockname()[1]
        s.close()
        lector = LectorKVP("127.0.0.1", libre, timeout=0.5)
        with self.assertRaises(OSError):
            lector.leer("estado_g4")


if __name__ == "__main__":
    unittest.main(verbosity=2)
