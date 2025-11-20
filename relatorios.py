import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Frame
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import math

# -----------------------
# Configuração / Helpers
# -----------------------
def agora_brasil():
    """Retorna datetime com timezone America/Sao_Paulo"""
    return datetime.now(ZoneInfo("America/Sao_Paulo"))

# Pasta de relatórios
RELATORIOS_DIR = os.path.join(os.path.dirname(__file__), "static", "relatorios")
os.makedirs(RELATORIOS_DIR, exist_ok=True)

# Estilos globais
_styles = getSampleStyleSheet()
TITLE_STYLE = ParagraphStyle(
    "ReportTitle",
    parent=_styles["Heading1"],
    fontSize=16,
    leading=20,
    alignment=1,  # center
    spaceAfter=12
)
META_STYLE = ParagraphStyle(
    "Meta",
    parent=_styles["Normal"],
    fontSize=9,
    leading=12,
    alignment=1  # center
)
NORMAL_STYLE = ParagraphStyle(
    "NormalLeft",
    parent=_styles["Normal"],
    fontSize=9,
    leading=12,
    alignment=0  # left
)
FOOTER_STYLE = ParagraphStyle(
    "Footer",
    parent=_styles["Normal"],
    fontSize=8,
    leading=10,
    alignment=1
)

# -----------------------
# Util: calcular larguras
# -----------------------
def calcular_col_widths(data_rows, page_width=A4[0], left_margin=36, right_margin=36, min_col=30, max_col=300):
    """
    Estima larguras de colunas com base no conteúdo textual.
    Retorna lista de larguras em pontos que somam no máximo page_width - margins.
    """
    usable_width = page_width - left_margin - right_margin
    # transpor
    cols = list(zip(*data_rows))
    # medimos comprimento aproximado (número de caracteres)
    lengths = [max(len(str(cell)) for cell in col) for col in cols]
    total = sum(lengths) or 1
    # converte para width proporcional
    widths = []
    for l in lengths:
        w = max(min_col, min(max_col, math.ceil((l / total) * usable_width)))
        widths.append(w)
    # ajustar soma para não ultrapassar usable_width
    current = sum(widths)
    if current != usable_width:
        diff = usable_width - current
        # distribuir diff proporcionalmente (simples)
        for i in range(len(widths)):
            add = math.floor(diff * (widths[i] / current)) if current else 0
            widths[i] += add
        # corrigir qualquer sobra
        while sum(widths) < usable_width:
            for i in range(len(widths)):
                widths[i] += 1
                if sum(widths) >= usable_width:
                    break
        while sum(widths) > usable_width:
            for i in range(len(widths)):
                if widths[i] > min_col:
                    widths[i] -= 1
                if sum(widths) <= usable_width:
                    break
    return widths

# -----------------------
# Util: header & footer
# -----------------------
def _cabecalho(canvas, doc, titulo):
    canvas.saveState()
    w, h = A4
    left = doc.leftMargin
    right = doc.rightMargin
    # Linha superior sutil
    canvas.setStrokeColor(colors.HexColor("#e0e0e0"))
    canvas.setLineWidth(0.5)
    canvas.line(left, h - 36, w - right, h - 36)
    # Título (já centrado via Paragraph no fluxo, aqui podemos colocar somente uma linha discreta)
    canvas.restoreState()

def _rodape(canvas, doc):
    canvas.saveState()
    w, h = A4
    page_num = canvas.getPageNumber()
    footer_text = f"Vivants — Relatório gerado em {agora_brasil().strftime('%d/%m/%Y %H:%M')} — Página {page_num}"
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawCentredString(w / 2.0, 12 * mm, footer_text)
    canvas.restoreState()

# -----------------------
# Util: criar tabela estilizada (zebra, cabeçalho escuro)
# -----------------------
def criar_tabela_estilizada(data_rows, col_widths=None, repeat_header=True):
    """
    Gera Table com estilo corporativo:
    - Cabeçalho escuro com texto branco
    - Linhas zebradas (bege / branco)
    - Grid fino
    """
    if col_widths is None:
        col_widths = calcular_col_widths(data_rows)

    table = Table(data_rows, colWidths=col_widths, repeatRows=1 if repeat_header else 0)

    # Base style
    style = TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBEFORE", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("LINEAFTER", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
    ])

    # Cabeçalho escuro
    style.add("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6c757d"))
    style.add("TEXTCOLOR", (0, 0), (-1, 0), colors.white)

    # Zebra para linhas alternadas
    for idx in range(1, len(data_rows)):
        bg = colors.whitesmoke if idx % 2 == 0 else colors.beige
        style.add("BACKGROUND", (0, idx), (-1, idx), bg)

    table.setStyle(style)
    return table

