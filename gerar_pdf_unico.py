import pandas as pd
import os
import re
from sqlalchemy import create_engine
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from datetime import datetime

# --- CONFIGURAÇÕES ---
NOME_ARQUIVO_FINAL = "relatorio_geral_com_auditoria.pdf"

db_url = "postgresql://admin:senha_segura_123@localhost:5432/eleicoes_2024"
engine = create_engine(db_url)

def carregar_dados():
    print("📥 Carregando dados do banco...")
    
    query_secoes = "SELECT DISTINCT secao FROM boletins ORDER BY secao"
    todas_secoes = pd.read_sql(query_secoes, engine)['secao'].tolist()

    # 2. Busca os votos detalhados
    query_votos = """
    SELECT 
        v.cargo,
        v.numero,
        v.nome,
        b.secao,
        v.qtd_votos
    FROM votos v
    JOIN boletins b ON v.boletim_id = b.id
    ORDER BY v.cargo, v.nome
    """
    df_votos = pd.read_sql(query_votos, engine)

   
    query_oficial = "SELECT numero, votos as votos_tse FROM resultado_oficial"
    try:
        df_oficial = pd.read_sql(query_oficial, engine)
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível carregar tabela oficial ({e}). O comparativo não será feito.")
        df_oficial = pd.DataFrame(columns=['numero', 'votos_tse'])
    
    return todas_secoes, df_votos, df_oficial

def gerar_relatorio_unico():
    lista_secoes_mestra, df, df_oficial = carregar_dados()
    
    if df.empty:
        print("❌ Nenhum dado encontrado.")
        return

    # Agrupar por candidato
    grupos = df.groupby(['cargo', 'numero', 'nome'])
    total_candidatos = len(grupos)
    
    print(f"🚀 Iniciando geração do relatório auditorado para {total_candidatos} candidatos...")

    # --- CRIAÇÃO DO DOCUMENTO ---
    doc = SimpleDocTemplate(
        NOME_ARQUIVO_FINAL, 
        pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm, 
        topMargin=15*mm, bottomMargin=15*mm
    )
    
    elementos = []
    styles = getSampleStyleSheet()
    
    # Estilos Personalizados
    estilo_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'], alignment=1, fontSize=16)
    estilo_subtitulo = ParagraphStyle('Subtitulo', parent=styles['Normal'], alignment=1, fontSize=10)
    estilo_cand = ParagraphStyle('Cand', parent=styles['Heading2'], fontSize=12, textColor=colors.darkblue)

    # Cabeçalho
    data_hoje = datetime.now().strftime("%d/%m/%Y às %H:%M")
    elementos.append(Paragraph(f"Relatório de Conferência de Votos", estilo_titulo))
    elementos.append(Paragraph(f"Comparativo: Apurado (DB) vs Oficial (TSE) - {data_hoje}", estilo_subtitulo))
    elementos.append(Spacer(1, 10*mm))
    
    contador = 0

    for (cargo, numero, nome), grupo_df in grupos:
        contador += 1
        
        # --- CÁLCULOS ---
        votos_series = grupo_df.set_index('secao')['qtd_votos']
        votos_completos = votos_series.reindex(lista_secoes_mestra, fill_value=0)
        
        total_apurado = int(votos_completos.sum())
        
        # Busca total oficial no dataframe auxiliar
        try:
            total_tse = df_oficial.loc[df_oficial['numero'] == numero, 'votos_tse'].values[0]
            total_tse = int(total_tse)
        except IndexError:
            total_tse = total_apurado # Se não achar no oficial, assume que está igual para não dar erro
        
        diferenca = total_tse - total_apurado

        # --- CONTEÚDO VISUAL ---
        texto_header = f"<b>{nome}</b> ({numero}) - {cargo.upper()}"
        
        # Montagem da Tabela
        dados_flat = []
        dados_flat.append(['Seção', 'Votos', 'Status']) # Cabeçalho

        for secao, voto in votos_completos.items():
            voto_int = int(voto)
            status = "VOTADO" if voto_int > 0 else "NÃO VOTADO"
            dados_flat.append([secao, voto_int, status])
        
        # Linha de Total Apurado
        dados_flat.append(['TOTAL (Nominal)', total_apurado, ''])

        # --- LÓGICA DO AVISO DE LEGENDA ---
        tem_diferenca = diferenca > 0
        if tem_diferenca:
            texto_aviso = f"⚠ +{diferenca} Votos de Legenda (Total TSE: {total_tse})"
            dados_flat.append([texto_aviso, '', '']) # Colunas vazias pois faremos merge (span)

        # --- ESTILIZAÇÃO DA TABELA ---
        tabela = Table(dados_flat, colWidths=[30*mm, 30*mm, 50*mm], hAlign='LEFT')
        
        estilo_base = [
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.navy),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]

        # Estilo da linha de Total Apurado (Penúltima ou Antepenúltima dependendo se tem erro)
        indice_linha_total = len(dados_flat) - 1 if not tem_diferenca else len(dados_flat) - 2
        
        estilo_base.extend([
            ('BACKGROUND', (0, indice_linha_total), (-1, indice_linha_total), colors.black),
            ('TEXTCOLOR', (0, indice_linha_total), (-1, indice_linha_total), colors.white),
            ('FONTNAME', (0, indice_linha_total), (-1, indice_linha_total), 'Helvetica-Bold'),
        ])

        # Se tiver diferença, estiliza a linha extra
        if tem_diferenca:
            indice_aviso = len(dados_flat) - 1
            estilo_base.extend([
                ('SPAN', (0, indice_aviso), (-1, indice_aviso)), # Mescla as 3 colunas
                ('BACKGROUND', (0, indice_aviso), (-1, indice_aviso), colors.mistyrose), # Fundo vermelho claro
                ('TEXTCOLOR', (0, indice_aviso), (-1, indice_aviso), colors.red), # Texto vermelho
                ('FONTNAME', (0, indice_aviso), (-1, indice_aviso), 'Helvetica-BoldOblique'),
                ('ALIGN', (0, indice_aviso), (-1, indice_aviso), 'CENTER'),
            ])

        # Loop para colorir linhas com votos > 0
        for i, linha in enumerate(dados_flat):
            if i == 0: continue 
            if "TOTAL" in str(linha[0]) or "⚠" in str(linha[0]): continue # Pula totais e avisos
            
            voto = linha[1]
            if isinstance(voto, int) and voto > 0:
                estilo_base.append(('BACKGROUND', (0, i), (-1, i), colors.lightgreen))

        tabela.setStyle(TableStyle(estilo_base))

        elementos.append(KeepTogether([
            Paragraph(texto_header, estilo_cand),
            Spacer(1, 2*mm),
            tabela
        ]))
        
        elementos.append(PageBreak())
        
        if contador % 10 == 0:
            print(f"... Processados {contador}/{total_candidatos}")

    print(f"💾 Salvando arquivo: {NOME_ARQUIVO_FINAL}...")
    try:
        doc.build(elementos)
        print("✅ Relatório gerado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao gerar PDF: {e}")

if __name__ == "__main__":
    gerar_relatorio_unico()