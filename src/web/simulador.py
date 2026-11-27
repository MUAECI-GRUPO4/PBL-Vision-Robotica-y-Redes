"""Simulación de la variable de estado del ciclo de pieza (estado_g4), sin red.

Valores (docs/variables-krl.md, tarea 1.6):
    0  reposo: el robot recoge la pieza de la cinta
    1  pieza delante de la cámara, espera orden
    2  girar 15° el eje 6 (la pasarela-R escribe 2, el robot vuelve a 1)
    3  pieza buena -> rutina de pieza buena y vuelve a 0
    4  pieza mala  -> rutina de pieza mala y vuelve a 0

Dos simuladores:
  - SimuladorProceso: ciclos sin fin con giros y resultado al azar (demostración).
  - SimuladorEscenario: lista fija de pasos (pruebas). Sin hilos: el valor se
    calcula en cada leer() a partir del reloj.
"""

import random
import time
from collections import deque


class SimuladorProceso:
    def __init__(self, ratio_buenas=0.85, giros_min=2, giros_max=5,
                 t_recoger=2.5, t_camara=1.2, t_giro=0.9, t_dejar=2.5, velocidad=1.0):
        self.ratio_buenas = ratio_buenas
        self.giros_min, self.giros_max = giros_min, giros_max
        self.t_recoger, self.t_camara = t_recoger, t_camara
        self.t_giro, self.t_dejar = t_giro, t_dejar
        self.velocidad = max(0.05, float(velocidad))
        self._cola = deque()
        self._valor = 0
        self._fin_paso = time.monotonic()

    def _ciclo_nuevo(self):
        pasos = [(0, self.t_recoger), (1, self.t_camara)]
        for _ in range(random.randint(self.giros_min, self.giros_max)):
            pasos += [(2, self.t_giro), (1, self.t_camara)]
        pasos.append((3 if random.random() < self.ratio_buenas else 4, self.t_dejar))
        return pasos

    def leer(self):
        ahora = time.monotonic()
        while ahora >= self._fin_paso:
            if not self._cola:
                self._cola.extend(self._ciclo_nuevo())
            self._valor, duracion = self._cola.popleft()
            self._fin_paso += duracion / self.velocidad
        return self._valor


def ciclo_pieza(resultado, giros=2, t_recoger=2.5, t_camara=1.2, t_giro=0.9, t_dejar=2.5):
    """Un ciclo completo de pieza como [(valor, segundos), ...].

    0 -> 1 -> (2 -> 1) x giros -> resultado (3 o 4)
    """
    pasos = [(0, t_recoger), (1, t_camara)]
    for _ in range(giros):
        pasos += [(2, t_giro), (1, t_camara)]
    pasos.append((resultado, t_dejar))
    return pasos


ESCENARIOS = {
    # una pieza buena (3) y vuelta a reposo
    "buena": ciclo_pieza(3) + [(0, 3.0)],
    # una pieza mala (4) y vuelta a reposo
    "mala": ciclo_pieza(4) + [(0, 3.0)],
    # pieza 1 buena, pieza 2 mala, y vuelta a reposo
    "ambas": ciclo_pieza(3) + ciclo_pieza(4, giros=3) + [(0, 3.0)],
}


class SimuladorEscenario:
    """Reproduce una lista fija de pasos (valor, duración en s).

    repetir=False -> al terminar se queda en el último valor (prueba)
    repetir=True  -> vuelve a empezar (pantalla de demostración)
    """

    def __init__(self, pasos, repetir=True, velocidad=1.0, reloj=time.monotonic):
        if isinstance(pasos, str):
            pasos = ESCENARIOS[pasos]
        self.pasos = list(pasos)
        self.repetir = repetir
        self.velocidad = max(0.05, float(velocidad))
        self.reloj = reloj
        self._t0 = reloj()
        self.duracion = sum(d for _, d in self.pasos) / self.velocidad

    @property
    def terminado(self):
        return not self.repetir and self.reloj() - self._t0 >= self.duracion

    def leer(self):
        t = self.reloj() - self._t0
        if self.repetir:
            t %= self.duracion
        for valor, duracion in self.pasos:
            t -= duracion / self.velocidad
            if t < 0:
                return valor
        return self.pasos[-1][0]
