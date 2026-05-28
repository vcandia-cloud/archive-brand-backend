# Archive Brand BA — Backend

## Archivos
- `main.py` — API REST y cron job automático
- `scraper.py` — extrae productos de cada tienda
- `database.py` — conexión a Supabase
- `requirements.txt` — dependencias
- `.env` — credenciales (no subir a GitHub)

## Endpoints
- `GET /productos` — todos los productos activos
- `GET /marcas` — todas las marcas
- `POST /sync` — sincronizar todo manualmente
- `GET /logs` — ver historial de sincronizaciones

## Variables de entorno en Render
SUPABASE_URL = https://tdknndjtxifdvjzkzdio.supabase.co
SUPABASE_KEY = tu_clave_aqui
