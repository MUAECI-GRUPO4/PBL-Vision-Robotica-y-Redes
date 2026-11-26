#!/usr/bin/env bash
# Emite el certificado de un nodo firmado por la CA del grupo (tarea 1.2, requisito S1).
#
# Uso:   ./generar_nodo.sh <nombre> <server|client> "<SAN>"
#   Ej.: ./generar_nodo.sh servidor   server "DNS:servidor.pbl1.local,IP:10.0.0.10"
#        ./generar_nodo.sh pasarela_v client "DNS:pasarela-v.pbl1.local"
#
# Variables opcionales:
#   CA_DIR  dónde están ca.crt y private/ca.key   (por defecto ./salida)
#   OUT     dónde se dejan el certificado y la clave (por defecto ./salida)
#   DIAS    validez del certificado en días         (por defecto 365)
#
# Resultado:
#   <OUT>/<nombre>.crt           certificado del nodo
#   <OUT>/private/<nombre>.key   clave privada del nodo (permisos 600, nunca al repositorio)
set -euo pipefail
# Ver generar_ca.sh: evita que Git Bash convierta "/O=.../CN=..." en una ruta de Windows.
export MSYS_NO_PATHCONV=1

if [ $# -ne 3 ]; then
  echo "Uso: $0 <nombre> <server|client> \"<SAN>\"" >&2
  exit 1
fi
NOMBRE=$1
ROL=$2
SAN=$3
CA_DIR=${CA_DIR:-./salida}
OUT=${OUT:-./salida}
DIAS=${DIAS:-365}

# El uso extendido (EKU) limita el certificado a su papel en TLS
case "$ROL" in
  server) EKU=serverAuth ;;
  client) EKU=clientAuth ;;
  *) echo "Rol no válido: '$ROL' (usa server o client)" >&2; exit 1 ;;
esac

if [ ! -f "$CA_DIR/ca.crt" ] || [ ! -f "$CA_DIR/private/ca.key" ]; then
  echo "No hay CA en $CA_DIR: ejecuta antes generar_ca.sh" >&2
  exit 1
fi

# CN legible: el primer nombre DNS del SAN (si no hay, el nombre del nodo).
# La identidad que se verifica en TLS es el SAN, no el CN.
CN=$(printf '%s\n' "$SAN" | tr ',' '\n' | sed -n 's/^ *DNS://p' | head -n 1)
CN=${CN:-$NOMBRE}

mkdir -p "$OUT/private"
chmod 700 "$OUT/private"

# 1) Clave privada del nodo (P-256, igual que la CA)
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$OUT/private/$NOMBRE.key"
chmod 600 "$OUT/private/$NOMBRE.key"

# 2) Petición de firma (CSR) con la identidad del nodo
#    Los temporales van dentro de $OUT y no en /tmp: en Git Bash, openssl.exe es un programa
#    de Windows y no entiende rutas como /tmp/... (MSYS_NO_PATHCONV impide convertirlas).
TMPD=$(mktemp -d "$OUT/.tmp.XXXXXX")
trap 'rm -rf "$TMPD"' EXIT
CSR=$TMPD/$NOMBRE.csr
EXT=$TMPD/$NOMBRE.ext
openssl req -new -key "$OUT/private/$NOMBRE.key" -subj "/O=PBL1 Grupo 4/CN=$CN" -out "$CSR"

# 3) Extensiones del certificado: el SAN es la identidad que comprueba el otro extremo
cat > "$EXT" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=$EKU
subjectAltName=$SAN
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid
EOF

# 4) La CA firma el certificado
openssl x509 -req -in "$CSR" -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/private/ca.key" \
  -CAcreateserial -days "$DIAS" -sha256 -extfile "$EXT" -out "$OUT/$NOMBRE.crt"

echo "Certificado emitido: $OUT/$NOMBRE.crt ($EKU, $SAN)"
