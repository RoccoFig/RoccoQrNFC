"""
Genera un lote de imágenes QR únicas, listas para mandar a imprenta.

Cada QR generado apunta a: TU-DOMINIO/r/CODIGO
Los códigos quedan guardados en la misma base de datos que usa app.py,
sin destino asignado todavía (los configurás después, desde /admin,
cuando vendas cada cartel).

Uso:
    python generar_qr.py --dominio https://tudominio.com --cantidad 50

Esto crea una carpeta "qr_generados/" con un PNG por código
(ej: A1B2C3.png), que es lo que le mandás a la imprenta.
"""

import argparse
import os
import sqlite3
import secrets
from datetime import datetime, timezone

import qrcode

DB_PATH = os.path.join(os.path.dirname(__file__), "carteles.db")
SALIDA = os.path.join(os.path.dirname(__file__), "qr_generados")


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS codigos (
            codigo TEXT PRIMARY KEY,
            destino TEXT,
            nombre_cliente TEXT,
            clicks INTEGER NOT NULL DEFAULT 0,
            creado_en TEXT NOT NULL,
            ultimo_click TEXT
        )
    """)
    db.commit()
    return db


def generar_codigo_unico(db):
    while True:
        codigo = secrets.token_hex(3).upper()
        existe = db.execute(
            "SELECT 1 FROM codigos WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not existe:
            return codigo


def main():
    parser = argparse.ArgumentParser(
        description="Genera un lote de códigos QR únicos para los carteles."
    )
    parser.add_argument(
        "--dominio", required=True,
        help="Dominio donde vas a alojar la app, ej: https://tudominio.com"
    )
    parser.add_argument(
        "--cantidad", type=int, default=10,
        help="Cantidad de QR a generar (default: 10)"
    )
    args = parser.parse_args()

    os.makedirs(SALIDA, exist_ok=True)
    db = init_db()

    generados = []
    for _ in range(args.cantidad):
        codigo = generar_codigo_unico(db)
        url = f"{args.dominio.rstrip('/')}/r/{codigo}"

        img = qrcode.make(url)
        ruta = os.path.join(SALIDA, f"{codigo}.png")
        img.save(ruta)

        db.execute(
            "INSERT INTO codigos (codigo, destino, nombre_cliente, clicks, creado_en) "
            "VALUES (?, NULL, NULL, 0, ?)",
            (codigo, datetime.now(timezone.utc).isoformat()),
        )
        generados.append((codigo, url))

    db.commit()
    db.close()

    print(f"\nSe generaron {len(generados)} códigos QR en la carpeta: {SALIDA}\n")
    for codigo, url in generados:
        print(f"  {codigo}  ->  {url}")
    print(
        "\nEstos códigos ya quedaron guardados en carteles.db sin destino "
        "asignado. Configurá el destino de cada uno desde el panel /admin "
        "cuando vendas cada cartel."
    )


if __name__ == "__main__":
    main()
