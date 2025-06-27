import streamlit as st
import requests
from typing import List, Tuple, Optional
import io
import zipfile
import pandas as pd
from streamlit_searchbox import st_searchbox
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Configuración inicial de la página
st.set_page_config(page_title="Descargador Gelbooru", layout="wide")
st.title("Descarga de imágenes desde gelbooru.com")
st.markdown("""
Descarga imágenes de Gelbooru, selecciona los tags que quieras incluir y excluir en la busqueda. 
Puedes usarlo para la descarga masiva de imágenes que puedes usar para crear datasets rápidamente y crear modelos de IA.
""")

# Estilos CSS optimizados
st.markdown("""
<style>
    .stButton button {
        height: 32px !important;
        padding: 0 10px !important;
        margin: 5px !important;
    }
    .stHorizontalBlock {
        gap: 0.5rem;
    }
    .thumbnail {
        transition: transform 0.2s;
    }
    .thumbnail:hover {
        transform: scale(1.05);
    }
</style>
""", unsafe_allow_html=True)

# Constantes
MAX_WORKERS = 10  # Número máximo de hilos para descargas concurrentes
IMGS_PER_PAGE = 10  # Imágenes por página en la galería
DEFAULT_API_KEY = "81a22cff97c4318582917a6cde4b8b99ea448e655b3d11df3c9fa55233da13e2595e51e960085805c00374192cd10e0ac781e4135889b832efd2058a6cd43498"
DEFAULT_USER_ID = "1741452"

# Caché para tags
@st.cache_data(ttl=3600, show_spinner="Cargando lista de tags...")
def cargar_tags_csv() -> List[str]:
    try:
        df = pd.read_csv('danbooru_tags_post_count.csv', header=None)
        return df[0].astype(str).tolist()
    except Exception as e:
        st.error(f"Error al cargar tags: {e}")
        return []

# Funciones optimizadas para búsqueda y descarga
def construir_query_tags(tags: List[str]) -> str:
    """Construye la cadena de query para la API de Gelbooru."""
    tags_incluir = [tag for tag in tags if not tag.startswith('-')]
    tags_excluir = [tag for tag in tags if tag.startswith('-')]
    return ' '.join(tags_incluir + tags_excluir)

