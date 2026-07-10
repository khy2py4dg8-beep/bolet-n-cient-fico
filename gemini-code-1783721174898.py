import os
import smtplib
from email.mime.text import MIMEText
import feedparser
from groq import Groq

# 1. Configuración de fuentes científicas
FEEDS = {
    "Nature": "https://www.nature.com/nature.rss",
    "Science": "https://www.science.org/blogs/feed",
    "PubMed_Neuro": "https://pubmed.ncbi.nlm.nih.gov/rss/search/1/?term=neuroscience"
}

def obtener_noticias_del_dia():
    titulos_y_resumenes = ""
    for fuente, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            titulos_y_resumenes += f"Fuente: {fuente}\nTítulo: {entry.title}\nResumen: {getattr(entry, 'summary', 'No abstract')}\n\n"
    return titulos_y_resumenes

def generar_boletin_con_ia(datos_cientificos):
    # Inicializa el cliente de Groq usando su llave
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    prompt_sistema = (
        "Actúa como un analista de comunicación científica. Tu objetivo es redactar un boletín diario "
        "con las noticias más relevantes basados EXCLUSIVAMENTE en el texto que te proporcionará el usuario. "
        "Enfócate en: Biomedicina, Biología Molecular, Neurobiología y Bioinformática. Busca impacto mundial o en México. "
        "Para cada noticia usa la estructura estricta:\n"
        "- Titular:\n- Área:\n- Alcance:\n- El Descubrimiento/Hito:\n- Por qué es relevante:\n- Fuente sugerida:\n"
        "Si no hay noticias relevantes de México en el texto provisto, indícalo de forma explícita y concéntrate en los hitos mundiales."
    )

    response = client.chat.completions.create(
        model="llama3-8b-8192", # El modelo gratuito de Meta en Groq, ideal para resúmenes rápidos
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Aquí están los datos del día:\n\n{datos_cientificos}"}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content

def enviar_correo(contenido_boletin):
    remitente = os.environ.get("EMAIL_REMITENTE")
    password = os.environ.get("EMAIL_PASSWORD")
    destinatario = os.environ.get("EMAIL_DESTINATARIO")

    msg = MIMEText(contenido_boletin, "plain", "utf-8")
    msg["Subject"] = "🔬 Boletín Científico Diario Automatizado"
    msg["From"] = remitente
    msg["To"] = destinatario

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())

if __name__ == "__main__":
    print("Recopilando datos científicos...")
    datos = obtener_noticias_del_dia()
    
    print("Enviando a Groq para curación...")
    boletin = generar_boletin_con_ia(datos)
    
    print("Enviando correo...")
    enviar_correo(boletin)
    print("¡Boletín enviado con éxito!")