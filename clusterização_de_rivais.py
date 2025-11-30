import pandas as pd
import sys
from sqlalchemy import create_engine
from sklearn.preprocessing import MaxAbsScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
import seaborn as sns

db_url = "postgresql://admin:senha_segura_123@localhost:5432/eleicoes_2024"
engine = create_engine(db_url)

print("📥 Carregando dados...")

# 1. Removemos filtros rígidos para garantir que venha dados
# 2. Usamos ILIKE para ignorar maiúsculas/minúsculas
query = """
SELECT 
    v.nome || ' (' || v.numero || ')' as candidato,
    b.secao,
    v.qtd_votos,
    v.cargo
FROM votos v
JOIN boletins b ON v.boletim_id = b.id
WHERE v.cargo ILIKE '%%VEREADOR%%' 
"""

try:
    df = pd.read_sql(query, engine)
except Exception as e:
    print(f"❌ Erro ao conectar ou executar query: {e}")
    sys.exit()

if df.empty:
    print("\n❌ ERRO CRÍTICO: A consulta retornou 0 linhas!")

    print("\n🔎 Verificando quais cargos existem no banco...")
    try:
        cargos = pd.read_sql("SELECT DISTINCT cargo FROM votos", engine)
        print(cargos)
    except:
        print("Não foi possível listar os cargos.")
    sys.exit()

print(f"✅ Dados carregados! {len(df)} registros encontrados.")

# --- 2. PRÉ-PROCESSAMENTO (PIVOT TABLE) ---
# Transforma: Linhas = Candidatos, Colunas = Seções
# fill_value=0 é crucial: quem não teve voto na seção ganha zero (não NaN)
df_pivot = df.pivot_table(index='candidato', columns='secao', values='qtd_votos', fill_value=0)

print(f"📊 Matriz de análise criada: {df_pivot.shape[0]} candidatos x {df_pivot.shape[1]} seções.")

if df_pivot.shape[0] < 2:
    print("❌ Poucos candidatos para agrupar. É necessário pelo menos 2.")
    sys.exit()

# Normalização
scaler = MaxAbsScaler()
X_scaled = scaler.fit_transform(df_pivot)

# --- 3. MACHINE LEARNING (K-MEANS) ---
# Define número de grupos (Clusters)
# Se tiver menos de 5 candidatos, ajusta o K para não dar erro
k = min(5, len(df_pivot) - 1)
print(f"🧠 Treinando IA para encontrar {k} perfis de candidatos...")

kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
clusters = kmeans.fit_predict(X_scaled)

# Adiciona o cluster ao dataframe original
df_pivot['Cluster'] = clusters

# --- 4. ANÁLISE DOS RESULTADOS ---
print(f"\nResultados da Clusterização:\n")

for i in range(k):
    candidatos_grupo = df_pivot[df_pivot['Cluster'] == i].index.tolist()
    qtd = len(candidatos_grupo)
    
    # Pega as seções mais fortes desse grupo
    centroide = kmeans.cluster_centers_[i]
    # Pega os índices das 3 maiores seções
    top_indices = centroide.argsort()[-3:][::-1] 
    top_secoes = df_pivot.columns[top_indices].tolist()
    
    print(f"🔹 GRUPO {i} ({qtd} cand.): Fortes nas seções {top_secoes}")
    # Mostra apenas os 5 primeiros nomes para não poluir
    print(f"   Exemplos: {candidatos_grupo[:5]}")
    print("-" * 40)

# --- 5. VISUALIZAÇÃO (PCA 2D) ---
try:
    print("\n🎨 Gerando gráfico...")
    pca = PCA(n_components=2)
    components = pca.fit_transform(X_scaled)

    plt.figure(figsize=(12, 8))
    sns.scatterplot(x=components[:,0], y=components[:,1], hue=clusters, palette='viridis', s=100)
    
    plt.title('Mapa de Concorrência Eleitoral (Quem pesca no mesmo aquário?)')
    plt.xlabel('Variação Geográfica 1')
    plt.ylabel('Variação Geográfica 2')
    plt.legend(title='Grupo')
    plt.grid(True, alpha=0.3)

    nome_img = "mapa_concorrencia.png"
    plt.savefig(nome_img)
    print(f"✅ Gráfico salvo como '{nome_img}'")
except Exception as e:
    print(f"⚠️ Não foi possível gerar o gráfico (falta biblioteca gráfica?): {e}")

print("\n🚀 Análise concluída!")