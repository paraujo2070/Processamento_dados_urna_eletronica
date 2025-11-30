import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from sqlalchemy import create_engine, text, Integer
import re
import os

# --- CONFIGURAÇÕES ---
URL_TSE = "https://resultados.tse.jus.br/oficial/app/index.html#/divulga/votacao-nominal;e=619;cargo=13;uf=pe;mu=23027;zn=TODAS"
db_url = "postgresql://admin:senha_segura_123@localhost:5432/eleicoes_2024"
engine = create_engine(db_url)

def raspar_dados_tse():
    print("🤖 Iniciando Robô de Sincronização (TSE -> Banco de Dados)...")
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,3000") # Janela alta para carregar mais itens
    
    options.binary_location = "/usr/bin/chromium-browser"
    caminho_driver = "/usr/bin/chromedriver"
    
    service = Service(caminho_driver) if os.path.exists(caminho_driver) else Service()

    try:
        driver = webdriver.Chrome(service=service, options=options)
        print(f"🌍 Acessando o TSE...")
        driver.get(URL_TSE)
        
        print("⏳ Aguardando carregamento (10s)...")
        time.sleep(10)

        # --- AUTO SCROLL ---
        print("📜 Rolando página para garantir carga completa...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        for i in range(20):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Captura texto
        page_text = driver.find_element(By.TAG_NAME, "body").text
        print("✅ Texto capturado! Processando...")
        
        dados = []
        linhas = page_text.split('\n')
        
        buffer_numero = None
        esperando_voto = False
        
        # --- PARSING ---
        for linha in linhas:
            linha = linha.strip()
            if not linha: continue
            
            # Identifica Candidato (5 dígitos)
            match_cand = re.search(r"^(\d{5})\s", linha)
            if match_cand:
                buffer_numero = int(match_cand.group(1))
                esperando_voto = False 
                continue
            
            # Identifica palavra chave e tenta pegar voto na mesma linha
            if "Votação" in linha and buffer_numero:
                linha_limpa = linha.replace("Votação", "").replace(".", "").strip()
                if linha_limpa.isdigit():
                    votos = int(linha_limpa)
                    dados.append({'numero': buffer_numero, 'votos': votos})
                    buffer_numero = None 
                else:
                    esperando_voto = True
                continue

            # Pega voto na linha seguinte
            if esperando_voto and buffer_numero:
                linha_limpa = linha.replace(".", "").strip()
                if linha_limpa.isdigit():
                    votos = int(linha_limpa)
                    dados.append({'numero': buffer_numero, 'votos': votos})
                    buffer_numero = None
                    esperando_voto = False

        df = pd.DataFrame(dados)
        
        if not df.empty:
            df = df.drop_duplicates(subset=['numero'])
            print(f"📦 Extraídos {len(df)} candidatos do TSE.")
            return df
        else:
            print("⚠️ Falha na extração dos dados.")
            return None

    except Exception as e:
        print(f"❌ Erro: {e}")
        return None
    finally:
        if 'driver' in locals():
            driver.quit()

def salvar_no_banco(df):
    if df is None or df.empty: return

    print("💾 Salvando na tabela 'resultado_oficial'...")
    
    # Salva no PostgreSQL
    # if_exists='replace': Apaga a tabela antiga e cria uma nova a cada execução
    df.to_sql('resultado_oficial', engine, if_exists='replace', index=False, dtype={
        'numero': Integer(),
        'votos': Integer()
    })
    
    print("✅ Tabela 'resultado_oficial' atualizada com sucesso!")

if __name__ == "__main__":
    df_tse = raspar_dados_tse()
    salvar_no_banco(df_tse)