# ════════════════════════════════════════════════════
#  main.py — API REST + cron job automático
# ════════════════════════════════════════════════════
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from database import supabase
from scraper import sincronizar_todo
import uvicorn

app = FastAPI(title="Archive Brand BA API")

# ── CORS — permite que el frontend pueda consumir la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── CRON JOB — se ejecuta automáticamente cada 24 horas
scheduler = BackgroundScheduler()
scheduler.add_job(sincronizar_todo, "interval", hours=24)
scheduler.start()

# ════════════════════════════════════════════════════
#  ENDPOINTS
# ════════════════════════════════════════════════════

# GET /productos — devuelve todos los productos activos
# Se puede filtrar por: categoria, marca, subcategoria, q (búsqueda)
@app.get("/productos")
def get_productos(
    categoria: str = None,
    marca: str = None,
    subcategoria: str = None,
    q: str = None,
    orden: str = None,  # 'precio_asc' | 'precio_desc' | 'marca'
    limit: int = 500,
):
    query = supabase.table("productos").select(
        "id, nombre, precio, imagen_url, producto_url, categoria, subcategoria, marcas(nombre)"
    ).eq("activo", True)

    if categoria:
        query = query.eq("categoria", categoria)
    if subcategoria:
        query = query.eq("subcategoria", subcategoria)
    if marca:
        # buscar el id de la marca primero
        marca_res = supabase.table("marcas").select("id").ilike("nombre", f"%{marca}%").execute()
        if marca_res.data:
            query = query.eq("marca_id", marca_res.data[0]["id"])
    if q:
        query = query.ilike("nombre", f"%{q}%")

    if orden == "precio_asc":
        query = query.order("precio", desc=False)
    elif orden == "precio_desc":
        query = query.order("precio", desc=True)
    elif orden == "marca":
        query = query.order("marca_id")

    res = query.limit(limit).execute()

    # formatear respuesta para que el frontend la entienda
    productos = []
    for p in res.data:
        productos.append({
            "id": p["id"],
            "nombre": p["nombre"],
            "precio": p["precio"],
            "imagen_url": p["imagen_url"],
            "producto_url": p["producto_url"],
            "categoria": p["categoria"],
            "subcategoria": p["subcategoria"],
            "marca": p["marcas"]["nombre"] if p.get("marcas") else "",
        })

    return {"productos": productos, "total": len(productos)}


# GET /marcas — devuelve todas las marcas activas
@app.get("/marcas")
def get_marcas():
    res = supabase.table("marcas").select("id, nombre, url_base").eq("activa", True).execute()
    return {"marcas": res.data}


# POST /sync — dispara la sincronización manualmente
@app.post("/sync")
def sync_manual():
    resultados = sincronizar_todo()
    return {"ok": True, "resultados": resultados}


# POST /sync/{marca_id} — sincroniza solo una marca
@app.post("/sync/{marca_id}")
def sync_una_marca(marca_id: int):
    res = supabase.table("marcas").select("*").eq("id", marca_id).execute()
    if not res.data:
        return {"error": "Marca no encontrada"}
    resultado = sincronizar_todo.__wrapped__(res.data[0]) if hasattr(sincronizar_todo, '__wrapped__') else None
    from scraper import sincronizar_marca
    resultado = sincronizar_marca(res.data[0])
    return {"ok": True, "resultado": resultado}


# GET /logs — ver el historial de sincronizaciones
@app.get("/logs")
def get_logs():
    res = supabase.table("scraper_logs").select(
        "*, marcas(nombre)"
    ).order("fecha", desc=True).limit(50).execute()
    return {"logs": res.data}


# GET / — health check
@app.get("/")
def health():
    return {"status": "ok", "app": "Archive Brand BA API"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
