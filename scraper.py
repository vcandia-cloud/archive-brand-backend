# ════════════════════════════════════════════════════
#  scraper.py — Extrae productos de cada tienda
# ════════════════════════════════════════════════════
import requests
import hashlib
import json
from bs4 import BeautifulSoup
from database import supabase

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ── Mapeo de categorías por palabras clave en el nombre o URL
CATEGORIAS = {
    "remeras":    ["remera", "top", "musculosa", "camiseta"],
    "camisas":    ["camisa"],
    "abrigos":    ["buzo", "sweater", "campera", "cardigan", "chaleco", "hoodie", "abrigo"],
    "pantalones": ["pantalon", "pantalón", "calza", "bermuda", "joggin"],
    "jeans":      ["jean", "denim"],
    "accesorios": ["accesorio", "collar", "aro", "anillo", "pulsera", "bufanda", "billetera", "cartera"],
    "zapatos":    ["zapato", "bota", "zapatilla", "sandalia", "sueco", "texana", "calzado"],
    "vestidos":   ["vestido", "body", "enterito"],
}

SUBCATEGORIAS = {
    "musculosas":   ["musculosa"],
    "manga-corta":  ["manga corta", "mc"],
    "manga-larga":  ["manga larga", "ml", "remeron"],
    "sweaters":     ["sweater", "cardigan"],
    "buzos":        ["buzo", "hoodie"],
    "camperas":     ["campera"],
    "bufandas":     ["bufanda"],
    "aros":         ["aro"],
    "collares":     ["collar"],
    "anillos":      ["anillo"],
    "pulseras":     ["pulsera"],
    "billeteras":   ["billetera"],
    "botas":        ["bota"],
    "zapatillas":   ["zapatilla"],
    "sandalias":    ["sandalia"],
    "suecos":       ["sueco", "texana"],
}

def detectar_categoria(nombre, url=""):
    texto = (nombre + " " + url).lower()
    for cat, palabras in CATEGORIAS.items():
        for p in palabras:
            if p in texto:
                return cat
    return "remeras"  # categoría por defecto

def detectar_subcategoria(nombre, url=""):
    texto = (nombre + " " + url).lower()
    for sub, palabras in SUBCATEGORIAS.items():
        for p in palabras:
            if p in texto:
                return sub
    return None

def hacer_hash(nombre, precio, imagen):
    datos = f"{nombre}{precio}{imagen}"
    return hashlib.md5(datos.encode()).hexdigest()

# ────────────────────────────────────────
#  SCRAPER TIENDA NUBE
# ────────────────────────────────────────
def scrape_tiendanube(marca):
    productos = []
    page = 1
    url_base = marca["url_base"]

    while True:
        try:
            url = f"{url_base}/productos/?page={page}"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all("li", class_=lambda x: x and "product" in x.lower())
            if not items:
                # intentar otro selector común de Tienda Nube
                items = soup.select("article.product-item, div.product-item, li.product")
            if not items:
                break
            for item in items:
                try:
                    # nombre
                    nombre_el = item.find(["h2","h3","h4","span"], class_=lambda x: x and "name" in str(x).lower())
                    if not nombre_el:
                        nombre_el = item.find("a")
                    nombre = nombre_el.get_text(strip=True) if nombre_el else "Sin nombre"

                    # link
                    link_el = item.find("a", href=True)
                    link = link_el["href"] if link_el else ""
                    if link and not link.startswith("http"):
                        link = url_base + link

                    # precio
                    precio_el = item.find(class_=lambda x: x and "price" in str(x).lower())
                    precio_texto = precio_el.get_text(strip=True) if precio_el else "0"
                    precio = float("".join(filter(str.isdigit, precio_texto.replace(",","."))) or 0) / 100

                    # imagen
                    img_el = item.find("img")
                    imagen = ""
                    if img_el:
                        imagen = img_el.get("data-src") or img_el.get("src") or ""
                        if imagen.startswith("//"):
                            imagen = "https:" + imagen

                    if link:
                        productos.append({
                            "nombre": nombre,
                            "precio": precio,
                            "imagen_url": imagen,
                            "producto_url": link,
                            "categoria": detectar_categoria(nombre, link),
                            "subcategoria": detectar_subcategoria(nombre, link),
                            "hash": hacer_hash(nombre, precio, imagen),
                        })
                except Exception:
                    continue
            page += 1
            if page > 20:
                break
        except Exception as e:
            print(f"Error scraping {url_base} página {page}: {e}")
            break

    return productos

