import os
import json
import smtplib
import feedparser
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq

# ==========================================
# CONFIGURACIÓN Y FUENTES RSS
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
EMAIL_REMITENTE = os.environ.get("EMAIL_REMITENTE")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_DESTINATARIO = os.environ.get("EMAIL_DESTINATARIO")

FUENTES_RSS = [
    "https://rss.sciencedaily.com/all.xml",
    "https://www.nature.com/nature.rss",
    "https://www.wired.com/feed/category/science/latest/rss",
    "https://eluniversal.com.mx/arc/outboundfeeds/rss/ciencia/"
]

# ==========================================
# BASE DE DATOS Y GUARDADO EN JSON
# ==========================================
def guardar_en_historico(noticias_procesadas, archivo_json="historico_noticias.json"):
    """Guarda y acumula las noticias procesadas en un archivo JSON local."""
    historico = []
    
    # 1. Cargar archivo existente si existe
    if os.path.exists(archivo_json):
        try:
            with open(archivo_json, "r", encoding="utf-8") as f:
                historico = json.load(f)
        except Exception as e:
            print(f"[WARN] No se pudo leer {archivo_json}, se creará uno nuevo. Error: {e}")

    # 2. Convertir y agregar noticias con su timestamp
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    for noticia in noticias_procesadas:
        registro = {
            "fecha": fecha_hoy,
            "titulo": noticia.get("titulo", ""),
            "resumen": noticia.get("resumen", ""),
            "categoria": noticia.get("categoria", "Ciencia"),
            "fuente": noticia.get("fuente", "Desconocida"),
            "url": noticia.get("link", "#")
        }
        historico.append(registro)

    # 3. Reescribir la base de datos actualizada
    try:
        with open(archivo_json, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)
        print(f"[ÉXITO] Se guardaron {len(noticias_procesadas)} noticias en {archivo_json}")
    except Exception as e:
        print(f"[ERROR] Error al escribir en {archivo_json}: {e}")

# ==========================================
# EXTRACCIÓN DE NOTICIAS
# ==========================================
def obtener_noticias():
    """Lee los feeds RSS y recupera las noticias más recientes."""
    noticias = []
    for url in FUENTES_RSS:
        try:
            feed = feedparser.parse(url)
            fuente = feed.feed.title if hasattr(feed.feed, 'title') else "Fuente Científica"
            for entry in feed.entries[:3]:  # Tomar hasta 3 por fuente
                noticias.append({
                    "titulo": entry.title,
                    "resumen": entry.get("summary", entry.get("description", "")),
                    "link": entry.link,
                    "fuente": fuente
                })
        except Exception as e:
            print(f"[WARN] Error al procesar fuente {url}: {e}")
    return noticias

# ==========================================
# PROCESAMIENTO CON GROQ (LLaMA 3.3 70B)
# ==========================================
def sintetizar_con_groq(noticias):
    """Sintetiza y clasifica las noticias con IA."""
    if not GROQ_API_KEY:
        print("[ERROR] Falta GROQ_API_KEY en las variables de entorno.")
        return []

    client = Groq(api_key=GROQ_API_KEY)
    noticias_procesadas = []

    for idx, noticia in enumerate(noticias[:5]):  # Limite a las 5 mejores noticias
        prompt = f"""
Eres el editor principal del boletín científico "DeNadA". 
Sintetiza la siguiente noticia de ciencia/tecnología en español en un párrafo directo, interesante y accesible.
Clasifícala en una categoría (ej. Biotecnología, Neurociencia, Astronomía, Genómica, Medicina).

Título: {noticia['titulo']}
Texto: {noticia['resumen']}

Responde EXCLUSIVAMENTE en formato JSON válido como este:
{{
  "titulo_es": "Título traducido o sintetizado en español",
  "resumen_es": "Resumen claro y fascinante en 2 o 3 oraciones.",
  "categoria": "Categoría asignada"
}}
"""
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            datos = json.loads(response.choices[0].message.content)
            noticias_procesadas.append({
                "titulo": datos.get("titulo_es", noticia['titulo']),
                "resumen": datos.get("resumen_es", noticia['resumen']),
                "categoria": datos.get("categoria", "Ciencia"),
                "fuente": noticia['fuente'],
                "link": noticia['link']
            })
        except Exception as e:
            print(f"[WARN] Error procesando noticia con Groq: {e}")
            # Fallback en caso de fallo de IA
            noticias_procesadas.append({
                "titulo": noticia['titulo'],
                "resumen": noticia['resumen'][:200] + "...",
                "categoria": "Ciencia",
                "fuente": noticia['fuente'],
                "link": noticia['link']
            })

    return noticias_procesadas

