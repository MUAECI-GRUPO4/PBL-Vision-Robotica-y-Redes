"""Servidor intermedio de PBL 1 (tarea 1.3).

Une los dos conductos: la pasarela de visión (conducto 1) y la pasarela del
robot (conducto 2), mantiene el estado de los enlaces y registra eventos.
"""

from .servidor import Enlace, ServidorIntermedio

__all__ = ["Enlace", "ServidorIntermedio"]
