import io
import re
import pytesseract
from pdf2image import convert_from_bytes
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship

# --- 1. CONFIGURAÇÃO DO BANCO (POSTGRESQL) ---
SQLALCHEMY_DATABASE_URL = "postgresql://admin:senha_segura_123@localhost:5432/eleicoes_2024"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 2. MODELOS ---
class Boletim(Base):
    __tablename__ = "boletins"
    id = Column(Integer, primary_key=True, index=True)
    arquivo_nome = Column(String)
    secao = Column(String)
    zona = Column(String)
    municipio = Column(String)
    votos = relationship("Voto", back_populates="boletim")

class Voto(Base):
    __tablename__ = "votos"
    id = Column(Integer, primary_key=True, index=True)
    boletim_id = Column(Integer, ForeignKey("boletins.id"))
    cargo = Column(String)
    numero = Column(Integer)
    nome = Column(String)
    qtd_votos = Column(Integer)
    boletim = relationship("Boletim", back_populates="votos")

Base.metadata.create_all(bind=engine)

def extrair_dados_com_ocr(file_bytes):
    print("Iniciando conversão PDF -> Imagem...")
    imagens = convert_from_bytes(file_bytes, dpi=350)
    
    texto_completo = ""
    print(f"PDF convertido. Total de páginas: {len(imagens)}")

    for i, imagem in enumerate(imagens):
        print(f"Lendo página {i+1} com OCR...")
        # Adicionei config='--psm 6' que assume um bloco único de texto (ajuda em tabelas quebradas)
        texto_pagina = pytesseract.image_to_string(imagem, lang='por', config='--psm 6')
        texto_completo += texto_pagina + "\n"

    print("--- DEBUG (Amostra do Texto Bruto) ---")
    print(texto_completo[:500])
    print("--------------------------------------")

    dados = {
        "metadata": {"zona": "N/A", "secao": "N/A", "municipio": "N/A"},
        "votos": []
    }

    # --- 1. METADADOS (ZONA/SEÇÃO/MUNICIPIO) ---
    # Procura padrão exato: "23027 0020 1481 0220"
    match_header = re.search(r"(\d{5})\s+(\d{4})\s+(\d{4})\s+(\d{4})", texto_completo)
    if match_header:
        dados["metadata"]["municipio"] = match_header.group(1)
        dados["metadata"]["zona"] = match_header.group(2)
        dados["metadata"]["secao"] = match_header.group(4)
        print(f"DEBUG: Seção Identificada: {dados['metadata']['secao']}")
    else:
        # Fallback: Procura "Seção 0220" isolada
        match_secao = re.search(r"Se[cç][ãa]o.*?\n.*?(\d{4})", texto_completo, re.IGNORECASE | re.DOTALL)
        if match_secao:
            dados["metadata"]["secao"] = match_secao.group(1)

    # --- 2. PREPARAÇÃO DO TEXTO ---
    # Quebra em linhas e remove linhas vazias ou inúteis
    linhas_brutas = texto_completo.split('\n')
    linhas = [l.strip() for l in linhas_brutas if l.strip()]
    
    total_linhas = len(linhas)
    cargo_atual = None
    
    # --- FUNÇÃO AUXILIAR DE BUSCA DE VOTO ---
    def buscar_voto_nas_proximas_linhas(indice_atual, max_busca=8):
        """
        Olha as próximas 'max_busca' linhas. 
        Retorna o primeiro número inteiro válido que encontrar.
        Ignora palavras como 'Votação', 'Total', etc.
        """
        for j in range(1, max_busca + 1):
            if indice_atual + j >= total_linhas:
                break
            
            prox_linha = linhas[indice_atual + j].upper().strip()
            
            # Limpa sujeira comum
            prox_linha = prox_linha.replace("VOTAÇÃO", "").replace(".", "").strip()
            
            # Se a linha virou um número puro, é o nosso voto
            if prox_linha.isdigit():
                return int(prox_linha), j # Retorna o voto e quantas linhas pulou
            
            # Se encontrar outro candidato ou cabeçalho importante, PARE (para não pegar voto do vizinho)
            # Ex: Se achar "Partido" ou outro número de 5 dígitos, aborta.
            if "PARTIDO" in prox_linha or re.match(r"\d{5}", prox_linha):
                break
                
        return None, 0

    # --- 3. LOOP DE EXTRAÇÃO ---
    i = 0
    while i < total_linhas:
        linha = linhas[i]

        # Detecta Cargo
        if "PREFEITO" in linha.upper() and "VICE" not in linha.upper(): cargo_atual = "prefeito"
        if "VEREADOR" in linha.upper(): cargo_atual = "vereador"

        # --- LÓGICA VEREADOR (5 DÍGITOS) ---
        if cargo_atual == "vereador":
            # Regex que aceita sujeira antes do número (flexível)
            match = re.search(r"(\d{5})\s+(.+)", linha)
            if match:
                num = int(match.group(1))
                nome_sujo = match.group(2).strip()
                
                # Tenta achar voto na MESMA linha
                match_voto_fim = re.search(r"(\d+)$", nome_sujo)
                
                voto_final = None
                nome_final = nome_sujo

                if match_voto_fim:
                    voto_final = int(match_voto_fim.group(1))
                    nome_final = nome_sujo.replace(match_voto_fim.group(1), "").strip()
                else:
                    voto_encontrado, pulo = buscar_voto_nas_proximas_linhas(i)
                    if voto_encontrado is not None:
                        voto_final = voto_encontrado
                        nome_final = nome_sujo
                
                # ---> LIMPEZA: Remove a palavra 'Votação' com possível duplicidade
                palavras_lixo = ["Votação", "Votaçã", "Votacao", "Votos", "Total", "Partido"]
                for lixo in palavras_lixo:
                    padrao = re.compile(re.escape(lixo), re.IGNORECASE)
                    nome_final = padrao.sub("", nome_final)

                nome_final = nome_final.strip()
                while nome_final and nome_final[-1] in ".-_ ":
                    nome_final = nome_final[:-1].strip()

                if voto_final is not None:
                    print(f"Vereador Capturado: {num} - {nome_final} - {voto_final}")
                    dados["votos"].append({
                        "cargo": "vereador",
                        "numero": num,
                        "nome": nome_final,
                        "qtd": voto_final
                    })

        # --- LÓGICA PREFEITO (2 DÍGITOS) ---
        # Refinada para pegar casos onde o voto está longe
        elif cargo_atual == "prefeito":
            match = re.search(r"^(\d{2})\s+(.+)", linha)
            if match:
                try:
                    num = int(match.group(1))
                    # Filtra falsos positivos (números de seção, zona, totais)
                    if 10 <= num <= 99:
                        nome_sujo = match.group(2).strip()
                        
                        # Palavras proibidas no nome (cabeçalhos que parecem candidatos)
                        if any(x in nome_sujo.upper() for x in ["ZONA", "SEÇÃO", "APTOS", "NOMINAIS", "BRANCO", "NULOS"]):
                            i += 1
                            continue

                        voto_final = None
                        
                        # Tenta mesma linha
                        match_voto_fim = re.search(r"(\d+)$", nome_sujo)
                        if match_voto_fim:
                            voto_final = int(match_voto_fim.group(1))
                            nome_final = nome_sujo.replace(match_voto_fim.group(1), "").strip()
                        else:
                            # Busca agressiva nas próximas 10 linhas para prefeito
                            # Porque no final da página costuma ter muita sujeira
                            voto_encontrado, pulo = buscar_voto_nas_proximas_linhas(i, max_busca=10)
                            if voto_encontrado is not None:
                                voto_final = voto_encontrado
                                nome_final = nome_sujo

                        nome_final = nome_final.replace("Votação", "").strip()

                        if voto_final is not None:
                            print(f"Prefeito Capturado: {num} - {nome_final} - {voto_final}")
                            dados["votos"].append({
                                "cargo": "prefeito",
                                "numero": num,
                                "nome": nome_final,
                                "qtd": voto_final
                            })
                except: pass

        i += 1

    return dados
# --- 4. API ---
app = FastAPI()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@app.get("/")
def home():
    return RedirectResponse(url="/docs")

@app.post("/upload-boletim/")
async def upload_boletim(file: UploadFile = File(...), db: Session = Depends(get_db)):
    conteudo = await file.read()
    
    try:
        # Chama a nova função com OCR
        dados = extrair_dados_com_ocr(conteudo)
    except Exception as e:
        print(f"Erro no OCR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Salva no Banco
    novo_boletim = Boletim(
        arquivo_nome=file.filename,
        secao=dados["metadata"]["secao"],
        zona="N/A", municipio="N/A"
    )
    db.add(novo_boletim)
    db.commit()
    db.refresh(novo_boletim)

    count_votos = 0
    for v in dados["votos"]:
        novo_voto = Voto(
            boletim_id=novo_boletim.id,
            cargo=v['cargo'],   
            numero=v['numero'],
            nome=v['nome'],
            qtd_votos=v['qtd']
        )
        db.add(novo_voto)
        count_votos += 1
    
    db.commit()

    return {"status": "ok", "votos_lidos": count_votos, "secao": dados["metadata"]["secao"]}

@app.get("/resultados")
def ver_resultados(db: Session = Depends(get_db)):
    return db.query(Boletim).all()