# -----------------------
# EXCEL: produtos, pedidos, clientes (mantive implementação simples)
# -----------------------
def gerar_excel_produtos(produtos, salvar_arquivo=False):
    data = []
    for produto in produtos:
        data.append({
            "ID": produto["id"],
            "Nome": produto["nome"],
            "Categoria": produto["categoria_nome"],
            "Preço": f"R$ {produto['preco']:.2f}",
            "Preço Promocional": f"R$ {produto['preco_promocional']:.2f}" if produto.get("preco_promocional") else "",
            "Estoque": produto.get("estoque", ""),
            "Destaque": "Sim" if produto.get("destaque") else "Não",
            "Data Cadastro": produto.get("data_cadastro", "")
        })
    df = pd.DataFrame(data)
    filename = f"relatorio_produtos_{agora_brasil().strftime('%Y%m%d_%H%M%S')}.xlsx"

    if salvar_arquivo:
        filepath = os.path.join(RELATORIOS_DIR, filename)
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Produtos", index=False)
            ws = writer.sheets["Produtos"]
            for col, width in zip("ABCDEFGH", [8, 30, 20, 12, 15, 10, 10, 15]):
                ws.column_dimensions[col].width = width
        return filename, filepath

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Produtos", index=False)
    output.seek(0)
    return output

def gerar_excel_pedidos(pedidos, salvar_arquivo=False):
    data = []
    for pedido in pedidos:
        data.append({
            "ID": pedido["id"],
            "Cliente": pedido["cliente_nome"],
            "Email": pedido.get("cliente_email", ""),
            "Total": f"R$ {pedido['total']:.2f}",
            "Status": pedido.get("status", "").upper(),
            "Data Pedido": pedido.get("data_pedido", ""),
            "Endereço": pedido.get("endereco_entrega", "")
        })
    df = pd.DataFrame(data)
    filename = f"relatorio_pedidos_{agora_brasil().strftime('%Y%m%d_%H%M%S')}.xlsx"

    if salvar_arquivo:
        filepath = os.path.join(RELATORIOS_DIR, filename)
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Pedidos", index=False)
            ws = writer.sheets["Pedidos"]
            for col, width in zip("ABCDEFG", [8, 25, 25, 12, 15, 15, 30]):
                ws.column_dimensions[col].width = width
        return filename, filepath

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Pedidos", index=False)
    output.seek(0)
    return output

def gerar_excel_clientes(clientes, salvar_arquivo=False):
    data = []
    for cliente in clientes:
        data.append({
            "ID": cliente["id"],
            "Nome": cliente["nome"],
            "Email": cliente.get("email", ""),
            "Telefone": cliente.get("telefone") or "Não informado",
            "Data Cadastro": cliente.get("data_cadastro", "")
        })
    df = pd.DataFrame(data)
    filename = f"relatorio_clientes_{agora_brasil().strftime('%Y%m%d_%H%M%S')}.xlsx"

    if salvar_arquivo:
        filepath = os.path.join(RELATORIOS_DIR, filename)
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Clientes", index=False)
            ws = writer.sheets["Clientes"]
            for col, width in zip("ABCDE", [8, 25, 25, 20, 15]):
                ws.column_dimensions[col].width = width
        return filename, filepath

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Clientes", index=False)
    output.seek(0)
    return output

