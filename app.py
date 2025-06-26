import streamlit as st
import requests
from typing import List
import io
import zipfile
import pandas as pd
from streamlit_searchbox import st_searchbox

st.set_page_config(page_title="Descargador Gelbooru", layout="wide")
st.title("Descarga de imágenes desde gelbooru.com")
st.markdown("""
Descarga imágenes de Gelbooru, selecciona los tags que quieras incluir y excluir en la busqueda.
""")

st.markdown("""
<style>
    .stButton button {
        height: 32px !important;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        padding: 0 10px !important;
        margin: 5px !important;
    }
    
    /* Contenedor de columnas para evitar espacio no deseado */
    .stHorizontalBlock {
        gap: 0.5rem;  /* Espacio entre columnas */
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def cargar_tags_csv():
    df = pd.read_csv('danbooru_tags_post_count.csv', header=None)
    return df[0].astype(str).tolist()

tags_csv = cargar_tags_csv()

def construir_query_tags(tags: List[str]) -> str:
    tags_incluir = [tag for tag in tags if not tag.startswith('-')]
    tags_excluir = [tag for tag in tags if tag.startswith('-')]
    query = ' '.join(tags_incluir + tags_excluir)
    return query

def buscar_imagenes_gelbooru(api_key: str, user_id: str, tags: List[str], limit: int = 10):
    base_url = 'https://gelbooru.com/index.php'
    params = {
        'page': 'dapi',
        's': 'post',
        'q': 'index',
        'json': 1,
        'api_key': api_key,
        'user_id': user_id,
        'tags': construir_query_tags(tags),
        'limit': limit
    }
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'post' in data:
            return data['post']
        else:
            return []
    except Exception as e:
        st.error(f'Error al buscar imágenes: {e}')
        return []

def descargar_imagenes_en_memoria(imagenes):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for idx, img in enumerate(imagenes, 1):
            url = img.get('file_url')
            if not url:
                continue
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                nombre_archivo = f"gelbooru_{idx}.jpg"
                zip_file.writestr(nombre_archivo, resp.content)
            except Exception as e:
                st.warning(f'Error al descargar imagen {idx}: {e}')
    zip_buffer.seek(0)
    return zip_buffer

if "searchbox_pos_counter" not in st.session_state:
    st.session_state.searchbox_pos_counter = 0
if "searchbox_neg_counter" not in st.session_state:
    st.session_state.searchbox_neg_counter = 0

if "tags" not in st.session_state:
    st.session_state.tags = []
if "tags_neg" not in st.session_state:
    st.session_state.tags_neg = []

def search_tags_local(q):
    return [t for t in tags_csv if q.lower() in t.lower()][:15] if q else []

st.markdown("**Tags positivos:**")
tag = st_searchbox(
    search_function=search_tags_local,
    placeholder="Escribe un tag para agregar",
    label="Buscar tag positivo",
    key=f"tag_searchbox_pos_{st.session_state.searchbox_pos_counter}"
)

if tag and tag not in st.session_state.tags:
    st.session_state.tags.append(tag)
    st.session_state.searchbox_pos_counter += 1 
    st.rerun()

if st.session_state.tags:
    cols = st.columns(5)  # 5 columnas
    for i, t in enumerate(st.session_state.tags):
        if cols[i % 5].button(f"❌ {t}", key=f"del_pos_{t}", use_container_width=True):
            st.session_state.tags.remove(t)
            st.rerun()

st.markdown("**Tags negativos (excluir):**")
tag_neg = st_searchbox(
    search_function=search_tags_local,
    placeholder="Escribe un tag para excluir",
    label="Buscar tag negativo",
    key=f"tag_searchbox_neg_{st.session_state.searchbox_neg_counter}" 
)

if tag_neg and tag_neg not in st.session_state.tags_neg:
    st.session_state.tags_neg.append(tag_neg)
    st.session_state.searchbox_neg_counter += 1 
    st.rerun()

if st.session_state.tags_neg:
    st.markdown("**Tags negativos seleccionados:**")
    cols = st.columns(5)
    for i, t in enumerate(st.session_state.tags_neg):
        if cols[i % 5].button(f"❌ {t}", key=f"del_neg_{t}", use_container_width=True):
            st.session_state.tags_neg.remove(t)
            st.rerun()

num_images = st.number_input("Número de imágenes a descargar", min_value=1, max_value=100, value=10)

if "imagenes" not in st.session_state:
    st.session_state.imagenes = []

if st.button("Buscar y descargar"):
    if not st.session_state.tags and not st.session_state.tags_neg:
        st.error("Por favor, selecciona al menos un tag positivo o negativo.")
    else:
        api_key = "81a22cff97c4318582917a6cde4b8b99ea448e655b3d11df3c9fa55233da13e2595e51e960085805c00374192cd10e0ac781e4135889b832efd2058a6cd43498"
        user_id = "1741452"
        tags = st.session_state.tags + [f"-{t}" for t in st.session_state.tags_neg]
        st.info("Buscando imágenes...")
        imagenes = buscar_imagenes_gelbooru(api_key, user_id, tags, num_images)
        st.session_state.imagenes = imagenes
        st.success(f"Se encontraron {len(imagenes)} imágenes.")

if st.session_state.imagenes:
    st.info("Preparando archivo comprimido para descarga...")
    zip_buffer = descargar_imagenes_en_memoria(st.session_state.imagenes)
    st.download_button(
        label="Descargar todas las imágenes en ZIP",
        data=zip_buffer,
        file_name="imagenes_gelbooru.zip",
        mime="application/zip"
    )
    cols = st.columns(5)
    for idx, img in enumerate(st.session_state.imagenes):
        url = img.get('file_url')
        if url:
            with cols[idx % 5]:
                st.image(url, width=150)