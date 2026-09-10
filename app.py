import os
import sqlite3
import secrets
from datetime import datetime, timezone
from functools import wraps

import qrcode

from flask import (
    Flask, g, request, redirect, render_template,
    session, url_for, flash, abort, send_from_directory
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "carteles.db")
QR_DIR = os.path.join(BASE_DIR, "qr_generados")
os.makedirs(QR_DIR, exist_ok=True)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "cambiame123")
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(16))

app = Flask(__name__)
app.secret_key = SECRET_KEY

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

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
    db.close()

def generar_codigo_unico(db):
    while True:
        codigo = secrets.token_hex(3).upper()
        existe = db.execute(
            "SELECT 1 FROM codigos WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not existe:
            return codigo

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logueado"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

@app.route("/")
def home():
    return "Sistema de carteles NFC/QR. Panel de administración en /admin"

@app.route("/r/<codigo>")
def redirigir(codigo):
    codigo = codigo.upper()
    db = get_db()
    fila = db.execute(
        "SELECT * FROM codigos WHERE codigo = ?", (codigo,)
    ).fetchone()

    if fila is None:
        abort(404)

    if not fila["destino"]:
        return render_template("sin_configurar.html", codigo=codigo)

    db.execute(
        "UPDATE codigos SET clicks = clicks + 1, ultimo_click = ? WHERE codigo = ?",
        (datetime.now(timezone.utc).isoformat(), codigo),
    )
    db.commit()
    return redirect(fila["destino"], code=302)

@app.route("/qr/<codigo>")
@login_required
def ver_qr(codigo):
    codigo = codigo.upper()
    nombre = f"{codigo}.png"
    ruta = os.path.join(QR_DIR, nombre)

    if not os.path.exists(ruta):
        abort(404)

    return send_from_directory(QR_DIR, nombre)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logueado"] = True
            destino = request.args.get("next") or url_for("admin_panel")
            return redirect(destino)
        flash("Contraseña incorrecta.")
    return render_template("login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("logueado", None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
@login_required
def admin_panel():
    db = get_db()
    codigos = db.execute(
        "SELECT * FROM codigos ORDER BY creado_en DESC"
    ).fetchall()
    return render_template("panel.html", codigos=codigos)

@app.route("/admin/configurar/<codigo>", methods=["GET", "POST"])
@login_required
def configurar(codigo):
    codigo = codigo.upper()
    db = get_db()
    fila = db.execute(
        "SELECT * FROM codigos WHERE codigo = ?", (codigo,)
    ).fetchone()

    if fila is None:
        abort(404)

    if request.method == "POST":
        destino = request.form.get("destino", "").strip()
        nombre_cliente = request.form.get("nombre_cliente", "").strip()

        if destino and not destino.startswith(("http://", "https://")):
            destino = "https://" + destino

        db.execute(
            "UPDATE codigos SET destino = ?, nombre_cliente = ? WHERE codigo = ?",
            (destino, nombre_cliente, codigo),
        )
        db.commit()

        flash(f"Código {codigo} actualizado.")
        return redirect(url_for("admin_panel"))

    return render_template("configurar.html", fila=fila)

@app.route("/admin/generar", methods=["POST"])
@login_required
def generar():
    try:
        cantidad = int(request.form.get("cantidad", 10))
    except ValueError:
        cantidad = 10

    cantidad = max(1, min(cantidad, 500))

    db = get_db()
    creados = []
    dominio = request.host_url.rstrip("/")

    for _ in range(cantidad):
        codigo = generar_codigo_unico(db)

        db.execute(
            "INSERT INTO codigos (codigo, destino, nombre_cliente, clicks, creado_en) "
            "VALUES (?, NULL, NULL, 0, ?)",
            (codigo, datetime.now(timezone.utc).isoformat()),
        )

        url_qr = f"{dominio}/r/{codigo}"
        imagen_qr = qrcode.make(url_qr)
        imagen_qr.save(os.path.join(QR_DIR, f"{codigo}.png"))

        creados.append(codigo)

    db.commit()

    flash(
        f"Se generaron {len(creados)} códigos y sus QR: "
        f"{', '.join(creados)}"
    )
    return redirect(url_for("admin_panel"))


@app.route("/admin/eliminar/<codigo>", methods=["POST"])
@login_required
def eliminar(codigo):
    codigo = codigo.upper()
    db = get_db()

    fila = db.execute(
        "SELECT * FROM codigos WHERE codigo = ?", (codigo,)
    ).fetchone()

    if fila is None:
        abort(404)

    db.execute("DELETE FROM codigos WHERE codigo = ?", (codigo,))
    db.commit()

    archivo_qr = os.path.join(QR_DIR, f"{codigo}.png")
    if os.path.exists(archivo_qr):
        os.remove(archivo_qr)

    flash(f"Código {codigo} eliminado correctamente.")
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
