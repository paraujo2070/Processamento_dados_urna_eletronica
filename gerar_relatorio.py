import pandas as pd
from sqlalchemy import create_engine
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from datetime import datetime


NOME_ARQUIVO = "Relatorio_Completo_Com_Zeros.pdf"

db_url = "postgresql://admin:senha_segura_123@localhost:5432/eleicoes_2024"
engine = create_engine(db_url)

def carregar_dados():
    print("📥 Carregando dados do banco...")
    
    # 1. Busca TODAS as seções existentes (Lista Mestra)
    query_secoes = "SELECT DISTINCT secao FROM boletins ORDER BY secao"
    todas_secoes = pd.read_sql(query_secoes, engine)['secao'].tolist()
    print(f"   -> Total de Seções na Cidade: {len(todas_secoes)}")

    # 2. Busca os votos registrados
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
    
    return todas_secoes, df_votos

def criar_pdf():
    lista_secoes_mestra, df = carregar_dados()
    
    if df.empty:
        print("❌ Nenhum dado encontrado.")
        return

    doc = SimpleDocTemplate(
        NOME_ARQUIVO, 
        pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm, 
        topMargin=15*mm, bottomMargin=15*mm
    )
    
    elementos = []
    styles = getSampleStyleSheet()
    
    # Estilos
    estilo_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'], alignment=1, fontSize=16)
    estilo_cand = ParagraphStyle('Cand', parent=styles['Heading2'], fontSize=12, textColor=colors.darkblue, spaceAfter=4)
    
    # Cabeçalho do Documento
    data_hoje = datetime.now().strftime("%d/%m/%Y às %H:%M")
    elementos.append(Paragraph("Relatório Completo de Votação (Incluindo Zeros)", estilo_titulo))
    elementos.append(Paragraph(f"Total de Seções Processadas: {len(lista_secoes_mestra)}", styles['Normal']))
    elementos.append(Spacer(1, 8*mm))

    # Agrupar por candidato
    grupos = df.groupby(['cargo', 'numero', 'nome'])

    print(f"📄 Gerando tabelas para {len(grupos)} candidatos...")

    for (cargo, numero, nome), grupo_df in grupos:
        
        votos_series = grupo_df.set_index('secao')['qtd_votos']
        
        votos_completos = votos_series.reindex(lista_secoes_mestra, fill_value=0)
        
        # 3. Calcula total real
        total_votos = int(votos_completos.sum())

        # Cabeçalho do Candidato
        texto_header = f"<b>{nome}</b> ({numero}) - {cargo.upper()} | Total: <b>{total_votos}</b>"
        elementos.append(Paragraph(texto_header, estilo_cand))

        # Preparar dados para a tabela
        # Layout: Seção | Votos || Seção | Votos
        
        dados_flat = []
        for secao, voto in votos_completos.items():
            dados_flat.append([secao, int(voto)])
        
        # Adiciona linha de TOTAL no final dos dados
        dados_flat.append(['TOTAL', total_votos])

        # Cria a tabela
        tabela = Table(dados_flat, colWidths=[30*mm, 20*mm], hAlign='LEFT')
        
        # Estilo Condicional: Se voto > 0 pinta de verde claro, se 0 deixa branco
        estilo_base = [
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            # Destacar linha de Total
            ('BACKGROUND', (0, -1), (-1, -1), colors.black),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]
        
        # Loop para pintar linhas onde teve voto > 0 para facilitar visualização
        for i, (secao, voto) in enumerate(dados_flat):
            # A última linha é o TOTAL, ignoramos no loop de cor de votos
            if secao != 'TOTAL' and voto > 0:
                estilo_base.append(('BACKGROUND', (1, i), (1, i), colors.lightgreen))
                estilo_base.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

        tabela.setStyle(TableStyle(estilo_base))

        # Mantém junto na página se possível
        elementos.append(KeepTogether([
            tabela,
            Spacer(1, 8*mm)
        ]))

    try:
        doc.build(elementos)
        print(f"✅ Arquivo '{NOME_ARQUIVO}' gerado com sucesso!")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    criar_pdf()