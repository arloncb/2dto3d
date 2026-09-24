import streamlit as st
import numpy as np
from PIL import Image
from stl import mesh
import io
import time
import requests

# Configuração da página
st.set_page_config(page_title="Gerador 3D Multi-Modo", layout="wide")
st.title(" Gerador de Modelos 3D a partir de Imagens")

# Chave da API Tripo (Configurada)
TRIPO_API_KEY = "tsk_IB_MJ9GR7Mn9eV0qXdYamU05XNEiEDzGpI3XUUl0l5b"

# Menu lateral para escolher o modo
st.sidebar.header(" Configurações")
modo = st.sidebar.radio(
    "Escolha o Tipo de Geração:",
    (" Litofania / Relevo (Rápido - STL)", " IA Tripo3D (Escultura Completa 360° - GLB)")
)

# Upload da Imagem
uploaded_file = st.file_uploader("Envie sua imagem (PNG, JPG, WEBP)", type=["png", "jpg", "jpeg", "webp"])

# --- FUNÇÃO 1: RELEVO / LITOFANIA ---
def image_to_stl(image_bytes, base_th, max_h, max_w):
    img = Image.open(io.BytesIO(image_bytes)).convert('L')
    w_percent = (max_w / float(img.size[0]))
    h_size = int((float(img.size[1]) * float(w_percent)))
    img = img.resize((max_w, h_size), Image.Resampling.LANCZOS)
    
    img_array = np.array(img, dtype=float)
    img_array = (img_array / 255.0) * max_h + base_th
    rows, cols = img_array.shape

    num_triangles = (rows - 1) * (cols - 1) * 2
    stl_mesh = mesh.Mesh(np.zeros(num_triangles, dtype=mesh.Mesh.dtype))

    triangle_idx = 0
    for i in range(rows - 1):
        for j in range(cols - 1):
            p1 = [j, rows - 1 - i, img_array[i, j]]
            p2 = [j + 1, rows - 1 - i, img_array[i, j + 1]]
            p3 = [j, rows - 1 - (i + 1), img_array[i + 1, j]]
            p4 = [j + 1, rows - 1 - (i + 1), img_array[i + 1, j + 1]]

            stl_mesh.vectors[triangle_idx] = np.array([p1, p2, p3])
            stl_mesh.vectors[triangle_idx + 1] = np.array([p2, p4, p3])
            triangle_idx += 2

    stl_buffer = io.BytesIO()
    stl_mesh.save(stl_buffer)
    stl_buffer.seek(0)
    return stl_buffer

# --- FUNÇÃO 2: IA TRIPO3D V3 ---
def tripo_image_to_3d(image_bytes, filename):
    headers = {"Authorization": f"Bearer {TRIPO_API_KEY}"}
    
    # 1. Enviar arquivo para a Tripo
    st.info(" Enviando imagem para os servidores da IA...")
    files = {"file": (filename, image_bytes)}
    upload_res = requests.post("https://openapi.tripo3d.ai/v3/files", headers=headers, files=files)
    
    if upload_res.status_code != 200:
        st.error(f"Erro no envio da imagem: {upload_res.text}")
        return None
        
    file_token = upload_res.json()["data"]["file_token"]

    # 2. Criar tarefa de conversão Image-to-Model
    st.info(" Iniciando IA de reconstrução 3D...")
    task_payload = {
        "type": "image_to_model",
        "file": {
            "type": filename.split('.')[-1].lower(),
            "file_token": file_token
        }
    }
    task_res = requests.post("https://openapi.tripo3d.ai/v3/task", headers=headers, json=task_payload)
    
    if task_res.status_code != 200:
        st.error(f"Erro ao criar tarefa: {task_res.text}")
        return None

    task_id = task_res.json()["data"]["task_id"]

    # 3. Aguardar processamento (Polling)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for _ in range(60): # Espera até ~2 minutos
        time.sleep(2)
        status_res = requests.get(f"https://openapi.tripo3d.ai/v3/task/{task_id}", headers=headers)
        if status_res.status_code == 200:
            data = status_res.json()["data"]
            status = data.get("status")
            progress = data.get("progress", 0)
            
            progress_bar.progress(progress / 100.0)
            status_text.text(f"Progresso da IA: {progress}% (Status: {status})")

            if status == "success":
                model_url = data["output"]["model"]
                status_text.text(" Modelo gerado com sucesso!")
                
                # Baixa o modelo final
                model_download = requests.get(model_url)
                return model_download.content
            elif status in ["failed", "cancelled"]:
                st.error("A IA falhou ao reconstruir o modelo.")
                return None
                
    st.warning("Tempo limite excedido. Tente novamente.")
    return None

# --- EXECUÇÃO PRINCIPAL ---
if uploaded_file is not None:
    col1, col2 = st.columns(2)
    with col1:
        st.image(uploaded_file, caption="Imagem Original", use_container_width=True)

    with col2:
        if modo.startswith(" Litofania"):
            st.subheader("Parâmetros do Relevo")
            base_th = st.sidebar.slider("Espessura da Base (mm)", 0.4, 5.0, 1.0)
            max_h = st.sidebar.slider("Altura Máxima do Relevo (mm)", 1.0, 15.0, 4.0)
            resolucao = st.sidebar.slider("Largura / Resolução (px)", 50, 400, 150)
            
            if st.button("Gerar STL de Relevo"):
                with st.spinner("Esculpindo malha..."):
                    stl_data = image_to_stl(uploaded_file.getvalue(), base_th, max_h, resolucao)
                    st.success("Relevo pronto!")
                    st.download_button(
                        label=" Baixar Arquivo .STL",
                        data=stl_data,
                        file_name="relevo_litofania.stl",
                        mime="application/octet-stream"
                    )

        else:
            st.subheader("Modo Escultura Completa com IA")
            st.write("A inteligência artificial irá criar a geometria frontal e traseira da imagem.")
            
            if st.button("Gerar Modelo 3D com IA"):
                model_data = tripo_image_to_3d(uploaded_file.getvalue(), uploaded_file.name)
                if model_data:
                    st.download_button(
                        label=" Baixar Modelo 3D (.GLB)",
                        data=model_data,
                        file_name="objeto_completo_3d.glb",
                        mime="model/gltf-binary"
                    )
