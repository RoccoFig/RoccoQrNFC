# Sistema de carteles NFC/QR

Este proyecto resuelve el problema de imprimir QR genéricos por mayor, pero
que cada uno pueda redirigir a un destino distinto (Instagram, Google Maps,
lo que sea) configurado después de imprimir.

## Cómo funciona

1. Cada QR impreso apunta siempre a la misma estructura de URL:
   `https://TU-DOMINIO/r/CODIGO` (ej: `https://tudominio.com/r/A1B2C3`).
2. Esa URL nunca cambia. Lo que se puede cambiar en cualquier momento,
   desde el panel de administración, es **a dónde redirige** cada código.
3. Así podés generar e imprimir un lote grande de una sola vez, y recién
   configurar el destino cuando vendas cada cartel a un comercio.
4. La misma lógica sirve para el chip NFC: en vez de grabarle el link de
   Instagram directo, le grabás `https://TU-DOMINIO/r/A1B2C3`. De esa forma
   un mismo panel controla el NFC y el QR de un mismo cartel a la vez.

## Archivos

- `app.py` — la app web: la redirección pública (`/r/<codigo>`) y el panel
  de administración (`/admin`).
- `generar_qr.py` — script de línea de comandos para generar en lote las
  imágenes PNG de los QR, listas para mandar a imprenta.
- `templates/` — las páginas HTML del panel.
- `carteles.db` — base de datos SQLite (se crea sola la primera vez).

## Probarlo en tu computadora

```bash
pip install -r requirements.txt
python app.py
```

Abrí `http://127.0.0.1:5000/admin` — contraseña por defecto: `cambiame123`
(cambiala, ver más abajo).

Desde ahí podés:
- Generar códigos nuevos (botón "Generar").
- Ver la lista de códigos, cuáles tienen destino configurado y cuántos
  clicks tuvo cada uno.
- Configurar o cambiar el destino de cualquier código en cualquier momento.

## Generar el lote de QR para la imprenta

Una vez que tengas un dominio (ver siguiente sección), corré:

```bash
python generar_qr.py --dominio https://tudominio.com --cantidad 100
```

Esto crea la carpeta `qr_generados/` con un PNG por código (ej:
`A1B2C3.png`), y guarda esos 100 códigos en la base de datos sin destino
todavía. Esas imágenes son las que le mandás a la imprenta para el diseño
del cartel.

## Poner esto en internet (necesario para que los QR funcionen de verdad)

Un QR apunta a una URL pública, así que la app tiene que estar corriendo en
algún servidor con dominio propio, no solo en tu computadora. Opciones
simples y con plan gratuito para arrancar:

- **Render** (render.com) — subís el proyecto desde GitHub, detecta que es
  Flask y lo deja corriendo en una URL tipo `tuapp.onrender.com`.
- **Railway** (railway.app) — similar a Render, muy simple para proyectos
  chicos.
- **PythonAnywhere** — pensado específicamente para apps Python/Flask
  chicas, fácil de configurar sin usar la terminal.

En cualquiera de los tres, después podés conectar un dominio propio
(ej: `tudominio.com`) si querés algo más corto y con tu marca, en vez del
subdominio gratuito que te dan.

Para probar el QR **antes** de desplegar en serio, podés usar `ngrok` para
exponer temporalmente tu `http://127.0.0.1:5000` con una URL pública de
prueba.

## Importante antes de usarlo con clientes reales

- Cambiá la contraseña del panel: definí la variable de entorno
  `ADMIN_PASSWORD` con una contraseña tuya (en vez de `cambiame123`).
- Definí también `SECRET_KEY` con un valor fijo propio (si no, cada vez que
  reinicies el servidor se cierran las sesiones de todos).
- Hacé backup de `carteles.db` de vez en cuando: ahí vive la relación
  código → destino de todos los carteles vendidos.

## Ideas para más adelante

- Mostrarle al cliente cuántos escaneos tuvo su cartel (ya se está
  guardando el contador de `clicks`), como valor agregado del servicio.
- Permitir que un mismo código tenga varios destinos según franja horaria
  o día (ej: Instagram de semana, promo de fin de semana).
- Exportar el listado de códigos sin configurar como planilla, para llevar
  el control de stock impreso vs. vendido.