# ==========================================
# CONSTRUCCIÓN DE HTML Y PLANTILLA
# ==========================================
def generar_tarjeta_html(noticia):
    """Genera una tarjeta individual para el correo."""
    return f"""
    <div style="background: #ffffff; border-radius: 12px; padding: 20px; margin-bottom: 20px; border-left: 5px solid #0052cc; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
        <span style="background: #e6f0ff; color: #0052cc; font-size: 12px; font-weight: bold; padding: 4px 10px; border-radius: 20px; text-transform: uppercase;">
            {noticia['categoria']}
        </span>
        <h3 style="color: #1e293b; font-size: 18px; margin: 12px 0 8px 0; line-height: 1.4;">
            {noticia['titulo']}
        </h3>
        <p style="color: #475569; font-size: 14px; line-height: 1.6; margin-bottom: 14px;">
            {noticia['resumen']}
        </p>
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #64748b;">
            <span>Fuente: <strong>{noticia['fuente']}</strong></span>
            <a href="{noticia['link']}" target="_blank" style="color: #0052cc; font-weight: bold; text-decoration: none;">Leer más &rarr;</a>
        </div>
    </div>
    """

def construir_boletin_completo(tarjetas_html, fecha_str):
    """Genera la estructura HTML global con la marca DeNadA."""
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 0; }}
            .container {{ max-width: 650px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 30px; text-align: center; border-radius: 16px 16px 0 0; }}
            .brand {{ font-size: 36px; font-weight: 800; letter-spacing: 1px; margin: 0; color: #ffffff; }}
            .brand span {{ color: #38bdf8; text-decoration: underline; }}
            .subtitle {{ color: #94a3b8; font-size: 14px; margin-top: 5px; }}
            .content {{ background: #f1f5f9; padding: 20px; border-radius: 0 0 16px 16px; }}
            .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #94a3b8; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 class="brand">DeNad<span>A</span></h1>
                <p class="subtitle">Boletín Informativo de Noticias Científicas • {fecha_str}</p>
            </div>
            <div class="content">
                {tarjetas_html}
            </div>
            <div class="footer">
                <p>Generado automáticamente por el pipeline DeNadA | Maxi Jesús López Helacio</p>
            </div>
        </div>
    </body>
    </html>
    """

# ==========================================
# ENVÍO DE CORREO SMTP
# ==========================================
def enviar_correo(html_contenido, fecha_str):
    """Envía el boletín generado por correo electrónico mediante SMTP."""
    if not all([EMAIL_REMITENTE, EMAIL_PASSWORD, EMAIL_DESTINATARIO]):
        print("[ERROR] Faltan variables de entorno para el envío de correo.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🧬 DeNadA Digest: Noticias de Ciencia ({fecha_str})"
    msg["From"] = EMAIL_REMITENTE
    msg["To"] = EMAIL_DESTINATARIO

    part_html = MIMEText(html_contenido, "html")
    msg.attach(part_html)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_REMITENTE, EMAIL_PASSWORD)
            server.sendmail(EMAIL_REMITENTE, EMAIL_DESTINATARIO.split(","), msg.as_string())
        print("[ÉXITO] Boletín enviado por correo satisfactoriamente.")
    except Exception as e:
        print(f"[ERROR] Error al enviar el correo: {e}")

# ==========================================
# FLUJO PRINCIPAL
# ==========================================
def main():
    print("[INFO] Iniciando pipeline DeNadA...")
    fecha_str = datetime.now().strftime("%d/%m/%Y")
    
    # 1. Obtener noticias de los feeds RSS
    print("[INFO] Obteniendo noticias de fuentes RSS...")
    noticias_raw = obtener_noticias()
    
    if not noticias_raw:
        print("[WARN] No se encontraron noticias hoy.")
        return

    # 2. Procesar y resumir con IA
    print("[INFO] Procesando noticias con Groq (LLaMA 3.3)...")
    noticias_procesadas = sintetizar_con_groq(noticias_raw)

    # 3. Guardar en base de datos local JSON
    print("[INFO] Guardando noticias en la base de datos JSON...")
    guardar_en_historico(noticias_procesadas)

    # 4. Generar tarjetas HTML
    tarjetas = [generar_tarjeta_html(n) for n in noticias_procesadas]
    tarjetas_html = "\n".join(tarjetas)
    html_final = construir_boletin_completo(tarjetas_html, fecha_str)

    # 5. Enviar boletín por correo
    print("[INFO] Enviando correo...")
    enviar_correo(html_final, fecha_str)
    
    print("[ÉXITO] Proceso completado con éxito.")

if __name__ == "__main__":
    main()
