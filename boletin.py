import feedparser
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from groq import Groq

# 1. Configuración de Fuentes Científicas (RSS Feeds)
FEEDS = {
    "Nature": "https://www.nature.com/nature.rss",
    "Science": "https://www.science.org/blogs/feed"
}

def recopilar_noticias():
    print("Recopilando datos científicos...")
    datos_crudos = ""
    for fuente, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entrada in feed.entries[:3]: # Tomamos las 3 más recientes de cada una
            # Intentar extraer una imagen si el feed la incluye
            img_url = ""
            if 'media_content' in entrada:
                img_url = entrada.media_content[0]['url']
            elif 'links' in entrada:
                for link in entrada.links:
                    if 'image' in link.get('type', ''):
                        img_url = link.get('href', '')
            
            datos_crudos += f"Fuente: {fuente}\nTítulo: {entrada.title}\nLink: {entrada.link}\nResumen Original: {entrada.description}\nImagen: {img_url}\n---\n"
    return datos_crudos

def generar_boletin_con_ia(datos_cientificos):
    print("Enviando a Groq para maquetación editorial...")
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # Instrucciones estrictas a la IA para que actúe como diseñadora web y redactora científica
    
    prompt = f"""
    [INSTRUCCIÓN PRINCIPAL]
    Actúa como un Diseñador Web Front-End y Divulgador Científico experto. Tu tarea es tomar las noticias del apartado [DATOS_CRUDOS] de abajo y redactar un boletín informativo hermoso y limpio.

    [REGLAS CRÍTICAS DE FORMATO HTML]
    - Genera ÚNICAMENTE código HTML funcional para el cuerpo del correo.
    - NO uses etiquetas ```html, ni comillas invertidas, ni texto introductorio o aclaraciones fuera de las etiquetas HTML.
    - Prohibido usar Markdown: NO uses asteriscos (**) ni numerales (#). 
    - Reemplaza el texto "URL_DE_LA_NOTICIA" por el Link real provisto abajo.
    - Para cada noticia, crea un contenedor estructurado:
      <div style="background: #ffffff; padding: 20px; margin-bottom: 25px; border-radius: 8px; border-left: 5px solid #003366; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
      <span style="color: #6c757d; font-size: 12px; font-weight: bold; text-transform: uppercase;">Noticia de Fuente</span>
      <h3 style="color: #003366; margin: 5px 0 10px 0; font-size: 18px;">Título Traducido a Español</h3>
      <p style="color: #495057; font-size: 14px; line-height: 1.5;">Resumen analítico y divulgativo en español de 3 o 4 líneas.</p>
    </div>
    [DATOS_CRUDOS]
    {datos_cientificos}
    """
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3 # Menor temperatura para que sea más obediente con el formato
    )
    return response.choices[0].message.content

def enviar_correo(contenido_html):
    print("Estructurando correo electrónico enriquecido...")
    remitente = os.environ.get("EMAIL_REMITENTE")
    password = os.environ.get("EMAIL_PASSWORD")
    destinatario = os.environ.get("EMAIL_DESTINATARIO")
    
    # Configuramos el contenedor MIME para correos estructurados
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "📰 Boletín de Vanguardia Científica y Biomédica"
    msg['From'] = remitente
    msg['To'] = destinatario
    
    # Plantilla base del diseño tipo Newsletter (Encabezado y Pie de página con tu firma)
    html_completo = f"""
    <html>
      <body style="background-color: #f4f6f9; font-family: Arial, sans-serif; margin: 0; padding: 20px;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
          
          <!-- Banner Principal -->
          <div style="background-color: #003366; padding: 30px; text-align: center; color: #ffffff;">
            <h1 style="margin: 0; font-size: 24px; letter-spacing: 1px;">VANGUARDIA CIENTÍFICA</h1>
            <p style="margin: 5px 0 0 0; color: #b3ccff; font-size: 14px;">Curación diaria de Ciencias Biológicas y de la Salud</p>
          </div>
          
          <!-- Contenido generado por la IA -->
          <div style="padding: 25px; color: #333333; line-height: 1.6;">
            {contenido_html}
          </div>
          
          <!-- Firma Editorial para Portafolio Académico -->
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
    
    # Adjuntamos el HTML especificando el tipo text/html
    msg.attach(MIMEText(html_completo, 'html'))
    
    # Envío SMTP
    print("Conectando al servidor e iniciando transferencia...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())
    print("¡Revista enviada con éxito!")

if __name__ == "__main__":
    datos = recopilar_noticias()
    boletin_html = generar_boletin_con_ia(datos)
    
    # Python inyecta los links reales en las tarjetas generadas por la IA
    for fuente, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entrada in feed.entries[:3]:
            # Creamos el botón real con el enlace directo del RSS
            boton_real = f'<br><a href="{entrada.link}" target="_blank" style="display: inline-block; background: #003366; color: #ffffff; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 12px; margin-top: 10px; font-family: Arial, sans-serif; font-weight: bold;">Leer Artículo Original →</a></div>'
            # Reemplazamos el cierre del contenedor para meter el botón antes de que se cierre la tarjeta
            boletin_html = boletin_html.replace('</div>', boton_real, 1)

    enviar_correo(boletin_html)
