import streamlit as st
import numpy as np
from PIL import Image
from stl import mesh
import io

st.set_page_config(page_title="Gerador 2D para STL", page_icon="🧊", layout="centered")

st.title("🧊 Imagem 2D para STL 3D")
st.write("Faça o upload de uma imagem e gere o arquivo STL pronto para impressão 3D.")

# Upload da imagem
arquivo_imagem = st.file_uploader("Escolha uma imagem (JPG, PNG)", type=["jpg", "jpeg", "png"])

if arquivo_imagem is not None:
    img = Image.open(arquivo_imagem)
    st.image(img, caption="Imagem Carregada", use_column_width=True)

    # Parâmetros na barra lateral
    st.sidebar.header("⚙️ Ajustes do Relevo")
    largura_mm = st.sidebar.slider("Largura (mm)", 30, 200, 100)
    altura_max_mm = st.sidebar.slider("Altura Máxima do Relevo (mm)", 1.0, 20.0, 5.0)
    espessura_base_mm = st.sidebar.slider("Espessura da Base (mm)", 0.5, 10.0, 1.5)
    inverter = st.sidebar.checkbox("Inverter cores (Litofania / Negativo)", value=False)

    if st.button("Gerar STL"):
        with st.spinner("Processando malha 3D..."):
            # Converte para cinza e limita tamanho para manter a nuvem rápida
            img_gray = img.convert("L")
            img_gray.thumbnail((250, 250))

            largura_px, altura_px = img_gray.size
            proporcao = altura_px / largura_px
            comprimento_mm = largura_mm * proporcao

            dados = np.array(img_gray) / 255.0
            if inverter:
                dados = 1.0 - dados

            z_map = espessura_base_mm + (dados * altura_max_mm)

            x = np.linspace(0, largura_mm, largura_px)
            y = np.linspace(0, comprimento_mm, altura_px)
            xv, yv = np.meshgrid(x, y)

            num_triangulos = (largura_px - 1) * (altura_px - 1) * 2
            superficie = mesh.Mesh(np.zeros(num_triangulos, dtype=mesh.Mesh.dtype))

            indice = 0
            for i in range(altura_px - 1):
                for j in range(largura_px - 1):
                    p1 = [xv[i, j], yv[i, j], z_map[i, j]]
                    p2 = [xv[i, j + 1], yv[i, j + 1], z_map[i, j + 1]]
                    p3 = [xv[i + 1, j], yv[i + 1, j], z_map[i + 1, j]]
                    p4 = [xv[i + 1, j + 1], yv[i + 1, j + 1], z_map[i + 1, j + 1]]

                    superficie.vectors[indice] = np.array([p1, p3, p2])
                    superficie.vectors[indice + 1] = np.array([p2, p3, p4])
                    indice += 2

            # Salva em memória (buffer) para download
            buffer_stl = io.BytesIO()
            superficie.save("temp.stl")
            with open("temp.stl", "rb") as f:
                buffer_stl.write(f.read())
            buffer_stl.seek(0)

            st.success("Modelo 3D gerado com sucesso!")
            st.download_button(
                label="📥 Baixar arquivo STL",
                data=buffer_stl,
                file_name="modelo_3d.stl",
                mime="application/sla"
            )
