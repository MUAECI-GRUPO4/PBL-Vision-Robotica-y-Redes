"""Comprueba que la configuración de ejemplo y los ejemplos de docs/contratos.md son válidos.

Ejecutar desde la raíz del repositorio:  python -m unittest discover -s tests
"""
import configparser
import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TIPOS = {"HELLO", "HELLO_ACK", "HEARTBEAT", "PIECE_RESULT", "ORDER", "ORDER_ACK",
         "ROBOT_STATUS", "ORDER_DONE", "ACK", "ERROR"}
RESPUESTAS = {"HELLO_ACK", "ORDER_ACK", "ACK", "ERROR"}
CON_PIEZA = {"PIECE_RESULT", "ORDER", "ORDER_ACK", "ROBOT_STATUS", "ORDER_DONE"}
ID_PIEZA = re.compile(r"^P\d{8}-\d{6}-\d{3}$")
TEXTO = (RAIZ / "docs" / "contratos.md").read_text(encoding="utf-8")


class ConfigEjemplo(unittest.TestCase):
    def setUp(self):
        self.cfg = configparser.ConfigParser()
        self.cfg.read(RAIZ / "config" / "ejemplo.ini", encoding="utf-8")

    def test_secciones(self):
        for s in ("node", "server", "tls", "protocol", "robot", "web"):
            self.assertIn(s, self.cfg)

    def test_valores_sin_comentarios_pegados(self):
        for sec in self.cfg.sections():
            for k, v in self.cfg[sec].items():
                self.assertNotIn("#", v, f"[{sec}] {k}")

    def test_tiempos_coinciden_con_los_contratos(self):
        p, r = self.cfg["protocol"], self.cfg["robot"]
        esperado = {"heartbeat_s": "1", "missed_beats": "3", "ack_timeout_s": "2", "order_timeout_s": "60"}
        for k, v in esperado.items():
            self.assertEqual(p[k], v)
            self.assertIn(f"`protocol.{k}`", TEXTO)
        self.assertEqual(r["poll_ms"], "200")

    def test_sin_secretos_en_el_fichero(self):
        for sec in self.cfg.sections():
            for k in self.cfg[sec]:
                self.assertNotIn("password", k)
                self.assertNotIn("secret", k)


class Ejemplos(unittest.TestCase):
    mensajes = [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", TEXTO, re.S)]

    def test_hay_un_ejemplo_de_cada_tipo(self):
        self.assertEqual({m["type"] for m in self.mensajes}, TIPOS)

    def test_sobre_comun(self):
        for m in self.mensajes:
            for campo in ("v", "type", "id", "ts", "body"):
                self.assertIn(campo, m, m["type"])
            self.assertEqual(m["v"], 1)
            self.assertRegex(m["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")

    def test_las_respuestas_llevan_ref(self):
        for m in self.mensajes:
            self.assertEqual("ref" in m, m["type"] in RESPUESTAS, m["type"])

    def test_los_mensajes_de_pieza_llevan_identificador_valido(self):  # P3
        for m in self.mensajes:
            if m["type"] in CON_PIEZA:
                self.assertRegex(m.get("piece", ""), ID_PIEZA, m["type"])

    def test_clase_valida(self):
        resultado = next(m for m in self.mensajes if m["type"] == "PIECE_RESULT")
        self.assertIn(resultado["body"]["class"], {"A", "B", "REJECT"})
        self.assertTrue(0 <= resultado["body"]["confidence"] <= 1)

    def test_cada_tipo_esta_en_la_tabla(self):
        for t in TIPOS:
            self.assertIn(f"| `{t}` |", TEXTO)


if __name__ == "__main__":
    unittest.main()
