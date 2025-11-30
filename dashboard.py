import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditoria por Seção", layout="wide", page_icon="🗳️")

@st.cache_resource
def get_engine():
    db_url = "postgresql://admin:senha_segura_123@localhost:5432/eleicoes_2024"
    return create_engine(db_url)

engine = get_engine()

# --- FUNÇÕES DE BUSCA ---

def listar_secoes():
    """Retorna lista de todas as seções disponíveis no banco"""
    query = "SELECT DISTINCT secao FROM boletins ORDER BY secao"
    df = pd.read_sql(query, engine)
    return df['secao'].tolist()

def buscar_dados_secao(secao):
    """Busca votos de Prefeito e Vereador para uma seção específica"""
    # Usamos parameters no read_sql para segurança e filtro
    query = text("""
        SELECT v.cargo, v.numero, v.nome, v.qtd_votos 
        FROM votos v
        JOIN boletins b ON v.boletim_id = b.id
        WHERE b.secao = :secao
        ORDER BY v.qtd_votos DESC
    """)
    
    # Passando o parâmetro de forma segura
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"secao": secao})
        
    return df

# --- INTERFACE (SIDEBAR) ---
st.sidebar.header("🔍 Filtro")
lista_secoes = listar_secoes()

if not lista_secoes:
    st.error("Nenhuma seção encontrada no Banco de Dados.")
    st.stop()

# Caixa de seleção da Seção
secao_selecionada = st.sidebar.selectbox(
    "Selecione a Seção Eleitoral:", 
    lista_secoes
)

# --- CARREGAMENTO DOS DADOS ---
if secao_selecionada:
    df_geral = buscar_dados_secao(secao_selecionada)
    
    # Separa os dataframes
    df_prefeito = df_geral[df_geral['cargo'] == 'prefeito'].reset_index(drop=True)
    df_vereador = df_geral[df_geral['cargo'] == 'vereador'].reset_index(drop=True)
    
    # Calcula total de votos na urna (soma de nominais capturados)
    total_votos_urna = df_geral['qtd_votos'].sum()

    # --- CABEÇALHO ---
    st.title(f"🗳️ Resultado da Seção {secao_selecionada}")
    st.caption(f"Total de votos nominais processados nesta urna: {total_votos_urna}")
    st.divider()

    # --- BLOCO 1: PREFEITO ---
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("🎩 Prefeito")
        if not df_prefeito.empty:
            # Mostra o vencedor em destaque
            vencedor = df_prefeito.iloc[0]
            st.metric(label="Mais votado na seção", value=vencedor['nome'], delta=f"{vencedor['qtd_votos']} votos")
            
            # Gráfico de Rosca (Donut Chart)
            st.write("Distribuição:")
            st.bar_chart(df_prefeito.set_index('nome')['qtd_votos'], color="#29b5e8")
        else:
            st.warning("Nenhum voto para prefeito encontrado nesta seção.")

    with col2:
        st.subheader("Detalhes (Prefeito)")
        st.dataframe(
            df_prefeito[['numero', 'nome', 'qtd_votos']],
            column_config={
                "numero": st.column_config.NumberColumn("Número", format="%d"),
                "qtd_votos": st.column_config.ProgressColumn(
                    "Votos", 
                    format="%d", 
                    min_value=0, 
                    max_value=int(df_prefeito['qtd_votos'].max()) if not df_prefeito.empty else 100
                ),
            },
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # --- BLOCO 2: VEREADOR ---
    st.subheader("👥 Vereadores")
    
    if not df_vereador.empty:
        # Filtros visuais
        tab1, tab2 = st.tabs(["📊 Gráfico", "📋 Tabela Detalhada"])
        
        with tab1:
            # Gráfico dos top 15 na seção
            top_ver = df_vereador.head(15)
            st.caption("Top 15 mais votados nesta urna")
            st.bar_chart(
                top_ver,
                x="nome",
                y="qtd_votos",
                color="#ff4b4b",
                horizontal=True
            )
            
        with tab2:
            st.dataframe(
                df_vereador[['numero', 'nome', 'qtd_votos']],
                column_config={
                    "numero": st.column_config.NumberColumn("Número", format="%d"),
                    "nome": "Candidato",
                    "qtd_votos": st.column_config.NumberColumn("Votos"),
                },
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("Nenhum voto para vereador registrado nesta seção.")

else:
    st.info("Selecione uma seção na barra lateral para ver os dados.")