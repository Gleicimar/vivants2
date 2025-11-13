import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime
import os

# Configuração da pasta de relatórios
RELATORIOS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'relatorios')

# Criar pasta se não existir
if not os.path.exists(RELATORIOS_DIR):
    os.makedirs(RELATORIOS_DIR)

def gerar_excel_produtos(produtos, salvar_arquivo=False):
    """Gera relatório de produtos em Excel"""
    # Criar DataFrame
    data = []
    for produto in produtos:
        data.append({
            'ID': produto['id'],
            'Nome': produto['nome'],
            'Categoria': produto['categoria_nome'],
            'Preço': f"R$ {produto['preco']:.2f}",
            'Preço Promocional': f"R$ {produto['preco_promocional']:.2f}" if produto['preco_promocional'] else '',
            'Estoque': produto['estoque'],
            'Destaque': 'Sim' if produto['destaque'] else 'Não',
            'Data Cadastro': produto['data_cadastro']
        })

    df = pd.DataFrame(data)

    if salvar_arquivo:
        # Salvar no servidor
        filename = f"relatorio_produtos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(RELATORIOS_DIR, filename)

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Produtos', index=False)

            # Formatar a planilha
            worksheet = writer.sheets['Produtos']
            worksheet.column_dimensions['A'].width = 8
            worksheet.column_dimensions['B'].width = 30
            worksheet.column_dimensions['C'].width = 20
            worksheet.column_dimensions['D'].width = 12
            worksheet.column_dimensions['E'].width = 15
            worksheet.column_dimensions['F'].width = 10
            worksheet.column_dimensions['G'].width = 10
            worksheet.column_dimensions['H'].width = 15

        return filename, filepath
    else:
        # Gerar em memória
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Produtos', index=False)

            worksheet = writer.sheets['Produtos']
            worksheet.column_dimensions['A'].width = 8
            worksheet.column_dimensions['B'].width = 30
            worksheet.column_dimensions['C'].width = 20
            worksheet.column_dimensions['D'].width = 12
            worksheet.column_dimensions['E'].width = 15
            worksheet.column_dimensions['F'].width = 10
            worksheet.column_dimensions['G'].width = 10
            worksheet.column_dimensions['H'].width = 15

        output.seek(0)
        return output

def gerar_excel_pedidos(pedidos, salvar_arquivo=False):
    """Gera relatório de pedidos em Excel"""
    data = []
    for pedido in pedidos:
        data.append({
            'ID': pedido['id'],
            'Cliente': pedido['cliente_nome'],
            'Email': pedido['cliente_email'],
            'Total': f"R$ {pedido['total']:.2f}",
            'Status': pedido['status'].upper(),
            'Data Pedido': pedido['data_pedido'],
            'Endereço': pedido['endereco_entrega']
        })

    df = pd.DataFrame(data)

    if salvar_arquivo:
        filename = f"relatorio_pedidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(RELATORIOS_DIR, filename)

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Pedidos', index=False)

            worksheet = writer.sheets['Pedidos']
            worksheet.column_dimensions['A'].width = 8
            worksheet.column_dimensions['B'].width = 25
            worksheet.column_dimensions['C'].width = 25
            worksheet.column_dimensions['D'].width = 12
            worksheet.column_dimensions['E'].width = 15
            worksheet.column_dimensions['F'].width = 15
            worksheet.column_dimensions['G'].width = 30

        return filename, filepath
    else:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Pedidos', index=False)

            worksheet = writer.sheets['Pedidos']
            worksheet.column_dimensions['A'].width = 8
            worksheet.column_dimensions['B'].width = 25
            worksheet.column_dimensions['C'].width = 25
            worksheet.column_dimensions['D'].width = 12
            worksheet.column_dimensions['E'].width = 15
            worksheet.column_dimensions['F'].width = 15
            worksheet.column_dimensions['G'].width = 30

        output.seek(0)
        return output

def gerar_excel_clientes(clientes, salvar_arquivo=False):
    """Gera relatório de clientes em Excel"""
    data = []
    for cliente in clientes:
        data.append({
            'ID': cliente['id'],
            'Nome': cliente['nome'],
            'Email': cliente['email'],
            'Telefone': cliente['telefone'] or 'Não informado',
            'Data Cadastro': cliente['data_cadastro']
        })

    df = pd.DataFrame(data)

    if salvar_arquivo:
        filename = f"relatorio_clientes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(RELATORIOS_DIR, filename)

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Clientes', index=False)

            worksheet = writer.sheets['Clientes']
            worksheet.column_dimensions['A'].width = 8
            worksheet.column_dimensions['B'].width = 25
            worksheet.column_dimensions['C'].width = 25
            worksheet.column_dimensions['D'].width = 20
            worksheet.column_dimensions['E'].width = 15

        return filename, filepath
    else:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Clientes', index=False)

            worksheet = writer.sheets['Clientes']
            worksheet.column_dimensions['A'].width = 8
            worksheet.column_dimensions['B'].width = 25
            worksheet.column_dimensions['C'].width = 25
            worksheet.column_dimensions['D'].width = 20
            worksheet.column_dimensions['E'].width = 15

        output.seek(0)
        return output

