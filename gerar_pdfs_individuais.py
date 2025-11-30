import pandas as pd
import os
import re
from sqlalchemy import create_engine
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from datetime import datetime

PASTA_SAIDA = "relatorios_individuais_auditados"

db_url = "postgresql://admin:senha_segura_123@localhost:5432/eleicoes_2024"
engine = create_engine(db_url)

def limpar_nome_arquivo(nome):
    """Remove caracteres inválidos para nome de arquivo"""
    nome_limpo = re.sub(r'[^\w\s-]', '', nome)
    return nome_limpo.strip().replace(' ', '_').upper()

def carregar_dados():
    print("📥 Carregando dados do banco...")
    
    # 1. Busca TODAS as seções
    query_secoes = "SELECT DISTINCT secao FROM boletins ORDER BY secao"
    todas_secoes = pd.read_sql(query_secoes, engine)['secao'].tolist()

    # 2. Busca os votos
    query_votos = """
    SELECT 
        v.cargo,
        v.numero,
        v.nome,
        b.secao,
        v.qtd_votos
    FROM votos v
    JOIN boletins b ON v.boletim_id = b.id
    """
    df_votos = pd.read_sql(query_votos, engine)

    # 3. Busca o Total Oficial do TSE
    try:
        query_oficial = "SELECT numero, votos as votos_tse FROM resultado_oficial"
        df_oficial = pd.read_sql(query_oficial, engine)
    except:
        print("⚠️ Tabela oficial não encontrada. Comparativo desativado.")
        df_oficial = pd.DataFrame(columns=['numero', 'votos_tse'])
    
    return todas_secoes, df_votos, df_oficial

def gerar_arquivos():
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    
    lista_secoes_mestra, df, df_oficial = carregar_dados()
    
    if df.empty:
        print("❌ Nenhum dado encontrado.")
        return

    # Agrupa por Cargo e Número
    grupos = df.groupby(['cargo', 'numero'])
    total_candidatos = len(grupos)
    
    print(f"🚀 Iniciando geração de {total_candidatos} arquivos PDF...")

    contador = 0
    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'], alignment=1, fontSize=16)
    estilo_subtitulo = ParagraphStyle('Subtitulo', parent=styles['Normal'], alignment=1, fontSize=10)
    estilo_cand = ParagraphStyle('Cand', parent=styles['Heading2'], fontSize=12, textColor=colors.darkblue)

    for (cargo, numero), grupo_df in grupos:
        contador += 1
        
        # Pega o nome mais comum
        nome_principal = grupo_df['nome'].mode()[0]
        
        # Cálculos de Votos
        votos_series = grupo_df.groupby('secao')['qtd_votos'].sum()
        votos_completos = votos_series.reindex(lista_secoes_mestra, fill_value=0)
        
        total_apurado = int(votos_completos.sum())
        
        # Busca Oficial TSE
        try:
            total_tse = int(df_oficial.loc[df_oficial['numero'] == numero, 'votos_tse'].values[0])
        except IndexError:
            total_tse = total_apurado 
        
        diferenca = total_tse - total_apurado

        # --- GERAÇÃO PDF ---
        nome_arquivo = limpar_nome_arquivo(nome_principal)
        caminho_arquivo = os.path.join(PASTA_SAIDA, f"{nome_arquivo}_{numero}.pdf")
        
        doc = SimpleDocTemplate(
            caminho_arquivo, 
            pagesize=A4,
            rightMargin=15*mm, leftMargin=15*mm, 
            topMargin=15*mm, bottomMargin=15*mm
        )
        
        elementos = []
        
        data_hoje = datetime.now().strftime("%d/%m/%Y às %H:%M")
        elementos.append(Paragraph(f"Relatório Individual de Auditoria", estilo_titulo))
        elementos.append(Paragraph(f"{data_hoje}", estilo_subtitulo))
        elementos.append(Spacer(1, 10*mm))

        texto_header = f"<b>{nome_principal}</b> ({numero})<br/>Cargo: {cargo.upper()} | Apurado: <b>{total_apurado}</b>"
        elementos.append(Paragraph(texto_header, estilo_cand))
        elementos.append(Spacer(1, 5*mm))

        # Tabela
        dados_flat = []
        dados_flat.append(['Seção', 'Votos', 'Status'])

        for secao, voto in votos_completos.items():
            voto_int = int(voto)
            status = "VOTADO" if voto_int > 0 else "NÃO VOTADO"
            dados_flat.append([secao, voto_int, status])
        
        # Linha Total Apurado
        dados_flat.append(['TOTAL (Nominal)', total_apurado, ''])

        tem_diferenca = diferenca > 0
        if tem_diferenca:
            texto_aviso = f"⚠ +{diferenca} Votos de Legenda (Total TSE: {total_tse})"
            dados_flat.append([texto_aviso, '', '']) # Colunas vazias pois faremos merge (span) 

        # --- ESTILOS ---
        tabela = Table(dados_flat, colWidths=[30*mm, 30*mm, 50*mm], hAlign='LEFT')
        
        estilo_base = [
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.navy),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]
        
        # Estilo da Linha TOTAL (Preto)
        idx_total = len(dados_flat) - 2 if tem_diferenca else len(dados_flat) - 1
        estilo_base.extend([
            ('BACKGROUND', (0, idx_total), (-1, idx_total), colors.black),
            ('TEXTCOLOR', (0, idx_total), (-1, idx_total), colors.white),
            ('FONTNAME', (0, idx_total), (-1, idx_total), 'Helvetica-Bold'),
        ])

        # Estilo da Linha AVISO (Vermelho Claro)
        if tem_diferenca:
            idx_aviso = len(dados_flat) - 1
            estilo_base.extend([
                ('SPAN', (0, idx_aviso), (-1, idx_aviso)), # Mescla as 3 colunas
                ('BACKGROUND', (0, idx_aviso), (-1, idx_aviso), colors.mistyrose),
                ('TEXTCOLOR', (0, idx_aviso), (-1, idx_aviso), colors.red),
                ('FONTNAME', (0, idx_aviso), (-1, idx_aviso), 'Helvetica-Bold'),
                ('ALIGN', (0, idx_aviso), (-1, idx_aviso), 'CENTER'), # Centraliza o texto do aviso
            ])

        for i, linha in enumerate(dados_flat):
            if i == 0 or "TOTAL" in str(linha[0]) or "⚠" in str(linha[0]): continue
            if linha[1] > 0:
                estilo_base.append(('BACKGROUND', (0, i), (-1, i), colors.lightgreen))
                estilo_base.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))

        tabela.setStyle(TableStyle(estilo_base))
        elementos.append(tabela)

        try:
            doc.build(elementos)
            print(f"[{contador}/{total_candidatos}] OK: {caminho_arquivo}")
        except Exception as e:
            print(f"❌ Erro ao gerar {nome_principal}: {e}")

    print("-" * 50)
    print("✅ Processo finalizado!")

if __name__ == "__main__":
    gerar_arquivos()