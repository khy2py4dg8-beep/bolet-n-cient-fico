#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 DeNadA - Divulgación Científica
================================================================================
Editado y coordinado por: LOPEZ HELACIO MAXI JESUS
Tecnológico Nacional de México | Instituto Tecnológico de Celaya
Automatizado mediante GitHub Actions & Groq
"""

import os
import re
import json
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

import requests
import feedparser

# ==============================================================================
# 1. CONFIGURACIÓN GENERAL
# ==============================================================================

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

EMAIL_ORIGEN = os.environ["EMAIL_REMITENTE"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_DESTINO = os.environ["EMAIL_DESTINATARIO"]
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))

MIN_NOTICIAS_MUNDIALES = 4
MIN_NOTICIAS_MEXICO = 2
MIN_TOTAL = 6

HEADERS_HTTP = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DeNadABoletin/2.0; "
        "+https://github.com/)"
    )
}

# Fuentes de impacto mundial (ciencias biológicas y de la salud)
FEEDS_MUNDIALES = {
    "NATURE": "https://www.nature.com/nature.rss",
    "SCIENCEDAILY": "https://www.sciencedaily.com/rss/top/science.xml",
    "EUREKALERT": "https://www.eurekalert.org/rss/health_medicine.xml",
    "NIH": "https://www.nih.gov/news-events/news-releases/feed",
    "WHO": "https://www.who.int/rss-feeds/news-english.xml",
}

# Fuentes específicas de México
FEEDS_MEXICO = {
    "GACETA UNAM": "https://www.gaceta.unam.mx/feed/",
    "CIENCIA UNAM": "https://ciencia.unam.mx/rss",
}


# ==============================================================================
# 2. OBTENCIÓN Y ORDENAMIENTO DE NOTICIAS (RSS)
# ==============================================================================

def extraer_imagen(entry):
    try:
        media_content = entry.get("media_content")
        if media_content:
            url = (media_content[0].get("url") or "").strip()
            if url:
                return url

        media_thumbnail = entry.get("media_thumbnail")
        if media_thumbnail:
            url = (media_thumbnail[0].get("url") or "").strip()
            if url:
                return url

        for link in entry.get("links", []) or []:
            tipo = (link.get("type") or "")
            if tipo.startswith("image/"):
                href = (link.get("href") or "").strip()
                if href:
                    return href

        contenido_crudo = entry.get("summary") or ""
        if not contenido_crudo and entry.get("content"):
            try:
                contenido_crudo = entry["content"][0].get("value", "")
            except Exception:
                contenido_crudo = ""

        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', contenido_crudo)
        if match:
            return match.group(1).strip()

    except Exception as e:
        print(f"[AVISO] Error al buscar imagen: {e}")

    return None


def es_url_imagen_valida(url):
    if not url:
        return False
    return url.startswith("http://") or url.startswith("https://")


def obtener_entradas_de_feeds(feeds_dict, max_por_feed=3):
    entradas = []
    for fuente, url in feeds_dict.items():
        try:
            resp = requests.get(url, headers=HEADERS_HTTP, timeout=15)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)

            entradas_ordenadas = parsed.entries
            if entradas_ordenadas and hasattr(entradas_ordenadas[0], 'published_parsed'):
                try:
                    entradas_ordenadas = sorted(
                        entradas_ordenadas,
                        key=lambda x: x.published_parsed if x.get('published_parsed') else time.gmtime(0),
                        reverse=True
                    )
                except Exception:
                    pass

            for entry in entradas_ordenadas[:max_por_feed]:
                link = (entry.get("link") or "").strip()
                titulo = (entry.get("title") or "").strip()
                resumen_original = (
                    entry.get("summary") or entry.get("description") or ""
                ).strip()
                resumen_original = re.sub(r"<[^>]+>", "", resumen_original)

                imagen = extraer_imagen(entry)
                if not es_url_imagen_valida(imagen):
                    imagen = None

                if link and titulo:
                    entradas.append({
                        "fuente": fuente,
                        "titulo": titulo,
                        "resumen_original": resumen_original[:800],
                        "link": link,
                        "imagen": imagen,
                    })
        except Exception as e:
            print(f"[AVISO] No se pudo leer el feed '{fuente}': {e}")
            continue

    return entradas


def seleccionar_noticias():
    entradas_mundiales = obtener_entradas_de_feeds(FEEDS_MUNDIALES)
    entradas_mexico = obtener_entradas_de_feeds(FEEDS_MEXICO)

    vistos = set()

    def sin_duplicados(lista):
        unicas = []
        for e in lista:
            if e["link"] not in vistos:
                vistos.add(e["link"])
                unicas.append(e)
        return unicas

    entradas_mundiales = sin_duplicados(entradas_mundiales)
    entradas_mexico = sin_duplicados(entradas_mexico)

    seleccion_mexico = entradas_mexico[:MIN_NOTICIAS_MEXICO]
    seleccion_mundial = entradas_mundiales[:MIN_NOTICIAS_MUNDIALES]

    seleccion_final = seleccion_mundial + seleccion_mexico

    if len(seleccion_final) < MIN_TOTAL:
        restantes = [
            e for e in (entradas_mundiales + entradas_mexico)
            if e["link"] not in {x["link"] for x in seleccion_final}
        ]
        faltan = MIN_TOTAL - len(seleccion_final)
        seleccion_final += restantes[:faltan]

    return seleccion_final


# ==============================================================================
# 3. PROCESAMIENTO CON IA (Groq)
# ==============================================================================

SYSTEM_PROMPT = '''Eres un traductor y divulgador científico experto en ciencias biológicas y de la salud para el proyecto DeNadA.

Tu única tarea es tomar un título y un resumen y devolver EXCLUSIVAMENTE un objeto JSON válido:
{"titulo_es": "...", "resumen_es": "..."}

Reglas estrictas:
- "titulo_es": traducción clara y atractiva al español neutro.
- "resumen_es": resumen divulgativo de 3 a 4 líneas en español neutro.
- No incluyas enlaces ni etiquetas HTML.
'''


def limpiar_posible_markdown(texto):
    if not texto:
        return ""
    texto = re.sub(r"```[a-zA-Z]*", "", texto)
    texto = texto.replace("```", "")
    texto = texto.replace("**", "")
    texto = re.sub(r"(?m)^#+\s*", "", texto)
    return texto.strip()


def extraer_json(contenido_ia):
    contenido_ia = contenido_ia.strip()
    contenido_ia = re.sub(r"^```[a-zA-Z]*", "", contenido_ia)
    contenido_ia = contenido_ia.replace("```", "").strip()

    try:
        return json.loads(contenido_ia)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", contenido_ia, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def resumir_y_traducir_con_ia(entrada, reintentos=2):
    mensaje_usuario = (
        f"Título original: {entrada['titulo']}\n"
        f"Resumen original: {entrada['resumen_original']}\n"
        f"Fuente: {entrada['fuente']}"
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": mensaje_usuario},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    for intento in range(reintentos + 1):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            contenido = data["choices"][0]["message"]["content"]
            resultado = extraer_json(contenido)

            titulo_es = limpiar_posible_markdown(resultado.get("titulo_es", "")) or entrada["titulo"]
            resumen_es = limpiar_posible_markdown(resultado.get("resumen_es", "")) or entrada["resumen_original"]
            return titulo_es, resumen_es

        except Exception as e:
            print(f"[AVISO] Intento {intento + 1} falló para '{entrada['titulo'][:60]}...': {e}")
            time.sleep(2)

    return entrada["titulo"], entrada["resumen_original"]


# ==============================================================================
# 4. CONSTRUCCIÓN DEL HTML (DISEÑO DeNadA)
# ==============================================================================

def construir_tarjeta_html(fuente, titulo_es, resumen_es, link, imagen=None):
    fuente_mayus = fuente.upper()

    imagen_html = ""
    if imagen:
        imagen_html = (
            f'<img src="{imagen}" alt="{titulo_es}" '
            f'style="max-width:100%; height:auto; border-radius:6px; '
            f'margin-bottom:14px; display:block;">'
        )

    return f'''
    <div style="background-color:#ffffff; border:1px solid #d9d9d9; border-left:5px solid #00D2FF; border-radius:8px; padding:22px; margin-bottom:22px; font-family: Georgia, 'Times New Roman', serif;">
        {imagen_html}
        <p style="color:#003366; font-size:12px; font-weight:bold; letter-spacing:1.5px; margin:0 0 10px 0; text-transform:uppercase;">{fuente_mayus}</p>
        <h2 style="color:#1a1a1a; font-size:19px; margin:0 0 12px 0; line-height:1.35;">{titulo_es}</h2>
        <p style="color:#3a3a3a; font-size:15px; line-height:1.6; margin:0 0 18px 0;">{resumen_es}</p>
        <a href="{link}" target="_blank" style="display:inline-block; background-color:#001F3F; color:#00D2FF; text-decoration:none; padding:10px 20px; border-radius:4px; font-size:13px; font-weight:bold; font-family: Arial, sans-serif;">Leer Artículo Original &rarr;</a>
    </div>
    '''


def construir_boletin_completo(tarjetas_html, fecha_str):
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>DeNadA - Divulgación Científica</title>
</head>
<body style="margin:0; padding:0; background-color:#eef1f4;">

    <!-- ENCABEZADO CON LOGO DE "DeNadA" -->
    <div style="background-color:#001F3F; padding:30px 20px; text-align:center; border-bottom: 4px solid #00D2FF;">
      <svg width="60" height="60" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" style="vertical-align:middle; margin-bottom:10px;">
        <circle cx="50" cy="50" r="45" stroke="#00D2FF" stroke-width="3" stroke-dasharray="6 6" />
        <ellipse cx="50" cy="50" rx="35" ry="12" stroke="#00D2FF" stroke-width="3" transform="rotate(30 50 50)"/>
        <ellipse cx="50" cy="50" rx="35" ry="12" stroke="#ffffff" stroke-width="3" transform="rotate(-30 50 50)"/>
        <circle cx="50" cy="50" r="8" fill="#00D2FF"/>
      </svg>
      <h1 style="color:#ffffff; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size:34px; font-weight:800; letter-spacing:3px; margin:5px 0 0 0;">
        De<span style="color:#00D2FF;">NAD</span>A
      </h1>
      <p style="color:#B0C4DE; font-family: Arial, sans-serif; font-size:12px; letter-spacing:2px; text-transform:uppercase; margin:5px 0 0 0; font-weight:600;">
        Divulgación Científica
      </p>
      <p style="color:#8fa3bd; font-family: Arial, sans-serif; font-size:11px; margin:10px 0 0 0;">{fecha_str}</p>
    </div>

    <!-- CUERPO DE NOTICIAS -->
    <div style="max-width:700px; margin:0 auto; padding:30px 20px; background-color:#f4f6f8;">
        {tarjetas_html}
    </div>

    <!-- PIE DE PÁGINA -->
    <div style="background-color:#001F3F; padding:26px 20px; text-align:center; font-family: Arial, sans-serif; border-top: 1px solid #00D2FF;">
        <p style="color:#ffffff; font-size:13px; margin:0 0 6px 0;">Editado y coordinado por: <strong>LOPEZ HELACIO MAXI JESUS</strong></p>
        <p style="color:#9fb2c9; font-size:12px; margin:0 0 6px 0;">Tecnológico Nacional de México | Instituto Tecnológico de Celaya</p>
        <p style="color:#6f7f91; font-size:11px; margin:0;">Proyecto DeNadA &bull; GitHub Actions &amp; Groq</p>
    </div>

</body>
</html>'''


# ==============================================================================
# 5. ENVÍO Y EJECUCIÓN
# ==============================================================================

def enviar_correo(html_final, fecha_str):
    destinatarios = [d.strip() for d in EMAIL_DESTINO.split(",") if d.strip()]

    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = f"DeNadA - Boletín Científico del {fecha_str}"
    mensaje["From"] = EMAIL_ORIGEN
    mensaje["To"] = ", ".join(destinatarios)

    mensaje.attach(MIMEText(html_final, "html", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as servidor:
        servidor.login(EMAIL_ORIGEN, EMAIL_PASSWORD)
        servidor.sendmail(EMAIL_ORIGEN, destinatarios, mensaje.as_string())

    print(f"[OK] Correo enviado a: {', '.join(destinatarios)}")


def main():
    fecha_str = datetime.now().strftime("%d de %B de %Y")

    print("[INFO] Obteniendo noticias de feeds RSS...")
    noticias = seleccionar_noticias()

    if not noticias:
        print("[ERROR] No se obtuvo ninguna noticia válida.")
        return

    print(f"[INFO] {len(noticias)} noticias seleccionadas. Procesando...")

    tarjetas = []
    for i, entrada in enumerate(noticias, start=1):
        print(f"[INFO] ({i}/{len(noticias)}) Procesando: {entrada['titulo'][:70]}...")
        titulo_es, resumen_es = resumir_y_traducir_con_ia(entrada)

        tarjeta_html = construir_tarjeta_html(
            fuente=entrada["fuente"],
            titulo_es=titulo_es,
            resumen_es=resumen_es,
            link=entrada["link"],
            imagen=entrada.get("imagen"),
        )
        tarjetas.append(tarjeta_html)

        time.sleep(1.2)

    tarjetas_html = "\n".join(tarjetas)
    html_final = construir_boletin_completo(tarjetas_html, fecha_str)

    print("[INFO] Enviando boletín DeNadA por correo...")
    enviar_correo(html_final, fecha_str)

    print("[OK] Proceso finalizado correctamente.")


if __name__ == "__main__":
    main()