# -----------------------
# PDF: Produtos, Pedidos, Clientes (com espaçamento maior entre título e "Emitido em")
# -----------------------
def gerar_pdf_produtos(produtos, salvar_arquivo=False):
    buffer = BytesIO()
    filename = f"relatorio_produtos_{agora_brasil().strftime('%Y%m%d_%H%M%S')}.pdf"
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=48, bottomMargin=48)

    # Header title + emission (com espaçamento aumentado)
    titulo = Paragraph("RELATÓRIO DE PRODUTOS - VIVANTS", TITLE_STYLE)
    # Espaçamento maior solicitado entre o título e a linha "Emitido em"
    emitido = Paragraph(f"Emitido em: {agora_brasil().strftime('%d/%m/%Y %H:%M')}", META_STYLE)

    data = [["ID", "Nome", "Categoria", "Preço", "Estoque", "Destaque"]]
    for p in produtos:
        data.append([
            str(p.get("id", "")),
            p.get("nome", ""),
            p.get("categoria_nome", ""),
            f"R$ {p.get('preco', 0):.2f}",
            str(p.get("estoque", "")),
            "Sim" if p.get("destaque") else "Não"
        ])

    col_widths = calcular_col_widths(data, page_width=A4[0], left_margin=doc.leftMargin, right_margin=doc.rightMargin)
    tabela = criar_tabela_estilizada(data, col_widths)

    elements = [
        titulo,
        Spacer(1, 12),            # mantém espaçamento padrão abaixo do título
        emitido,
        Spacer(1, 18),            # >>> AUMENTEI esse Spacer para ampliar o espaço pedido
        tabela,
        Spacer(1, 12),
        Paragraph(f"Total de produtos: {len(produtos)}", NORMAL_STYLE)
    ]

    # build com header/footer
    doc.build(elements, onFirstPage=lambda c, d: (_cabecalho(c, d, titulo), _rodape(c, d)),
              onLaterPages=lambda c, d: (_cabecalho(c, d, titulo), _rodape(c, d)))

    if salvar_arquivo:
        filepath = os.path.join(RELATORIOS_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(buffer.getvalue())
        return filename, filepath

    buffer.seek(0)
    return buffer

def gerar_pdf_pedidos(pedidos, salvar_arquivo=False):
    buffer = BytesIO()
    filename = f"relatorio_pedidos_{agora_brasil().strftime('%Y%m%d_%H%M%S')}.pdf"
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=48, bottomMargin=48)

    titulo = Paragraph("RELATÓRIO DE PEDIDOS - VIVANTS", TITLE_STYLE)
    emitido = Paragraph(f"Emitido em: {agora_brasil().strftime('%d/%m/%Y %H:%M')}", META_STYLE)

    data = [["ID", "Cliente", "Total", "Status", "Data"]]
    for ped in pedidos:
        data.append([
            f"#{ped.get('id', '')}",
            ped.get("cliente_nome", ""),
            f"R$ {ped.get('total', 0):.2f}",
            ped.get("status", "").upper(),
            ped.get("data_pedido", "")
        ])

    col_widths = calcular_col_widths(data, page_width=A4[0], left_margin=doc.leftMargin, right_margin=doc.rightMargin)
    tabela = criar_tabela_estilizada(data, col_widths)

    faturamento = sum(p.get("total", 0) for p in pedidos)

    elements = [
        titulo,
        Spacer(1, 12),
        emitido,
        Spacer(1, 18),            # espaço aumentado entre título e emitido em
        tabela,
        Spacer(1, 12),
        Paragraph(f"Total de pedidos: {len(pedidos)}", NORMAL_STYLE),
        Paragraph(f"Faturamento total: R$ {faturamento:.2f}", NORMAL_STYLE)
    ]

    doc.build(elements, onFirstPage=lambda c, d: (_cabecalho(c, d, titulo), _rodape(c, d)),
              onLaterPages=lambda c, d: (_cabecalho(c, d, titulo), _rodape(c, d)))

    if salvar_arquivo:
        filepath = os.path.join(RELATORIOS_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(buffer.getvalue())
        return filename, filepath

    buffer.seek(0)
    return buffer

def gerar_pdf_clientes(clientes, salvar_arquivo=False):
    buffer = BytesIO()
    filename = f"relatorio_clientes_{agora_brasil().strftime('%Y%m%d_%H%M%S')}.pdf"
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=48, bottomMargin=48)

    titulo = Paragraph("RELATÓRIO DE CLIENTES - VIVANTS", TITLE_STYLE)
    emitido = Paragraph(f"Emitido em: {agora_brasil().strftime('%d/%m/%Y %H:%M')}", META_STYLE)

    data = [["ID", "Nome", "Email", "Telefone", "Cadastro"]]
    for c in clientes:
        data.append([
            str(c.get("id", "")),
            c.get("nome", ""),
            c.get("email", ""),
            c.get("telefone") or "Não informado",
            c.get("data_cadastro", "")
        ])

    col_widths = calcular_col_widths(data, page_width=A4[0], left_margin=doc.leftMargin, right_margin=doc.rightMargin)
    tabela = criar_tabela_estilizada(data, col_widths)

    elements = [
        titulo,
        Spacer(1, 12),
        emitido,
        Spacer(1, 18),            # espaço aumentado entre título e emitido em
        tabela,
        Spacer(1, 12),
        Paragraph(f"Total de clientes: {len(clientes)}", NORMAL_STYLE)
    ]

    doc.build(elements, onFirstPage=lambda c, d: (_cabecalho(c, d, titulo), _rodape(c, d)),
              onLaterPages=lambda c, d: (_cabecalho(c, d, titulo), _rodape(c, d)))

    if salvar_arquivo:
        filepath = os.path.join(RELATORIOS_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(buffer.getvalue())
        return filename, filepath

    buffer.seek(0)
    return buffer

# -----------------------
# Listar relatórios salvos
# -----------------------
def listar_relatorios():
    relatorios = []
    if os.path.exists(RELATORIOS_DIR):
        for filename in os.listdir(RELATORIOS_DIR):
            if filename.endswith((".xlsx", ".pdf")):
                filepath = os.path.join(RELATORIOS_DIR, filename)
                stat = os.stat(filepath)
                relatorios.append({
                    "nome": filename,
                    "caminho": filepath,
                    "tamanho": stat.st_size,
                    "data_criacao": datetime.fromtimestamp(stat.st_ctime, ZoneInfo("America/Sao_Paulo")),
                    "tipo": "Excel" if filename.endswith(".xlsx") else "PDF"
                })
    relatorios.sort(key=lambda x: x["data_criacao"], reverse=True)
    return relatorios

# -----------------------
# Exemplo rápido (apenas para dev/teste)
# -----------------------
if __name__ == "__main__":
    # Quando rodar diretamente, gera PDFs de exemplo na pasta de relatórios
    exemplo_produtos = [
        {"id": 1, "nome": "Shampoo A", "categoria_nome": "Cabelos", "preco": 29.9, "estoque": 10, "destaque": True},
        {"id": 2, "nome": "Condicionador B com nome longo", "categoria_nome": "Cabelos", "preco": 24.5, "estoque": 5, "destaque": False},
    ]
    gerar_pdf_produtos(exemplo_produtos, salvar_arquivo=True)
    print("PDF de produtos gerado em:", RELATORIOS_DIR)