def buscar_imagenes_gelbooru(
    api_key: str, 
    user_id: str, 
    tags: List[str], 
    limit: int = 10,
    timeout: int = 15
) -> List[dict]:
    """Busca imágenes en Gelbooru con paginación optimizada."""
    base_url = 'https://gelbooru.com/index.php'
    imagenes = []
    por_pagina = 100  # Límite máximo de la API
    
    with st.spinner(f"Buscando hasta {limit} imágenes..."):
        for pid in range((limit - 1) // por_pagina + 1):
            cantidad = min(por_pagina, limit - len(imagenes))
            params = {
                'page': 'dapi',
                's': 'post',
                'q': 'index',
                'json': 1,
                'api_key': api_key,
                'user_id': user_id,
                'tags': construir_query_tags(tags),
                'limit': cantidad,
                'pid': pid
            }
            
            try:
                response = requests.get(base_url, params=params, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                
                if 'post' in data:
                    posts = data['post']
                    imagenes.extend([posts] if isinstance(posts, dict) else posts)
                    
                    if len(posts) < cantidad:
                        break  # No hay más imágenes
                else:
                    break
            except requests.exceptions.RequestException as e:
                st.error(f'Error en la petición: {str(e)}')
                break
            except Exception as e:
                st.error(f'Error inesperado: {str(e)}')
                break
    
    return imagenes[:limit]

def descargar_imagen(url: str, idx: int) -> Optional[Tuple[int, bytes, str]]:
    """Descarga una imagen individual con manejo de errores."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return (idx, resp.content, f"gelbooru_{idx}.jpg")
    except Exception as e:
        st.warning(f'Error al descargar imagen {idx}: {str(e)}')
        return None

def descargar_imagenes_en_memoria(imagenes: List[dict]) -> io.BytesIO:
    """Descarga y comprime imágenes concurrentemente con progreso."""
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
                
                # Actualizar progreso
                progress = (i + 1) / total
                progress_bar.progress(progress)
                status_text.text(f"Descargando {i+1}/{total} imágenes...")
    
    progress_bar.empty()
    status_text.empty()
    zip_buffer.seek(0)
    return zip_buffer

# Inicialización del estado de la sesión
def inicializar_estado():
    if "searchbox_pos_counter" not in st.session_state:
        st.session_state.searchbox_pos_counter = 0
    if "searchbox_neg_counter" not in st.session_state:
        st.session_state.searchbox_neg_counter = 0
    if "tags" not in st.session_state:
        st.session_state.tags = []
    if "tags_neg" not in st.session_state:
        st.session_state.tags_neg = []
    if "imagenes" not in st.session_state:
        st.session_state.imagenes = []
    if "imagenes_pagina" not in st.session_state:
        st.session_state.imagenes_pagina = 0

# Componentes de la UI
def mostrar_tags(tags: List[str], key_prefix: str) -> bool:
    """Muestra los tags como botones y maneja su eliminación."""
    if not tags:
        return False
    
    cols = st.columns(5)
    for i, t in enumerate(tags):
        if cols[i % 5].button(f"❌ {t}", key=f"{key_prefix}_{t}", use_container_width=True):
            tags.remove(t)
            st.rerun()
    return True

def mostrar_galeria(imagenes: List[dict], imagenes_por_pagina: int = IMGS_PER_PAGE):
    """Muestra la galería de imágenes con paginación."""
    total_imgs = len(imagenes)
    total_paginas = max(1, (total_imgs - 1) // imagenes_por_pagina + 1)
    pag_actual = st.session_state.imagenes_pagina
    
    # Asegurar que la página actual esté en rango válido
    pag_actual = max(0, min(pag_actual, total_paginas - 1))
    st.session_state.imagenes_pagina = pag_actual
    
    # Mostrar miniaturas
    inicio = pag_actual * imagenes_por_pagina
    fin = min(inicio + imagenes_por_pagina, total_imgs)
    
    cols = st.columns(5)
    for idx, img in enumerate(imagenes[inicio:fin]):
        thumb_url = img.get('preview_url') or img.get('thumbnail_url') or img.get('file_url')
        if thumb_url:
            try:
                resp = requests.get(thumb_url, timeout=10)
                resp.raise_for_status()
                with cols[idx % 5]:
                    st.image(
                        resp.content,
                        width=150,
                        caption=f"Imagen {inicio + idx + 1}",
                        use_container_width=True,
                        output_format="JPEG"
                    )
            except Exception:
                pass
    
    # Controles de paginación
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("Anterior", disabled=pag_actual == 0, key="btn_prev"):
            st.session_state.imagenes_pagina -= 1
            st.rerun()
    with col3:
        if st.button("Siguiente", disabled=pag_actual >= total_paginas - 1, key="btn_next"):
            st.session_state.imagenes_pagina += 1
            st.rerun()
    with col2:
        st.markdown(
            f"<div style='text-align:center;'>Página {pag_actual+1} de {total_paginas}</div>", 
            unsafe_allow_html=True
        )

# Función principal
def main():
    inicializar_estado()
    tags_csv = cargar_tags_csv()
    
    def search_tags_local(q: str) -> List[str]:
        """Busca tags locales con coincidencia parcial."""
        return [t for t in tags_csv if q.lower() in t.lower()][:15] if q else []
    
    # UI para tags positivos
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
    
    if mostrar_tags(st.session_state.tags, "del_pos"):
        st.markdown("---")
    
    # UI para tags negativos
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
    
    if mostrar_tags(st.session_state.tags_neg, "del_neg"):
        st.markdown("---")
    
    # Configuración de descarga
    num_images = st.number_input(
        "Número de imágenes a descargar", 
        min_value=1, 
        max_value=1000, 
        value=10,
        help="Máximo 1000 imágenes por búsqueda"
    )
    
    # Botón de búsqueda
    if st.button("Buscar Imágenes", type="primary"):
        if not st.session_state.tags and not st.session_state.tags_neg:
            st.error("Por favor, selecciona al menos un tag positivo o negativo.")
        else:
            tags = st.session_state.tags + [f"-{t}" for t in st.session_state.tags_neg]
            with st.spinner("Buscando imágenes..."):
                st.session_state.imagenes = buscar_imagenes_gelbooru(
                    DEFAULT_API_KEY, 
                    DEFAULT_USER_ID, 
                    tags, 
                    num_images
                )
            st.session_state.imagenes_pagina = 0
            st.success(f"Se encontraron {len(st.session_state.imagenes)} imágenes.")
    
    # Mostrar galería si hay imágenes
    if st.session_state.imagenes:
        mostrar_galeria(st.session_state.imagenes)
        
        # Botón de descarga ZIP
        if st.button("Comprimir todas las imágenes en ZIP", type="secondary"):
            start_time = time.time()
            with st.spinner("Preparando archivo ZIP..."):
                zip_buffer = descargar_imagenes_en_memoria(st.session_state.imagenes)
                elapsed = time.time() - start_time
                st.success(f"Archivo ZIP listo en {elapsed:.2f} segundos")
                
                st.download_button(
                    label="Descargar ZIP",
                    data=zip_buffer,
                    file_name="imagenes_gelbooru.zip",
                    mime="application/zip",
                    type="primary"
                )

if __name__ == "__main__":
    main()