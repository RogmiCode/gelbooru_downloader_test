import requests
from typing import List, Tuple, Optional
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
import zipfile
import streamlit as st

MAX_WORKERS = 10
IMGS_PER_PAGE = 10

def descargar_imagen(url: str, idx: int) -> Optional[Tuple[int, bytes, str]]:
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return (idx, resp.content, f"gelbooru_{idx}.jpg")
    except Exception as e:
        st.warning(f'Error al descargar imagen {idx}: {str(e)}')
        return None

def descargar_imagenes_en_memoria(imagenes: List[dict]) -> io.BytesIO:
    zip_buffer = io.BytesIO()
    urls = [(img.get('file_url'), idx+1) for idx, img in enumerate(imagenes) if img.get('file_url')]
    if not urls:
        st.error("No hay URLs válidas para descargar")
        return zip_buffer
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(urls)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(descargar_imagen, url, idx) for url, idx in urls]
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                if result:
                    idx, content, filename = result
                    zip_file.writestr(filename, content)
                progress = (i + 1) / total
                progress_bar.progress(progress)
                status_text.text(f"Descargando {i+1}/{total} imágenes...")
    progress_bar.empty()
    status_text.empty()
    zip_buffer.seek(0)
    return zip_buffer
