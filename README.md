# PBL Visión, Robótica y Redes (MUAECI, Grupo 4)

Comunicación segura cámara--robot con clasificación por OCR. Este repositorio contiene la parte de Redes de Comunicación Industriales: pasarelas, servidor intermedio con TLS mutuo e interfaz web de supervisión.

```
cámaras ─GigE─ PC visión ─ pasarela-V ══TLS══╗
                                              ╠═ servidor intermedio ══ interfaz web
robot KUKA ─KukaVarProxy─ pasarela-R ══TLS══╝
```

| Carpeta | Contenido |
|---|---|
| `docs/` | contratos de interfaz ([`contratos.md`](docs/contratos.md)) y diagramas |
| `config/` | configuración de ejemplo; la real es `config/<nodo>.ini` y no se versiona |
| `src/proto` | librería común: delimitación, tipos de mensaje, confirmaciones y latidos |
| `src/server`, `src/gw_robot`, `src/vision_gw` | servidor intermedio, pasarela del robot y pasarela de visión |
| `src/web` | interfaz web de supervisión |
| `src/pki` | scripts de la CA propia y de los certificados (sin claves privadas) |
| `src/sims` | simuladores de visión y de robot |
| `deploy/` | servicios (systemd o Compose) |
| `tests/` | pruebas |

Pruebas (solo biblioteca estándar, Python 3.10 o superior), desde la raíz:

```
python -m unittest discover -s tests
```

Normas de Git en [`CONTRIBUTING.md`](CONTRIBUTING.md).
