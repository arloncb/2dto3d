import streamlit as st
import numpy as np
from PIL import Image
import trimesh
import requests
import io
import time
import os

# Configuração da página
st.set_page_config(page_title="Gerador 3D - Relevo & IA", layout="centered")

st.title(" Conversor de Imagem para 3D")
st.write("Crie modelos 3D a partir de fotos usando processamento local (Relevo STL) ou IA completa (Tripo3D GLB).")

# Obter a chave API dos Secrets do Streamlit ou variáveis de ambiente
TRIPO_API_KEY = st.secrets.get("TRIPO_API_KEY", os.getenv("TRIPO_API_KEY", ""))

# Sidebar com configurações
st.sidebar.header(" Configurações")
modo = st.sidebar.radio(
    "Modo de Geração:",
    ("Relevo em Altura (Local - STL)", "IA Tripo3D (Escultura Completa 360° - GLB)")
)

if modo == "Relevo em Altura (Local - STL)":
    altura_max = st.sidebar.slider("Altura Máxima do Relevo (mm)", 1.0, 30.0, 10.0)
    base_espessura = st.sidebar.slider("Espessura da Base (mm)", 0.5, 10.0, 2.0)
    inverter = st.sidebar.checkbox("Inverter Alturas (Tons escuros mais altos)", value=False)
else:
    if not TRIPO_API_KEY:
        st.sidebar.warning("⚠️ Chave TRIPO_API_KEY não encontrada nos Secrets!")

# --- FUNÇÃO 1: RELEVO LOCAL EM STL ---
def criar_relevo_stl(imagem_pil, altura, base, inverter_alturas):
    # Converte para tons de cinza
    img_gray = imagem_pil.convert('L')
    
    # Redimensiona para manter o desempenho ágil
    max_res = 350
    img_gray.thumbnail((max_res, max_res), Image.Resampling.LANCZOS)
    
    arr = np.array(img_gray, dtype=np.float32)
    if inverter_alturas:
        arr = 255.0 - arr
    
    # Normaliza entre 0 e a altura desejada
    arr = (arr / 255.0) * altura + base
    
    largura, comprimento = arr.shape[1], arr.shape[0]
    
    # Cria vértices
    x = np.arange(largura)
    y = np.arange(comprimento)
    xx, yy = np.meshgrid(x, y)
    
    vertices = np.column_stack((xx.flatten(), yy.flatten(), arr.flatten()))
    
    # Cria faces (triângulos)
    faces = []
    for i in range(comprimento - 1):
        for j in range(largura - 1):
            idx = i * largura + j
            # Triângulo 1
            faces.append([idx, idx + largura, idx + 1])
            # Triângulo 2
            faces.append([idx + 1, idx + largura, idx + largura + 1])
            
    mesh = trimesh.Trimesh(vertices=vertices, faces=np.array(faces))
    
    # Exporta para STL
    stl_io = io.BytesIO()
    mesh.export(stl_io, file_type='stl')
    return stl_io.getvalue()

# --- FUNÇÃO 2: IA TRIPO3D V3 ---
def tripo_image_to_3d(image_bytes, filename):
    headers = {"Authorization": f"Bearer {TRIPO_API_KEY}"}
    
    # 1. Enviar arquivo para a Tripo (/v3/files)
    st.info("📤 Enviando imagem para os servidores da IA...")
    files = {"file": (filename, image_bytes)}
    upload_res = requests.post("https://openapi.tripo3d.ai/v3/files", headers=headers, files=files)
    
    if upload_res.status_code != 200:
        st.error(f"Erro no envio da imagem: {upload_res.text}")
        return None
        
    file_token = upload_res.json().get("data", {}).get("file_token")

    # 2. Criar tarefa com o nome da versão aceita pela API
    st.info("🤖 Iniciando IA de reconstrução 3D...")
    task_payload = {
        "input": file_token,
        "model": "v3.1-20260211"
    }
    task_res = requests.post("https://openapi.tripo3d.ai/v3/generation/image-to-model", headers=headers, json=task_payload)
    
    if task_res.status_code != 200:
        st.error(f"Erro ao criar tarefa: {task_res.text}")
        return None

    task_id = task_res.json().get("data", {}).get("task_id")

    # 3. Consultar status (/v3/tasks/{task_id})
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for _ in range(60):  # Aguarda até 2 minutos
        time.sleep(2)
        status_res = requests.get(f"https://openapi.tripo3d.ai/v3/tasks/{task_id}", headers=headers)
        if status_res.status_code == 200:
            data = status_res.json().get("data", {})
            status = data.get("status")
            progress = data.get("progress", 0)
            
            progress_bar.progress(progress / 100.0)
            status_text.text(f"Progresso da IA: {progress}% (Status: {status})")

            if status == "success":
                output = data.get("output", {})
                model_url = output.get("model_url") or output.get("model")
                status_text.text("✅ Modelo gerado com sucesso!")
                
                # Baixa o modelo gerado (.glb)
                model_download = requests.get(model_url)
                return model_download.content
            elif status in ["failed", "cancelled"]:
                st.error("A IA falhou ao reconstruir o modelo.")
                return None
                
    st.warning("Tempo limite excedido. Tente novamente.")
    return None

# --- INTERFACE PRINCIPAL ---
arquivo = st.file_uploader("Selecione uma imagem (JPG, PNG ou WEBP)", type=["jpg", "jpeg", "png", "webp"])

if arquivo is not None:
    imagem = Image.open(arquivo)
    st.image(imagem, caption="Imagem Carregada", use_container_width=True)
    
    if modo == "Relevo em Altura (Local - STL)":
        if st.button("Gerar Relevo STL"):
            with st.spinner("Processando malha 3D localmente..."):
                stl_bytes = criar_relevo_stl(imagem, altura_max, base_espessura, inverter)
                st.success("Relevo 3D gerado com sucesso!")
                st.download_button(
                    label="⬇️ Baixar Arquivo .STL",
                    data=stl_bytes,
                    file_name="relevo_3d.stl",
                    mime="model/stl"
                )
                
    else:  # Modo IA Tripo3D
        if st.button("Gerar Modelo 3D com IA"):
            if not TRIPO_API_KEY:
                st.error("Configure sua chave TRIPO_API_KEY nos Secrets do Streamlit antes de continuar.")
            else:
                arquivo.seek(0)
                glb_bytes = tripo_image_to_3d(arquivo.read(), arquivo.name)
                if glb_bytes:
                    st.download_button(
                        label="⬇️ Baixar Modelo Completo (.GLB)",
                        data=glb_bytes,
                        file_name="modelo_3d.glb",
                        mime="model/gltf-binary"
                    )
