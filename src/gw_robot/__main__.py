"""Arranque de la pasarela del robot: python -m src.gw_robot --config config/ejemplo.ini"""

import argparse
import configparser
import logging

from .pasarela import PasarelaRobot


def main():
    parser = argparse.ArgumentParser(description="Pasarela del robot de PBL 1")
    parser.add_argument("--config", default="config/ejemplo.ini", help="fichero de configuración")
    args = parser.parse_args()

    cfg = configparser.ConfigParser()
    if not cfg.read(args.config, encoding="utf-8"):
        parser.error("no se pudo leer %s" % args.config)

    logging.basicConfig(
        level=cfg.get("node", "log_level", fallback="INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    pasarela = PasarelaRobot(cfg)
    try:
        pasarela.ejecutar()
    except KeyboardInterrupt:
        pasarela.detener()


if __name__ == "__main__":
    main()
