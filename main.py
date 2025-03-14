import streamlit as st
import boto3 
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from PIL import Image, ImageDraw, ImageFont
import io
import difflib


def config():
    st.set_page_config(
        page_title="FACE & TEXT EXTRACTION",
        page_icon=r"./logo.jpeg",
        initial_sidebar_state="expanded",
    )


# side bar que para enviar os 3 arquivos e colocar parte do endereço para fazer um match com a conta
def upload_documentos(): 

    st.title("Upload de Documentos")

    # Sidebar para uploads
    with st.sidebar:
        st.header("Uploads")
        cnh = st.file_uploader("Faça o upload da CNH", type=["png", "jpg", "jpeg"], key="cnh")
        foto_rosto = st.file_uploader("Faça o upload da Foto do Rosto", type=["png", "jpg", "jpeg"], key="rosto")
        conta = st.file_uploader("Faça o upload de uma Conta", type=["png", "jpg", "jpeg"], key="conta")
        endereco = st.text_input("Digite o endereço")

    # Exibição das imagens lado a lado
    cols = st.columns(3)

    imagens = [(cnh, "CNH"), (foto_rosto, "Foto do Rosto"), (conta, "Conta")]

    # Estado para controle de imagem expandida
    if "imagem_expandida" not in st.session_state:
        st.session_state.imagem_expandida = None

    for col, (imagem, legenda) in zip(cols, imagens):
        if imagem:
            img = Image.open(imagem)
            col.image(img, caption=legenda, width=100)
            if col.button(f"Ver {legenda}"):
                st.session_state.imagem_expandida = img
                st.session_state.legenda_expandida = legenda

    # botao para fechar as imagens expandidas
    if st.session_state.imagem_expandida:
        st.image(st.session_state.imagem_expandida, caption=st.session_state.legenda_expandida, use_container_width=True)
        if st.button("Fechar imagem"):
            st.session_state.imagem_expandida = None

    if endereco:
        st.write("**Endereço informado:**", endereco)


    return (cnh, foto_rosto, conta, endereco)


#usando o textract da aws para pegar todos os texto do arquivo enviado.
def processar_arquivo(uploaded_file):

    if uploaded_file is not None:
        # Converter arquivo em bytes
        bytes_test = uploaded_file.getvalue()

        # Configuração do Textract
        session = boto3.Session(aws_access_key_id=ACCESS_ID, aws_secret_access_key=ACCESS_KEY)
        client = session.client('textract', region_name=region)
        response = client.analyze_document(Document={'Bytes': bytes_test}, FeatureTypes=['FORMS'])

        return response

#o nome da pessoa no cnh fica abaixo da frase "1ª HABILITAÇÃO", entao essa função pegar o nome apos essa frase
def encontrar_nome(blocks, referencia="1ª HABILITAÇÃO"):
    capturar = False
    
    for block in blocks:
        if block["BlockType"] == "LINE" and int(block["Confidence"]) > 50:
            if capturar:
                return block["Text"]  # Retorna a próxima frase encontrada
            if block["Text"] == referencia:
                capturar = True  # Ativa a captura para a próxima iteração
    
    return None 

# igualmente a função a cima, apos a frase "9 CAT HAB" é o CPF
def encontrar_cpf(blocks, referencias=("9 CAT HAB", "9 CAT. HAB.")):
    capturar = False
    cpf_encontrado = None

    for block in blocks:
        if block["BlockType"] == "LINE" and int(block["Confidence"]) > 50:
            if capturar:
                cpf_encontrado = block["Text"]
                break 
            if block["Text"] in referencias:
                capturar = True  
    
    return cpf_encontrado if cpf_encontrado else None


def processar_imagem(file_source, file_target):
    # Verificando se os arquivos foram carregados corretamente
    if file_source is None or file_target is None:
        raise ValueError("Ambos os arquivos de imagem devem ser fornecidos.")

    try:
        # Lendo os arquivos de imagem em bytes, como ja foi lido pelo streamlit, faço a releitura para usar na aws
        bytes_file_source = file_source.getvalue() 
        bytes_file_target = file_target.getvalue() 


    except Exception as e:
        raise ValueError(f"Erro ao ler os arquivos de imagem: {e}")

    # Verificando se os bytes lidos não estão vazios
    if len(bytes_file_source) == 0 or len(bytes_file_target) == 0:
        raise ValueError("Erro ao ler os arquivos de imagem. Certifique-se de que os arquivos não estão vazios.")




    session = boto3.Session(aws_access_key_id=ACCESS_ID, aws_secret_access_key=ACCESS_KEY)
    client = session.client("rekognition", region_name=region)

    # Realizando a comparação das faces
    try:
        response = client.compare_faces(
            SourceImage={'Bytes': bytes_file_source},
            TargetImage={'Bytes': bytes_file_target},
        )
    except Exception as e:
        raise ValueError(f"Erro ao realizar a comparação de faces: {e}")

    return response

