"""Pasarela del robot de PBL 1 (tarea 1.4).

Recibe órdenes del servidor intermedio por el conducto 2 y las traduce a
escrituras de variables en la controladora KUKA a través de KukaVarProxy.
"""

from .kukavarproxy import ClienteKukaVarProxy
from .pasarela import PasarelaRobot

__all__ = ["ClienteKukaVarProxy", "PasarelaRobot"]