def gerar_pdf_produtos(produtos, salvar_arquivo=False):
    """Gera relatório de produtos em PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)

    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1
    )

    # Conteúdo
    elements = []

    # Título
    title = Paragraph("RELATÓRIO DE PRODUTOS - VIVANTS", title_style)
    elements.append(title)

    # Data de emissão
    data_emissao = Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal'])
    elements.append(data_emissao)
    elements.append(Spacer(1, 20))

    # Tabela de dados
    data = [['ID', 'Nome', 'Categoria', 'Preço', 'Estoque', 'Destaque']]

    for produto in produtos:
        data.append([
            str(produto['id']),
            produto['nome'],
            produto['categoria_nome'],
            f"R$ {produto['preco']:.2f}",
            str(produto['estoque']),
            'Sim' if produto['destaque'] else 'Não'
        ])

    table = Table(data, colWidths=[0.5*inch, 2.5*inch, 1.5*inch, 1*inch, 0.8*inch, 0.8*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)

    # Rodapé
    elements.append(Spacer(1, 20))
    total_produtos = Paragraph(f"Total de produtos: {len(produtos)}", styles['Normal'])
    elements.append(total_produtos)

    doc.build(elements)

    if salvar_arquivo:
        filename = f"relatorio_produtos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(RELATORIOS_DIR, filename)

        with open(filepath, 'wb') as f:
            f.write(buffer.getvalue())

        return filename, filepath
    else:
        buffer.seek(0)
        return buffer

def gerar_pdf_pedidos(pedidos, salvar_arquivo=False):
    """Gera relatório de pedidos em PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1
    )

    elements = []

    # Título
    title = Paragraph("RELATÓRIO DE PEDIDOS - VIVANTS", title_style)
    elements.append(title)

    # Data de emissão
    data_emissao = Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal'])
    elements.append(data_emissao)
    elements.append(Spacer(1, 20))

    # Tabela
    data = [['ID', 'Cliente', 'Total', 'Status', 'Data']]

    for pedido in pedidos:
        data.append([
            f"#{pedido['id']}",
            pedido['cliente_nome'],
            f"R$ {pedido['total']:.2f}",
            pedido['status'].upper(),
            pedido['data_pedido']
        ])

    table = Table(data, colWidths=[0.6*inch, 2.5*inch, 1.2*inch, 1.2*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)

    # Estatísticas
    elements.append(Spacer(1, 20))
    total_pedidos = Paragraph(f"Total de pedidos: {len(pedidos)}", styles['Normal'])
    faturamento_total = sum(pedido['total'] for pedido in pedidos)
    faturamento = Paragraph(f"Faturamento total: R$ {faturamento_total:.2f}", styles['Normal'])

    elements.append(total_pedidos)
    elements.append(faturamento)

    doc.build(elements)

    if salvar_arquivo:
        filename = f"relatorio_pedidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(RELATORIOS_DIR, filename)

        with open(filepath, 'wb') as f:
            f.write(buffer.getvalue())

        return filename, filepath
    else:
        buffer.seek(0)
        return buffer

def gerar_pdf_clientes(clientes, salvar_arquivo=False):
    """Gera relatório de clientes em PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1
    )

    elements = []

    # Título
    title = Paragraph("RELATÓRIO DE CLIENTES - VIVANTS", title_style)
    elements.append(title)

    # Data de emissão
    data_emissao = Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal'])
    elements.append(data_emissao)
    elements.append(Spacer(1, 20))

    # Tabela
    data = [['ID', 'Nome', 'Email', 'Telefone', 'Cadastro']]

    for cliente in clientes:
        data.append([
            str(cliente['id']),
            cliente['nome'],
            cliente['email'],
            cliente['telefone'] or 'Não informado',
            cliente['data_cadastro']
        ])

    table = Table(data, colWidths=[0.5*inch, 2*inch, 2*inch, 1.5*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)

    # Estatísticas
    elements.append(Spacer(1, 20))
    total_clientes = Paragraph(f"Total de clientes: {len(clientes)}", styles['Normal'])
    elements.append(total_clientes)

    doc.build(elements)

    if salvar_arquivo:
        filename = f"relatorio_clientes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(RELATORIOS_DIR, filename)

        with open(filepath, 'wb') as f:
            f.write(buffer.getvalue())

        return filename, filepath
    else:
        buffer.seek(0)
        return buffer

def listar_relatorios():
    """Lista todos os relatórios salvos"""
    relatorios = []

    if os.path.exists(RELATORIOS_DIR):
        for filename in os.listdir(RELATORIOS_DIR):
            if filename.endswith(('.xlsx', '.pdf')):
                filepath = os.path.join(RELATORIOS_DIR, filename)
                stat = os.stat(filepath)
                relatorios.append({
                    'nome': filename,
                    'caminho': filepath,
                    'tamanho': stat.st_size,
                    'data_criacao': datetime.fromtimestamp(stat.st_ctime),
                    'tipo': 'Excel' if filename.endswith('.xlsx') else 'PDF'
                })

    # Ordenar por data (mais recente primeiro)
    relatorios.sort(key=lambda x: x['data_criacao'], reverse=True)
    return relatorios
