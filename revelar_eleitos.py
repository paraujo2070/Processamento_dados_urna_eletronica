import pandas as pd
from sqlalchemy import create_engine, text

# --- CONFIGURAÇÃO ---
NUMERO_CADEIRAS = 11

# Conexão BD
db_url = "postgresql://admin:senha_segura_123@localhost:5432/eleicoes_2024"
engine = create_engine(db_url)

def carregar_votos_partido():
    """Calcula votos totais por partido (Nominais + Legenda)"""
    query = text("""
    SELECT 
        LEFT(CAST(numero AS TEXT), 2) as partido_prefixo, 
        SUM(qtd_votos) as votos_totais
    FROM votos 
    WHERE cargo = 'vereador'
    GROUP BY LEFT(CAST(numero AS TEXT), 2)
    ORDER BY votos_totais DESC
    """)
    return pd.read_sql(query, engine)

def obter_candidatos_do_partido(prefixo):
    """Busca os candidatos mais votados daquele partido (SOMANDO AS URNAS)"""
    # CORREÇÃO AQUI: Adicionado SUM() e GROUP BY
    query = text("""
    SELECT numero, nome, SUM(qtd_votos) as qtd_votos
    FROM votos
    WHERE cargo = 'vereador' 
      AND CAST(numero AS TEXT) LIKE :padrao
      AND numero > 99 
    GROUP BY numero, nome
    ORDER BY qtd_votos DESC
    """)
    
    return pd.read_sql(query, engine, params={"padrao": f"{prefixo}%"})

def calcular_distribuicao(df_partidos):
    """Refaz o cálculo de cadeiras (QP + Sobras)"""
    total_validos = df_partidos['votos_totais'].sum()
    qe = round(total_validos / NUMERO_CADEIRAS)
    
    df = df_partidos.copy()
    
    # Cálculo das Vagas Diretas (Quociente Partidário)
    df['vagas'] = (df['votos_totais'] / qe).astype(int)
    vagas_preenchidas = df['vagas'].sum()
    
    # Distribuição de Sobras (Médias)
    while vagas_preenchidas < NUMERO_CADEIRAS:
        medias = df['votos_totais'] / (df['vagas'] + 1)
        idx_vencedor = medias.idxmax()
        df.at[idx_vencedor, 'vagas'] += 1
        vagas_preenchidas += 1
        
    return df, qe

def gerar_lista_final():
    print(f"{'='*60}")
    print(f"🏆 LISTA OFICIAL DE VEREADORES ELEITOS - LAGOA DO CARRO")
    print(f"{'='*60}")

    df_partidos = carregar_votos_partido()
    df_distribuicao, qe = calcular_distribuicao(df_partidos)
    
    print(f"📊 Quociente Eleitoral: {qe} votos\n")

    total_eleitos = 0
    
    # Para cada partido, pegamos os TOP X candidatos
    for _, row in df_distribuicao.iterrows():
        partido = row['partido_prefixo']
        vagas = row['vagas']
        
        if vagas == 0:
            continue
            
        print(f"🚩 Partido {partido} conquistou {vagas} cadeira(s):")
        
        # Busca os candidatos no banco (AGORA SOMADOS CORRETAMENTE)
        candidatos = obter_candidatos_do_partido(partido)
        
        # Pega apenas os eleitos (limite de vagas)
        eleitos = candidatos.head(vagas)
        
        for i, cand in eleitos.iterrows():
            total_eleitos += 1
            nome = cand['nome']
            num = cand['numero']
            votos = cand['qtd_votos']
            print(f"   ✅ {i+1}º ELEITO: {nome:<30} ({num}) - {votos} votos")
            
        # Mostra o primeiro suplente (o "quase" entrou)
        if len(candidatos) > vagas:
            suplente = candidatos.iloc[vagas]
            print(f"      ⚠️ 1º Suplente: {suplente['nome']} ({suplente['qtd_votos']} votos)")
            
        print("-" * 50)

    print(f"\nTotal de Eleitos Listados: {total_eleitos}")

if __name__ == "__main__":
    gerar_lista_final()