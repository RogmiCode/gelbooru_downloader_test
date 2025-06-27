import io
import os
import requests
import zipfile
import streamlit as st
from tagger.app_tagger import Predictor, SWINV2_MODEL_DSV3_REPO
from PIL import Image

# Servicio para extraer tags y comprimir imágenes

def extraer_tags_y_comprimir(imagenes):
    """
    Descarga imágenes, extrae tags con wd-swinv2-tagger-v3 local y comprime todo en un ZIP.
    """
    zip_buffer = io.BytesIO()
    urls = [(img.get('file_url'), idx+1) for idx, img in enumerate(imagenes) if img.get('file_url')]
    if not urls:
        st.error("No hay URLs válidas para descargar")
        return zip_buffer
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(urls)
    predictor = Predictor()
    model_repo = SWINV2_MODEL_DSV3_REPO
    general_thresh = 0.35
    general_mcut_enabled = False
    character_thresh = 0.85
    character_mcut_enabled = False
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
        for i, (url, idx) in enumerate(urls):
            try:
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                img_bytes = resp.content
                img_name = f"gelbooru_{idx}.jpg"
                zip_file.writestr(img_name, img_bytes)
                image = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                tags, _, _, _ = predictor.predict(
                    image,
                    model_repo,
                    general_thresh,
                    general_mcut_enabled,
                    character_thresh,
                    character_mcut_enabled,
                )
                txt_name = os.path.splitext(img_name)[0] + ".txt"
                zip_file.writestr(txt_name, tags)
            except Exception as e:
                st.warning(f'Error al procesar imagen {idx}: {str(e)}')
            progress = (i + 1) / total
            progress_bar.progress(progress)
            status_text.text(f"Procesando {i+1}/{total} imágenes...")
    progress_bar.empty()
    status_text.empty()
    zip_buffer.seek(0)
    return zip_buffer
