import requests
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# --- CONFIGURAÇÕES LAGOA DO CARRO ---
MUNICIPIO_TSE = "23027"  # Código de Lagoa do Carro
UF = "pe"
ELEICAO_ID = "619"       # ID da Eleição 2024 (Oficial)

# Conexão com o Banco LOCAL
SQLALCHEMY_DATABASE_URL = "postgresql://admin:senha_segura_123@localhost:5432/eleicoes_2024"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def buscar_oficial_tse(cargo_codigo):
    """
    Baixa o JSON oficial do TSE (API de Resultados).
    Cargo: 11 (Prefeito), 13 (Vereador)
    """
    url = f"https://resultados.tse.jus.br/oficial/ele2024/{ELEICAO_ID}/dados/{UF}/{UF}{MUNICIPIO_TSE}-c00{cargo_codigo}-e000{ELEICAO_ID}-v.json"
    
    try:
        print(f"🌍 Conectando ao TSE para baixar dados de {UF.upper()} (Cargo {cargo_codigo})...")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        candidatos = {}
        lista = data.get('abr', [{}])[0].get('cand', [])
        
        for c in lista:
          
            nome = c['nm']
            numero = int(c['n'])
            votos = int(c['vap'])
            situacao = c['st']
            
            candidatos[numero] = {'nome': nome, 'votos': votos, 'situacao': situacao}
            
        return candidatos
    except Exception as e:
        print(f"❌ Erro na conexão com TSE: {e}")
        return {}

def buscar_meu_banco(cargo_nome):
    """
    Soma tudo que você processou dos PDFs no PostgreSQL
    """
    session = SessionLocal()
    query = text("""
        SELECT numero, nome, SUM(qtd_votos) as total 
        FROM votos 
        WHERE cargo = :cargo 
        GROUP BY numero, nome
    """)
    result = session.execute(query, {"cargo": cargo_nome}).fetchall()
    session.close()
    
    dados_locais = {}
    for row in result:
        # row[0]=numero, row[1]=nome, row[2]=total
        dados_locais[row[0]] = {'nome': row[1], 'votos': int(row[2])}
    
    return dados_locais

def auditar(cargo_tse_cod, cargo_local_nome):
    oficial = buscar_oficial_tse(cargo_tse_cod)
    meu_banco = buscar_meu_banco(cargo_local_nome)
    
    print(f"\n{'='*30} AUDITORIA: {cargo_local_nome.upper()} {'='*30}")
    print(f"{'NUM':<6} | {'NOME (TSE)':<25} | {'TSE':<8} | {'SEU BD':<8} | {'DIFERENÇA':<10} | {'STATUS'}")
    print("-" * 95)
    
    # iterar pelos dados DO TSE (que é a verdade absoluta)
    todos_numeros = set(oficial.keys()) | set(meu_banco.keys())
    
    erros = 0
    acertos = 0

    for num in sorted(todos_numeros):
        # Dados do TSE
        dados_tse = oficial.get(num, {'nome': 'NÃO EXISTE NO TSE', 'votos': 0})
        votos_tse = dados_tse['votos']
        nome_tse = dados_tse['nome']
        
        # Dados do seu Banco
        dados_local = meu_banco.get(num, {'nome': '---', 'votos': 0})
        votos_local = dados_local['votos']
        
        diferenca = votos_local - votos_tse
        
        # Análise do Status
        if diferenca == 0:
            status = "✅ PERFEITO"
            cor = "\033[92m" # Verde
            acertos += 1
        elif diferenca < 0:
            status = f"❌ FALTA {abs(diferenca)}"
            cor = "\033[93m" # Amarelo/Laranja
            erros += 1
        else:
            status = f"🚨 SOBRA {diferenca}"
            cor = "\033[91m" # Vermelho (Perigo: leu voto a mais!)
            erros += 1
        
        reset = "\033[0m"
        
        # Imprime a linha
        print(f"{cor}{num:<6} | {nome_tse[:25]:<25} | {votos_tse:<8} | {votos_local:<8} | {diferenca:<10} | {status}{reset}")

    print("-" * 95)
    print(f"RESUMO: {acertos} candidatos batem perfeitamente. {erros} com divergência.")

if __name__ == "__main__":
    auditar(11, "prefeito")
    auditar(13, "vereador")