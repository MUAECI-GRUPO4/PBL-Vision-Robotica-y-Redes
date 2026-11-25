"""Arranque del servidor intermedio: python -m src.server --config config/ejemplo.ini"""

import argparse
import configparser
import logging
import time

from .servidor import ServidorIntermedio


def main():
    parser = argparse.ArgumentParser(description="Servidor intermedio de PBL 1")
    parser.add_argument("--config", default="config/ejemplo.ini", help="fichero de configuración")
    args = parser.parse_args()

    cfg = configparser.ConfigParser()
    if not cfg.read(args.config, encoding="utf-8"):
        parser.error("no se pudo leer %s" % args.config)

    logging.basicConfig(
        level=cfg.get("node", "log_level", fallback="INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    servidor = ServidorIntermedio(cfg)
    servidor.iniciar()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        servidor.detener()


if __name__ == "__main__":
    main()
