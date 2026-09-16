import os
import sqlite3
import secrets
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse
def tipo_destino(destino):
    try:
        parsed = urlparse(destino)
        host = (parsed.netloc or "").lower().split(":")[0]
    except Exception:
        return "otro"

    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "instagram"

    dominios_google = (
        "google.com",
        "google.com.ar",
        "maps.google.com",
        "maps.app.goo.gl",
        "goo.gl",
        "g.page"
    )

    if any(host == d or host.endswith("." + d) for d in dominios_google):
        return "google"

    return "otro"

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
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def column_names(db, table):
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db():
    """Crea la tabla y migra bases anteriores sin borrar datos."""
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS codigos (
            codigo TEXT PRIMARY KEY,
            destino TEXT,
            nombre_cliente TEXT,
            clicks INTEGER NOT NULL DEFAULT 0,
            qr_clicks INTEGER NOT NULL DEFAULT 0,
            nfc_clicks INTEGER NOT NULL DEFAULT 0,
            otros_clicks INTEGER NOT NULL DEFAULT 0,
            creado_en TEXT NOT NULL,
            ultimo_click TEXT
        )
    """)

    cols = column_names(db, "codigos")
    migrations = {
        "qr_clicks": "INTEGER NOT NULL DEFAULT 0",
        "nfc_clicks": "INTEGER NOT NULL DEFAULT 0",
        "otros_clicks": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, definition in migrations.items():
        if name not in cols:
            db.execute(f"ALTER TABLE codigos ADD COLUMN {name} {definition}")

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


def normalizar_destino(raw):
    destino = (raw or "").strip()
    if not destino:
        return ""
    if not destino.lower().startswith(("http://", "https://")):
        destino = "https://" + destino
    parsed = urlparse(destino)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Ingresá una URL válida, por ejemplo https://instagram.com/usuario")
    return destino


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logueado"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def public_base_url():
    configured = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    return configured or request.host_url.rstrip("/")


def enlace_publico(codigo, source=None):
    base = public_base_url()
    url = f"{base}/r/{codigo}"
    if source:
        url += f"?src={source}"
    return url


def crear_qr(codigo):
    url = enlace_publico(codigo, "qr")
    qr = qrcode.QRCode(version=None, box_size=12, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(
        os.path.join(QR_DIR, f"{codigo}.png")
    )


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/r/<codigo>")
def redirigir(codigo):
    codigo = codigo.upper().strip()
    db = get_db()
    fila = db.execute("SELECT * FROM codigos WHERE codigo = ?", (codigo,)).fetchone()
    if fila is None:
        abort(404)
    if not fila["destino"]:
        return render_template("sin_configurar.html", codigo=codigo), 200

    src = request.args.get("src", "").lower()
    if src == "qr":
        source_column = "qr_clicks"
    elif src == "nfc":
        source_column = "nfc_clicks"
    else:
        source_column = "otros_clicks"

    db.execute(
        f"UPDATE codigos SET clicks = clicks + 1, {source_column} = {source_column} + 1, ultimo_click = ? WHERE codigo = ?",
        (now_iso(), codigo),
    )
    db.commit()
    destino = fila["destino"]

    return render_template(
        "redirigiendo.html",
        destino=destino,
        tipo=tipo_destino(destino),
        codigo=codigo,
    )


@app.route("/qr/<codigo>")
@login_required
def ver_qr(codigo):
    codigo = codigo.upper().strip()
    nombre = f"{codigo}.png"
    ruta = os.path.join(QR_DIR, nombre)
    if not os.path.exists(ruta):
        fila = get_db().execute("SELECT codigo FROM codigos WHERE codigo = ?", (codigo,)).fetchone()
        if fila is None:
            abort(404)
        crear_qr(codigo)
    return send_from_directory(QR_DIR, nombre)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("logueado"):
        return redirect(url_for("admin_panel"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if secrets.compare_digest(password, ADMIN_PASSWORD):
            session["logueado"] = True
            destino = request.args.get("next")
            if not destino or not destino.startswith("/") or destino.startswith("//"):
                destino = url_for("admin_panel")
            return redirect(destino)
        flash("Contraseña incorrecta.", "error")
    return render_template("login.html")


@app.route("/admin/logout", methods=["POST"])
@login_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_panel():
    db = get_db()
    buscar = request.args.get("q", "").strip()
    estado = request.args.get("estado", "todos")

    sql = "SELECT * FROM codigos WHERE 1=1"
    params = []
    if buscar:
        sql += " AND (codigo LIKE ? OR nombre_cliente LIKE ? OR destino LIKE ?)"
        like = f"%{buscar}%"
        params.extend([like, like, like])
    if estado == "configurados":
        sql += " AND destino IS NOT NULL AND TRIM(destino) <> ''"
    elif estado == "pendientes":
        sql += " AND (destino IS NULL OR TRIM(destino) = '')"
    sql += " ORDER BY creado_en DESC"

    codigos = db.execute(sql, params).fetchall()
    stats = db.execute("""
        SELECT
            COUNT(*) total,
            SUM(CASE WHEN destino IS NOT NULL AND TRIM(destino) <> '' THEN 1 ELSE 0 END) configurados,
            SUM(CASE WHEN destino IS NULL OR TRIM(destino) = '' THEN 1 ELSE 0 END) pendientes,
            COALESCE(SUM(clicks), 0) clicks,
            COALESCE(SUM(qr_clicks), 0) qr_clicks,
            COALESCE(SUM(nfc_clicks), 0) nfc_clicks
        FROM codigos
    """).fetchone()

    return render_template(
        "panel.html", codigos=codigos, stats=stats,
        buscar=buscar, estado=estado, base_url=public_base_url()
    )


@app.route("/admin/configurar/<codigo>", methods=["GET", "POST"])
@login_required
def configurar(codigo):
    codigo = codigo.upper().strip()
    db = get_db()
    fila = db.execute("SELECT * FROM codigos WHERE codigo = ?", (codigo,)).fetchone()
    if fila is None:
        abort(404)

    if request.method == "POST":
        nombre_cliente = request.form.get("nombre_cliente", "").strip()[:150]
        try:
            destino = normalizar_destino(request.form.get("destino", ""))
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template(
                "configurar.html", fila=fila,
                nfc_url=enlace_publico(codigo, "nfc"),
                qr_url=enlace_publico(codigo, "qr")
            ), 400

        db.execute(
            "UPDATE codigos SET destino = ?, nombre_cliente = ? WHERE codigo = ?",
            (destino or None, nombre_cliente or None, codigo),
        )
        db.commit()
        flash(f"Código {codigo} actualizado correctamente.", "success")
        return redirect(url_for("admin_panel"))

    return render_template(
        "configurar.html", fila=fila,
        nfc_url=enlace_publico(codigo, "nfc"),
        qr_url=enlace_publico(codigo, "qr")
    )


@app.route("/admin/generar", methods=["POST"])
@login_required
def generar():
    try:
        cantidad = int(request.form.get("cantidad", 10))
    except (TypeError, ValueError):
        cantidad = 10
    cantidad = max(1, min(cantidad, 500))

    db = get_db()
    creados = []
    for _ in range(cantidad):
        codigo = generar_codigo_unico(db)
        db.execute(
            "INSERT INTO codigos (codigo, destino, nombre_cliente, clicks, qr_clicks, nfc_clicks, otros_clicks, creado_en) "
            "VALUES (?, NULL, NULL, 0, 0, 0, 0, ?)",
            (codigo, now_iso()),
        )
        crear_qr(codigo)
        creados.append(codigo)
    db.commit()

    flash(f"Se generaron {len(creados)} carteles nuevos.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/regenerar-qr/<codigo>", methods=["POST"])
@login_required
def regenerar_qr(codigo):
    codigo = codigo.upper().strip()
    fila = get_db().execute("SELECT codigo FROM codigos WHERE codigo = ?", (codigo,)).fetchone()
    if fila is None:
        abort(404)
    crear_qr(codigo)
    flash(f"QR de {codigo} regenerado con seguimiento QR.", "success")
    return redirect(url_for("configurar", codigo=codigo))


@app.route("/admin/eliminar/<codigo>", methods=["POST"])
@login_required
def eliminar(codigo):
    codigo = codigo.upper().strip()
    db = get_db()
    fila = db.execute("SELECT codigo FROM codigos WHERE codigo = ?", (codigo,)).fetchone()
    if fila is None:
        abort(404)
    db.execute("DELETE FROM codigos WHERE codigo = ?", (codigo,))
    db.commit()
    archivo_qr = os.path.join(QR_DIR, f"{codigo}.png")
    if os.path.exists(archivo_qr):
        os.remove(archivo_qr)
    flash(f"Código {codigo} eliminado.", "success")
    return redirect(url_for("admin_panel"))


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", codigo=404, mensaje="La página o el código solicitado no existe."), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("error.html", codigo=500, mensaje="Ocurrió un error interno. Intentá nuevamente."), 500


# También se ejecuta cuando Railway/Gunicorn importa app.py.
init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
