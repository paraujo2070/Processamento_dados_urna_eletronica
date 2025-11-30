import os
import shutil
import requests
import time
import sys

# --- CONFIGURAÇÕES ---
PASTA_ORIGEM = "urnas_para_ler"       # Coloque seus PDFs aqui
PASTA_DESTINO = "urnas_concluidas"    # Eles virão para cá se der certo
PASTA_ERRO = "urnas_com_erro"         # Vão para cá se der erro
URL_API = "http://127.0.0.1:8000/upload-boletim/"

def processar_arquivos():
    # 1. Cria as pastas se não existirem
    for pasta in [PASTA_ORIGEM, PASTA_DESTINO, PASTA_ERRO]:
        os.makedirs(pasta, exist_ok=True)

    # 2. Lista os PDFs
    arquivos = [f for f in os.listdir(PASTA_ORIGEM) if f.lower().endswith('.pdf')]

    if not arquivos:
        print(f"⚠️  Nenhum arquivo PDF encontrado na pasta '{PASTA_ORIGEM}'.")
        print(f"👉 Cole os arquivos PDF lá e rode o script novamente.")
        return

    print(f"🚀 Iniciando processamento de {len(arquivos)} arquivos...")
    print("=" * 60)

    sucessos = 0
    falhas = 0

    # 3. Loop de Envio
    for i, arquivo in enumerate(arquivos):
        caminho_atual = os.path.join(PASTA_ORIGEM, arquivo)
        print(f"[{i+1}/{len(arquivos)}] Processando: {arquivo} ... ", end="", flush=True)

        try:
            # Abre e envia o arquivo
            with open(caminho_atual, 'rb') as f:
                response = requests.post(URL_API, files={"file": f})

            # Verifica resposta
            if response.status_code == 200:
                print("✅ SUCESSO")
                # Move para pasta de concluídos
                shutil.move(caminho_atual, os.path.join(PASTA_DESTINO, arquivo))
                sucessos += 1
            else:
                print(f"❌ ERRO ({response.status_code})")
                print(f"   Detalhe: {response.text}")
                # Move para pasta de erro para analisar depois
                shutil.move(caminho_atual, os.path.join(PASTA_ERRO, arquivo))
                falhas += 1

        except requests.exceptions.ConnectionError:
            print("\n⛔ ERRO FATAL: Não foi possível conectar ao servidor.")
            print("   Certifique-se que o 'main.py' está rodando (uvicorn).")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ ERRO NO SCRIPT: {e}")
            falhas += 1

    # 4. Resumo Final
    print("=" * 60)
    print("🏁 Processamento Finalizado!")
    print(f"📦 Total processado: {len(arquivos)}")
    print(f"✅ Sucessos: {sucessos}")
    print(f"❌ Falhas:   {falhas}")
    print(f"📁 Arquivos movidos para: '{PASTA_DESTINO}'")

if __name__ == "__main__":
    processar_arquivos()