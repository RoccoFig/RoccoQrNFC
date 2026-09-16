# RF Link — Carteles NFC + QR

Sistema Flask para vender carteles con QR impreso y chip NFC. Ambos usan el mismo código, pero incorporan `?src=qr` y `?src=nfc` para medir accesos por separado.

## Flujo
- QR: `https://tu-dominio/r/CODIGO?src=qr`
- NFC: `https://tu-dominio/r/CODIGO?src=nfc`
- Destino editable desde `/admin` sin cambiar el QR ni regrabar el NFC.

## Local
```bash
pip install -r requirements.txt
python app.py
```
Panel: `http://127.0.0.1:5000/admin`

## Variables recomendadas en Railway
- `ADMIN_PASSWORD`: contraseña fuerte.
- `SECRET_KEY`: valor aleatorio fijo.
- `PUBLIC_BASE_URL`: URL pública final, por ejemplo `https://rf-link.up.railway.app` o tu dominio propio. Esto garantiza que los QR generados usen siempre el dominio correcto.

La base existente se migra automáticamente agregando contadores `qr_clicks`, `nfc_clicks` y `otros_clicks`; no borra los registros viejos.

## NFC Tools
Abrí un cartel en **Configurar**, copiá “Enlace para NFC” y grabalo como registro URL/URI. No grabes directamente Instagram/Google si querés conservar la posibilidad de cambiar el destino desde el panel.