# aqui a gente faz um match, entao enviamos a palavra que queremos encontrar e o json que contem todo o texto.
def encontrar_nome_conta(cnh_nome, texto):

    for linha in texto:
        if cnh_nome.upper() in linha.upper():
            return linha  # Nome exato encontrado

    # Se não achou o nome exato, tenta encontrar o mais parecido
    melhor_match = difflib.get_close_matches(cnh_nome, texto, n=1, cutoff=0.6)
    return melhor_match[0] if melhor_match else None





#recebendo a key que esta no secret do streamlit
ACCESS_ID = st.secrets["ACCESS_ID"]
ACCESS_KEY = st.secrets["ACCESS_KEY"]
region = st.secrets["REGION"]


if __name__ == '__main__':
    
    config()

    st.title('Trabalho - Cognitive Environments')

    #recendo as imagens e textos do front-end
    cnh, foto_rosto, conta, endereco = upload_documentos()

    
    st.title("Informações capturadas")
    
    if cnh: 
        
        
        #recebendo a imagen do front, enviado para o textract e 
        #usando as funções para capturar o nome e cpf como ja mencionado 

        response_cnh = processar_arquivo(cnh)
        blocks  = response_cnh["Blocks"] 
        nome_cnh = encontrar_nome(blocks)
        nome_cnh_str = str(nome_cnh)

        cpf = encontrar_cpf(blocks)

        st.write('Nome: ', nome_cnh_str)
        st.write('CPF: ',cpf)

        #quando inserido a foto e a cnh inciamos essa função para fazer a comparação das imagens.
        if foto_rosto and cnh:
            comparacao = processar_imagem(cnh, foto_rosto)
          
            face_matches = comparacao.get("FaceMatches", [])
            threshold = 90 # threshold definido no trabalho.

            if not face_matches:
                st.write("As imagens não correspondem à mesma pessoa.")
            else:
                similarity = face_matches[0]['Similarity']
                if similarity >= threshold:
                    st.write(f"Confirmação: É a mesma pessoa (Similaridade: {similarity:.2f}%)")
                else:
                    st.write(f"Não é a mesma pessoa (Similaridade: {similarity:.2f}%)")

                # Processar e exibir a imagem com a caixa delimitadora
                if "SourceImageFace" in comparacao:
                    image_cnh = Image.open(cnh)
                    imgWidth, imgHeight = image_cnh.size
                    draw = ImageDraw.Draw(image_cnh)

                    # Extraindo a caixa delimitadora da face
                    box = comparacao["SourceImageFace"]["BoundingBox"]
                    top = imgHeight * box['Top']
                    left = imgWidth * box['Left']
                    width = imgWidth * box['Width']
                    height = imgHeight * box['Height']

                    draw.rectangle([left, top, left + width, top + height], outline='#00d400')

                    # Exibindo a imagem 
                    st.image(image_cnh, caption="Imagem com Caixa Delimitadora", use_container_width=True)



                # ajuste de tamanho de fonte
                font = ImageFont.truetype("./arial.ttf", 25)

                # imagem alvo
                image = Image.open(foto_rosto)
                imgWidth, imgHeight = image.size
                draw_rosto = ImageDraw.Draw(image)

                # analisando cada detecção de face
                for item_match in comparacao["FaceMatches"]:

                    box = item_match["Face"]["BoundingBox"]
                    top = imgHeight * box['Top']
                    left = imgWidth * box['Left']
                    width = imgWidth * box['Width']
                    height = imgHeight * box['Height']


                    draw_rosto.rectangle([left,top, left + width, top + height], outline='#00d400')
                    draw_rosto.text((left, top), "Similaridade: "+ str(item_match["Similarity"]), font=font)

                    st.image(image, caption="Imagem com Caixa Delimitadora", use_container_width=True)

    
    #quando a pessoa coloca a conta, cnh, e parte do texto do seu endereço que esta na conta. Fazemos uma match, 
    #com as informações ja obtida pela cnh e verifcamos com a conta inserida.

    if conta and cnh and endereco:
        response_conta = processar_arquivo(conta)
        texto_extraido_conta = [block["Text"] for block in response_conta["Blocks"] if block["BlockType"] == "LINE"]

        
        nome = encontrar_nome_conta(nome_cnh_str, texto_extraido_conta)
        
        #verificando se a conta tem o mesmo nome que na CNH.
        if nome:
            st.write('Nome na Conta: ', nome)
        else:
            st.write('Nome não correspontente com a CNH.')

        #verificando se o texto informado bate com que esta na conta. 
        # pensamos nessa solução, pois queremos verifica em qualquer modelo de conta, ao inves de ter apenas um modelo.
        rua = encontrar_nome_conta(endereco, texto_extraido_conta)
        if rua:
            st.write('Endereço da conta: ', rua)
        else:
            st.write('Endereço não encontrado no documento anexado.')