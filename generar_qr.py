import argparse, os, sqlite3, secrets
from datetime import datetime, timezone
import qrcode

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE_DIR,"carteles.db")
SALIDA=os.path.join(BASE_DIR,"qr_generados")

def init_db(db):
    db.execute("""CREATE TABLE IF NOT EXISTS codigos (codigo TEXT PRIMARY KEY,destino TEXT,nombre_cliente TEXT,clicks INTEGER NOT NULL DEFAULT 0,qr_clicks INTEGER NOT NULL DEFAULT 0,nfc_clicks INTEGER NOT NULL DEFAULT 0,otros_clicks INTEGER NOT NULL DEFAULT 0,creado_en TEXT NOT NULL,ultimo_click TEXT)""")
    cols={r[1] for r in db.execute("PRAGMA table_info(codigos)")}
    for name in ("qr_clicks","nfc_clicks","otros_clicks"):
        if name not in cols: db.execute(f"ALTER TABLE codigos ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0")

def code(db):
    while True:
        c=secrets.token_hex(3).upper()
        if not db.execute("SELECT 1 FROM codigos WHERE codigo=?",(c,)).fetchone(): return c

def main():
    p=argparse.ArgumentParser(description="Genera QR únicos con seguimiento QR.")
    p.add_argument("--dominio",required=True);p.add_argument("--cantidad",type=int,default=10)
    a=p.parse_args(); os.makedirs(SALIDA,exist_ok=True)
    db=sqlite3.connect(DB_PATH);init_db(db)
    for _ in range(max(1,min(a.cantidad,500))):
        c=code(db);url=f"{a.dominio.rstrip('/')}/r/{c}?src=qr"
        qrcode.make(url).save(os.path.join(SALIDA,f"{c}.png"))
        db.execute("INSERT INTO codigos (codigo,destino,nombre_cliente,clicks,qr_clicks,nfc_clicks,otros_clicks,creado_en) VALUES (?,NULL,NULL,0,0,0,0,?)",(c,datetime.now(timezone.utc).isoformat()))
        print(c,"->",url)
    db.commit();db.close()
if __name__=="__main__":main()
