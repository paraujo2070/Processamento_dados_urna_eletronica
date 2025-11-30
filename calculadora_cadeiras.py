import pandas as pd
import math

# --- CONFIGURAÇÕES ---
NUMERO_CADEIRAS = 11  

dados_partidos = {
    "10 - Republicanos": 1901,
    "45 - PSDB": 1723,
    "11 - Progressistas": 1683,
    "20 - Podemos": 1572,
    "22 - PL": 1544,
    "55 - PSD": 1475,
    "18 - Rede": 1464,
    "12 - PDT": 1170,
    "40 - PSB": 1024,
    "13 - PT": 57
}

def calcular_eleitos():
    print(f"{'='*40}")
    print(f"🗳️  SIMULADOR DE ELEITOS (Q.E.)")
    print(f"{'='*40}")

    # 1. Totais
    total_votos_validos = sum(dados_partidos.values())
    quociente_eleitoral = round(total_votos_validos / NUMERO_CADEIRAS)
    
    print(f"Total de Votos Válidos Nominais: {total_votos_validos}")
    print(f"Cadeiras em disputa:    {NUMERO_CADEIRAS}")
    print(f"QUOCIENTE ELEITORAL:    {quociente_eleitoral}")
    print(f"(O partido precisa de {quociente_eleitoral} votos para fazer o 1º vereador direto)")
    print("-" * 40)

    # DataFrame para gerenciar o cálculo
    df = pd.DataFrame(list(dados_partidos.items()), columns=['Partido', 'Votos'])
    df['Vagas'] = 0
    df['Media'] = 0.0

    # 2. Primeira Fase: Quociente Partidário (Vagas Diretas)
    # Fórmula: Votos do Partido / Quociente Eleitoral (descarta a fração)
    for index, row in df.iterrows():
        vagas_diretas = int(row['Votos'] / quociente_eleitoral)
        df.at[index, 'Vagas'] = vagas_diretas
        
        # Regra de Cláusula de Barreira (80% do QE) - Simplificada aqui
        # Assumindo que todos cumpriram, mas matematicamente é isso.

    vagas_preenchidas = df['Vagas'].sum()
    print(f"\n🔹 Vagas Diretas (QP): {vagas_preenchidas}")
    print(df[['Partido', 'Votos', 'Vagas']].sort_values(by='Votos', ascending=False).to_string(index=False))

    # 3. Segunda Fase: Distribuição das Sobras (Médias)
    # Enquanto houver vagas sobrando...
    while vagas_preenchidas < NUMERO_CADEIRAS:
        print(f"\n🔸 Distribuindo sobra {vagas_preenchidas + 1}/{NUMERO_CADEIRAS}...")
        
        # Calcula a média atual de cada partido
        # Fórmula: Votos / (Vagas Já Obtidas + 1)
        maior_media = -1
        partido_ganhador_index = -1

        for index, row in df.iterrows():
            media = row['Votos'] / (row['Vagas'] + 1)
            df.at[index, 'Media'] = media
            
            if media > maior_media:
                maior_media = media
                partido_ganhador_index = index

        # Entrega a vaga para quem tem a maior média
        partido_nome = df.at[partido_ganhador_index, 'Partido']
        df.at[partido_ganhador_index, 'Vagas'] += 1
        vagas_preenchidas += 1
        
        print(f"   -> Vaga foi para: {partido_nome} (Média: {int(maior_media)})")

    # --- RESULTADO FINAL ---
    print(f"\n{'='*40}")
    print(f"🏛️  COMPOSIÇÃO FINAL DA CÂMARA")
    print(f"{'='*40}")
    
    df_final = df.sort_values(by='Vagas', ascending=False)
    print(df_final[['Partido', 'Votos', 'Vagas']].to_string(index=False))

if __name__ == "__main__":
    calcular_eleitos()