import feedparser
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from groq import Groq

# Configuración de Fuentes Científicas (RSS Feeds)
FEEDS = {
    "Nature": "https://www.nature.com/nature.rss",
    "Science": "https://www.science.org/blogs/feed"
}

def recopilar_noticias():
    print("Recopilando datos científicos...")
    datos_crudos = ""
    for fuente, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entrada in feed.entries[:3]:
            # Guardamos la información limpia pasándole explícitamente el link
            datos_crudos += f"FUENTE_ORIGEN: {fuente}\nTITULO_ORIGEN: {entrada.title}\nENLACE_WEB: {entrada.link}\nRESUMEN_ORIGEN: {entrada.description}\n===\n"
    return datos_crudos

def generar_boletin_con_ia(datos_cientificos):
    print("Enviando a Groq para maquetación...")
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # Usamos triples comillas simples para que las llaves no interfieran con Python
    prompt = '''
    Actúa como un Diseñador Web Front-End y Divulgador Científico. Genera exclusivamente código HTML para las noticias provistas en [DATOS].

    REGLAS DE FORMATO:
    - NO uses Markdown, asteriscos (**) ni texto explicativo. Solo código HTML.
    - Traduce los títulos y resúmenes al español.
    - Por cada noticia del listado, genera exactamente esta estructura HTML:

    <div style="background: #ffffff; padding: 20px; margin-bottom: 25px; border-radius: 8px; border-left: 5px solid #003366; box-shadow: 0 2px 5px rgba(0,0,0,0.05); font-family: Arial, sans-serif;">
      <span style="color: #6c757d; font-size: 12px; font-weight: bold; text-transform: uppercase;">Noticia de FUENTE_ORIGEN</span>
      <h3 style="color: #003366; margin: 5px 0 10px 0; font-size: 18px;">Pone aquí el Título Traducido</h3>
      <p style="color: #495057; font-size: 14px; line-height: 1.5;">Pone aquí el Resumen en español de 3 o 4 líneas.</p>
      <a href="REEMPLAZA_CON_EL_ENLACE_WEB_DE_CADA_NOTICIA" target="_blank" style="display: inline-block; background: #003366; color: #ffffff; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 12px; margin-top: 10px; font-weight: bold;">Leer Artículo Original →</a>
    </div>

    [DATOS]
    ''' + datos_cientificos
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

def enviar_correo(contenido_html):
    print("Estructurando correo electrónico...")
    remitente = os.environ.get("EMAIL_REMITENTE")
    password = os.environ.get("EMAIL_PASSWORD")
    destinatario = os.environ.get("EMAIL_DESTINATARIO")
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "📰 Boletín de Vanguardia Científica y Biomédica"
    msg['From'] = remitente
    msg['To'] = destinatario
    
    html_completo = f"""
    <html>
      <body style="background-color: #f4f6f9; font-family: Arial, sans-serif; margin: 0; padding: 20px;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
          
          <div style="background-color: #003366; padding: 30px; text-align: center; color: #ffffff;">
            <h1 style="margin: 0; font-size: 24px; letter-spacing: 1px;">VANGUARDIA CIENTÍFICA</h1>
            <p style="margin: 5px 0 0 0; color: #b3ccff; font-size: 14px;">Curación diaria de Ciencias Biológicas y de la Salud</p>
          </div>
          
          <div style="padding: 25px; color: #333333; line-height: 1.6;">
            {contenido_html}
          </div>
          
          <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #e9ecef; color: #6c757d; font-size: 12px;">
            <p style="margin: 0 0 5px 0; font-weight: bold; color: #495057;">Boletín Informativo de Divulgación</p>
            <p style="margin: 0; font-style: italic;">Editado y coordinado por: <strong>LOPEZ HELACIO MAXI JESUS</strong></p>
            <p style="margin: 5px 0 0 0; font-size: 11px;">Tecnológico Nacional de México | Instituto Tecnológico de Celaya</p>
            <p style="margin: 15px 0 0 0; color: #adb5bd;">Automatizado mediante GitHub Actions & Groq Llama-3.1 IA</p>
          </div>
          
        </div>
      </body>
    </html>
    """
    
    msg.attach(MIMEText(html_completo, 'html'))
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())
    print("¡Revista enviada con éxito!")

if __name__ == "__main__":
    datos = recopilar_noticias()
    boletin_html = generar_boletin_con_ia(datos)
    enviar_correo(boletin_html)