# ────────────────────────────────────────
#  SCRAPER SHOPIFY (via products.json)
# ────────────────────────────────────────
def scrape_shopify(marca):
    productos = []
    page = 1
    url_base = marca["url_base"]

    while True:
        try:
            url = f"{url_base}/products.json?limit=250&page={page}"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                break
            data = r.json()
            items = data.get("products", [])
            if not items:
                break
            for item in items:
                try:
                    nombre = item.get("title", "Sin nombre")
                    handle = item.get("handle", "")
                    link = f"{url_base}/products/{handle}"
                    precio = float(item.get("variants", [{}])[0].get("price", 0))
                    imagen = ""
                    if item.get("images"):
                        imagen = item["images"][0].get("src", "")

                    productos.append({
                        "nombre": nombre,
                        "precio": precio,
                        "imagen_url": imagen,
                        "producto_url": link,
                        "categoria": detectar_categoria(nombre, link),
                        "subcategoria": detectar_subcategoria(nombre, link),
                        "hash": hacer_hash(nombre, precio, imagen),
                    })
                except Exception:
                    continue
            page += 1
            if page > 10:
                break
        except Exception as e:
            print(f"Error scraping Shopify {url_base}: {e}")
            break

    return productos

# ────────────────────────────────────────
#  FUNCIÓN PRINCIPAL DE SINCRONIZACIÓN
# ────────────────────────────────────────
def sincronizar_marca(marca):
    marca_id = marca["id"]
    plataforma = marca["plataforma"]
    nuevos = 0
    actualizados = 0
    eliminados = 0

    print(f"Sincronizando {marca['nombre']}...")

    # 1. Scrapear según plataforma
    if plataforma == "shopify":
        productos_scrapeados = scrape_shopify(marca)
    else:
        productos_scrapeados = scrape_tiendanube(marca)

    if not productos_scrapeados:
        return {"nuevos": 0, "actualizados": 0, "eliminados": 0, "error": "No se encontraron productos"}

    # 2. Obtener productos actuales en la base de datos
    res = supabase.table("productos").select("*").eq("marca_id", marca_id).execute()
    productos_db = {p["producto_url"]: p for p in res.data}

    # 3. Comparar y actualizar
    urls_scrapeadas = set()

    for p in productos_scrapeados:
        url = p["producto_url"]
        urls_scrapeadas.add(url)

        if url in productos_db:
            # Ya existe — verificar si cambió algo
            existente = productos_db[url]
            if existente["hash"] != p["hash"]:
                # Guardar precio anterior en historial
                if existente["precio"] != p["precio"]:
                    supabase.table("historial_precios").insert({
                        "producto_id": existente["id"],
                        "precio_anterior": existente["precio"],
                        "precio_nuevo": p["precio"],
                    }).execute()
                # Actualizar producto
                supabase.table("productos").update({
                    "nombre": p["nombre"],
                    "precio": p["precio"],
                    "imagen_url": p["imagen_url"],
                    "categoria": p["categoria"],
                    "subcategoria": p["subcategoria"],
                    "hash": p["hash"],
                    "activo": True,
                    "ultima_vez_visto": "NOW()",
                    "updated_at": "NOW()",
                }).eq("id", existente["id"]).execute()
                actualizados += 1
        else:
            # Producto nuevo
            supabase.table("productos").insert({
                "marca_id": marca_id,
                "nombre": p["nombre"],
                "precio": p["precio"],
                "imagen_url": p["imagen_url"],
                "producto_url": p["producto_url"],
                "categoria": p["categoria"],
                "subcategoria": p["subcategoria"],
                "hash": p["hash"],
                "activo": True,
            }).execute()
            nuevos += 1

    # 4. Marcar como inactivos los que ya no están
    for url, prod in productos_db.items():
        if url not in urls_scrapeadas and prod["activo"]:
            supabase.table("productos").update({
                "activo": False,
                "updated_at": "NOW()",
            }).eq("id", prod["id"]).execute()
            eliminados += 1

    # 5. Guardar log
    supabase.table("scraper_logs").insert({
        "marca_id": marca_id,
        "estado": "ok",
        "productos_nuevos": nuevos,
        "productos_actualizados": actualizados,
        "productos_eliminados": eliminados,
    }).execute()

    print(f"  ✓ {marca['nombre']}: {nuevos} nuevos, {actualizados} actualizados, {eliminados} eliminados")
    return {"nuevos": nuevos, "actualizados": actualizados, "eliminados": eliminados}

def sincronizar_todo():
    print("=== Iniciando sincronización completa ===")
    marcas = supabase.table("marcas").select("*").eq("activa", True).execute()
    resultados = []
    for marca in marcas.data:
        try:
            r = sincronizar_marca(marca)
            resultados.append({"marca": marca["nombre"], **r})
        except Exception as e:
            print(f"Error con {marca['nombre']}: {e}")
            supabase.table("scraper_logs").insert({
                "marca_id": marca["id"],
                "estado": "error",
                "mensaje": str(e),
            }).execute()
            resultados.append({"marca": marca["nombre"], "error": str(e)})
    print("=== Sincronización completa ===")
    return resultados
