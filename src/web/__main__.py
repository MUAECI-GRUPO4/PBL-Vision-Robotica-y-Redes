"""Arranque de la interfaz web: python -m src.web --config config/ejemplo.ini

Ejemplos:
  python -m src.web                                  simulador (ciclos al azar)
  python -m src.web --escenario ambas                pieza 1 buena (3) y pieza 2 mala (4)
  python -m src.web --escenario buena --una-vez      un ciclo y se queda en el último valor
  python -m src.web --modo kvp                       robot real ([robot] kvp_host / kvp_port)
  python -m src.web --port 8090                      otro puerto (8080 lo ocupa LabVIEW en algunos PC)
"""

import argparse
import configparser
import logging

from .interfaz_web import MonitorCelda, crear_servidor
from .kvp_lectura import LectorKVP
from .simulador import ESCENARIOS, SimuladorEscenario, SimuladorProceso

VARIABLE_ESTADO = "estado_g4"  # docs/variables-krl.md (tarea 1.6)


def main():
    parser = argparse.ArgumentParser(description="Interfaz web de supervisión de PBL 1")
    parser.add_argument("--config", default="config/ejemplo.ini", help="fichero de configuración")
    parser.add_argument("--modo", choices=["sim", "kvp"], default="sim",
                        help="sim: simulador sin red; kvp: lee el robot por KukaVarProxy (solo lectura)")
    parser.add_argument("--escenario", choices=sorted(ESCENARIOS),
                        help="secuencia fija de prueba, sin robot: buena, mala o ambas")
    parser.add_argument("--una-vez", action="store_true", help="reproduce el escenario una vez y se queda quieto")
    parser.add_argument("--kvp-host", help="IP de la controladora (por defecto [robot] kvp_host)")
    parser.add_argument("--variable", help="variable de estado (por defecto [robot] var_state o estado_g4)")
    parser.add_argument("--bind", help="IP de escucha (por defecto [web] bind)")
    parser.add_argument("--port", type=int, help="puerto HTTP (por defecto [web] port)")
    args = parser.parse_args()

    cfg = configparser.ConfigParser()
    if not cfg.read(args.config, encoding="utf-8"):
        parser.error("no se pudo leer %s" % args.config)

    logging.basicConfig(
        level=cfg.get("node", "log_level", fallback="INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    variable = args.variable or cfg.get("robot", "var_state", fallback=VARIABLE_ESTADO)
    kvp_host = args.kvp_host or cfg.get("robot", "kvp_host", fallback="127.0.0.1")
    kvp_port = cfg.getint("robot", "kvp_port", fallback=7000)
    periodo_s = cfg.getint("robot", "poll_ms", fallback=200) / 1000.0

    if args.modo == "kvp" and not args.escenario:
        fuente = LectorKVP(kvp_host, kvp_port)
        modo = "kvp"
        origen = "%s:%d" % (kvp_host, kvp_port)
    elif args.escenario:
        fuente = SimuladorEscenario(args.escenario, repetir=not args.una_vez)
        modo = "escenario"
        origen = "escenario '%s'" % args.escenario
    else:
        fuente = SimuladorProceso()
        modo = "sim"
        origen = "simulador"

    monitor = MonitorCelda(fuente, variable, modo, periodo_s, info={
        "celda": "Celda robot · Inspección por visión",
        "robot": "KUKA KR2",
        "origen": origen,
    })

    bind = args.bind or cfg.get("web", "bind", fallback="127.0.0.1")
    puerto = args.port or cfg.getint("web", "port", fallback=8080)
    try:
        httpd = crear_servidor(monitor, bind, puerto)
    except OSError as e:
        parser.exit(1, "ERROR: no se puede abrir el puerto %d (%s).\n"
                       "Otro programa lo está usando (en PC con LabVIEW, el 8080). Prueba con --port 8090.\n"
                       "Para ver quién lo usa:  netstat -ano | findstr :%d\n" % (puerto, e, puerto))

    if args.escenario:
        print("Escenario '%s': %s" % (args.escenario, " -> ".join(str(v) for v, _ in ESCENARIOS[args.escenario])))
    print("Interfaz web | modo=%s  origen=%s  variable=%s" % (modo, origen, variable))
    if bind in ("0.0.0.0", ""):
        print("Escuchando en todas las interfaces. Abrir http://localhost:%d  (Ctrl+C para parar)" % puerto)
    else:
        print("Escuchando solo en %s. Abrir http://%s:%d  (Ctrl+C para parar)" % (bind, bind, puerto))

    monitor.iniciar()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        monitor.detener()
        httpd.server_close()


if __name__ == "__main__":
    main()
