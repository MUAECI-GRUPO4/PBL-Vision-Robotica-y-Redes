#!/usr/bin/env bash
# Crea la autoridad de certificación (CA) propia del grupo (tarea 1.2, requisito S1).
#
# Uso:   ./generar_ca.sh [directorio_salida] ["Nombre de la CA"]
#        directorio_salida: por defecto $OUT o ./salida (ignorado por git)
#
# Resultado:
#   <salida>/ca.crt           certificado público de la CA: se copia a todos los nodos
#   <salida>/private/ca.key   clave privada de la CA: NUNCA sale del equipo que gestiona la PKI
set -euo pipefail
# Git Bash (Windows) convierte los argumentos que empiezan por "/" en rutas de Windows
# y estropearía el -subj "/O=.../CN=...". En Linux esta variable no tiene efecto.
export MSYS_NO_PATHCONV=1

OUT=${1:-${OUT:-./salida}}
NOMBRE=${2:-"PBL1 Grupo 4 CA raiz"}
DIAS=${DIAS:-3650}

# Regenerar la CA invalida todos los certificados emitidos con ella: se exige confirmarlo.
if [ -e "$OUT/private/ca.key" ] && [ "${FORZAR:-0}" != 1 ]; then
  echo "Ya existe una CA en $OUT. Para sustituirla: FORZAR=1 $0 $*" >&2
  exit 1
fi

mkdir -p "$OUT/private"
chmod 700 "$OUT/private"

# 1) Clave privada de la CA: curva elíptica P-256 (claves y firmas pequeñas, handshake rápido)
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$OUT/private/ca.key"
chmod 600 "$OUT/private/ca.key"

# 2) Certificado autofirmado de la CA
#    CA:TRUE      -> puede firmar otros certificados
#    pathlen:0    -> no puede haber CA intermedias por debajo
#    keyCertSign  -> la clave solo sirve para firmar certificados (y listas de revocación)
openssl req -x509 -new -key "$OUT/private/ca.key" -sha256 -days "$DIAS" \
  -subj "/O=PBL1 Grupo 4/CN=$NOMBRE" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash" \
  -out "$OUT/ca.crt"

echo "CA creada: $OUT/ca.crt (clave en $OUT/private/ca.key)"
