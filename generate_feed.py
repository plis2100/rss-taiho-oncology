from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator


NEWS_URL = "https://www.taihooncology.com/us/news/"
BASE_URL = "https://www.taihooncology.com"
OUTPUT_FILE = Path("docs/feed.xml")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def limpiar(texto):
    return " ".join((texto or "").split()).strip()


def es_noticia(url):
    ruta = urlparse(url).path.rstrip("/").lower()

    return (
        ruta.startswith("/us/news/")
        and ruta != "/us/news"
        and len(ruta) > len("/us/news/")
    )


def buscar_fecha(texto):
    coincidencia = re.search(
        r"\b(20\d{2})-(\d{2})-(\d{2})\b",
        texto,
    )

    if not coincidencia:
        return None

    año, mes, dia = map(int, coincidencia.groups())

    try:
        return datetime(
            año,
            mes,
            dia,
            12,
            0,
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None


def buscar_contenedor(enlace):
    contenedor = enlace

    for _ in range(6):
        if not contenedor.parent:
            break

        contenedor = contenedor.parent
        texto = limpiar(contenedor.get_text(" ", strip=True))

        if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", texto):
            return contenedor

    return enlace.parent or enlace


def buscar_descripcion(contenedor, titulo):
    for elemento in contenedor.find_all(["p", "div"]):
        texto = limpiar(elemento.get_text(" ", strip=True))

        if (
            texto
            and texto != titulo
            and len(texto) >= 60
            and len(texto) <= 1_500
            and "View 20" not in texto
        ):
            return texto

    return ""


def obtener_noticias():
    respuesta = requests.get(
        NEWS_URL,
        headers=HEADERS,
        timeout=60,
    )
    respuesta.raise_for_status()

    soup = BeautifulSoup(respuesta.text, "html.parser")
    noticias = {}

    for enlace in soup.find_all("a", href=True):
        url = urljoin(BASE_URL, enlace.get("href", ""))

        if not es_noticia(url):
            continue

        titulo = limpiar(enlace.get_text(" ", strip=True))

        if len(titulo) < 8:
            continue

        contenedor = buscar_contenedor(enlace)
        texto_contenedor = limpiar(
            contenedor.get_text(" ", strip=True)
        )

        fecha = buscar_fecha(texto_contenedor)
        descripcion = buscar_descripcion(contenedor, titulo)

        noticias[url] = {
            "titulo": titulo,
            "url": url,
            "fecha": fecha,
            "descripcion": descripcion,
        }

    if not noticias:
        raise RuntimeError(
            "No se encontraron comunicados de Taiho Oncology. "
            "La RSS anterior no será eliminada."
        )

    fecha_antigua = datetime(
        1970,
        1,
        1,
        tzinfo=timezone.utc,
    )

    resultado = sorted(
        noticias.values(),
        key=lambda noticia: noticia["fecha"] or fecha_antigua,
        reverse=True,
    )

    print(f"Comunicados encontrados: {len(resultado)}")

    return resultado


def crear_rss(noticias):
    feed = FeedGenerator()

    feed.id(NEWS_URL)
    feed.title("Taiho Oncology – Press Releases")
    feed.description(
        "Latest official press releases from Taiho Oncology"
    )
    feed.language("en")

    feed.link(
        href=NEWS_URL,
        rel="alternate",
    )

    feed.link(
        href=(
            "https://raw.githubusercontent.com/"
            "plis2100/rss-taiho-oncology/main/docs/feed.xml"
        ),
        rel="self",
    )

    feed.lastBuildDate(datetime.now(timezone.utc))

    for noticia in noticias[:100]:
        entrada = feed.add_entry()

        entrada.id(noticia["url"])
        entrada.title(noticia["titulo"])
        entrada.link(href=noticia["url"])

        entrada.description(
            noticia["descripcion"]
            or (
                "Read the complete press release on "
                f"Taiho Oncology: {noticia['titulo']}"
            )
        )

        if noticia["fecha"]:
            entrada.pubDate(
                format_datetime(noticia["fecha"])
            )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    feed.rss_file(
        str(OUTPUT_FILE),
        pretty=True,
        encoding="UTF-8",
    )

    print(f"RSS creada correctamente: {OUTPUT_FILE}")


if __name__ == "__main__":
    comunicados = obtener_noticias()
    crear_rss(comunicados)
