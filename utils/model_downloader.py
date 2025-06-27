import os
import requests
import streamlit as st

def descargar_archivo_si_no_existe(url, path, descripcion, token_env_var="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"):
    """
    Descarga un archivo desde una URL si no existe en la ruta especificada.
    Si se requiere autenticación, usa el token de HuggingFace desde la variable de entorno HF_TOKEN.
    """
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        headers = {}
        token = os.environ.get(token_env_var)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with st.spinner(f"Descargando {descripcion}..."):
            try:
                r = requests.get(url, stream=True, timeout=60, headers=headers)
                r.raise_for_status()
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            except Exception as e:
                st.error(f"No se pudo descargar {descripcion}: {e}")
                st.stop()
