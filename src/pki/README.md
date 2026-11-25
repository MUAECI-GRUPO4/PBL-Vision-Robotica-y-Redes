# PKI propia y TLS mutuo (tarea 1.2, DG)

CA del grupo y un certificado por nodo con SAN para los dos conductos TLS (requisitos S1–S6).
Aquí solo van los **scripts**: las claves privadas y los certificados generados no se versionan.

## Contenido previsto

| Fichero | Commit | Qué hace |
|---|---|---|
| `generar_ca.sh` | C1 | Crea la CA propia (ECDSA P-256, 10 años) |
| `generar_nodo.sh` | C1 | Emite el certificado de un nodo con su SAN y su uso (`serverAuth` o `clientAuth`) |
| `generar_todo.sh` | C2 | Emite los certificados del servidor y de las dos pasarelas |
| `tls_comun.py` | C3 | Contextos TLS mutuos reutilizables para el servidor y las pasarelas |
| `generar_pruebas.sh` | C4 | Certificados inválidos para las pruebas de rechazo (CA ajena, caducado, autofirmado, nombre incorrecto) |

## Propuesta de nombres y rutas (pendiente de acordar con Di y Se)

Sigue la sección `[tls]` de [`config/ejemplo.ini`](../../config/ejemplo.ini): cada nodo lee sus ficheros de `certs/`, que no se versiona.

| Nodo | SAN propuesto | Rol TLS | Ficheros en el nodo |
|---|---|---|---|
| Servidor intermedio | `DNS:servidor.pbl1.local` | servidor en los dos conductos (puertos 5001 y 5002) | `certs/ca.crt`, `certs/servidor.crt`, `certs/servidor.key` |
| Pasarela de visión | `DNS:pasarela-v.pbl1.local` | cliente del conducto 1 | `certs/ca.crt`, `certs/pasarela_v.crt`, `certs/pasarela_v.key` |
| Pasarela del robot | `DNS:pasarela-r.pbl1.local` | cliente del conducto 2 | `certs/ca.crt`, `certs/pasarela_r.crt`, `certs/pasarela_r.key` |

- Se añadirá la IP de cada equipo al SAN cuando esté fijada.
- El servidor comprobará el SAN del cliente según el puerto: en el 5001 solo acepta `pasarela-v`; en el 5002, solo `pasarela-r`.
- Hasta el hito H3 los conductos van en claro (acuerdo del reparto); después basta con apuntar la configuración a los certificados.

## Reglas

- `ca.key` no sale del equipo de quien gestiona la CA: a cada nodo solo llegan `ca.crt`, su `.crt` y su `.key`.
- Claves privadas con permisos `600` y carpeta `certs/` con `700`.
- Nada de `CERT_NONE` ni `check_hostname=False`: si falla la verificación, se arregla el certificado.
