from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db
from decorators import login_required, admin_required
from datetime import datetime
import sqlite3
import os
from werkzeug.utils import secure_filename
from relatorios import (
    gerar_excel_produtos, gerar_excel_pedidos, gerar_excel_clientes,
    gerar_pdf_produtos, gerar_pdf_pedidos, gerar_pdf_clientes,
    listar_relatorios, RELATORIOS_DIR
)

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui_mude_em_producao'

# Configurações de upload
UPLOAD_FOLDER = 'static/uploads/produtos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Criar diretório de uploads se não existir
os.makedirs(os.path.join(app.root_path, UPLOAD_FOLDER), exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_product_image(file):
    """Salva a imagem do produto e retorna a URL ou mensagem de erro"""
    if file and file.filename != '':
        if not allowed_file(file.filename):
            return None, "Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP"

        # Verificar tamanho do arquivo
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)

        if file_length > MAX_FILE_SIZE:
            return None, "Arquivo muito grande. Tamanho máximo: 5MB"

        # Criar nome seguro para o arquivo
        filename = secure_filename(file.filename)
        # Adicionar timestamp para evitar conflitos
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
        filename = timestamp + filename

        # Caminho completo do arquivo
        filepath = os.path.join(app.root_path, UPLOAD_FOLDER, filename)

        try:
            file.save(filepath)
            # Retornar URL relativa (sem 'app.root_path')
            return f'/{UPLOAD_FOLDER}/{filename}', None
        except Exception as e:
            return None, f"Erro ao salvar arquivo: {str(e)}"

    return None, "Nenhum arquivo selecionado"

# Funções auxiliares para converter Row para dicionário e processar datas
def parse_datetime(date_string):
    """Tenta converter string para datetime object"""
    if date_string is None:
        return None
    if isinstance(date_string, datetime):
        return date_string
    try:
        # Tenta vários formatos comuns do SQLite
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y'
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        return date_string  # Retorna como string se não conseguir converter
    except:
        return date_string

def row_to_dict(row):
    """Converte uma linha SQLite Row para dicionário"""
    if row is None:
        return None
    result = {}
    for key in row.keys():
        value = row[key]
        # Converte campos de data se possível
        if 'data' in key.lower() or 'cadastro' in key.lower() or 'pedido' in key.lower() or 'avaliacao' in key.lower():
            result[key] = parse_datetime(value)
        else:
            result[key] = value
    return result

def rows_to_dict_list(rows):
    """Converte uma lista de linhas SQLite Row para lista de dicionários"""
    return [row_to_dict(row) for row in rows]

def format_date(value, format='%d/%m/%Y %H:%M'):
    """Função para formatar datas nos templates"""
    if value is None:
        return "N/A"
    if isinstance(value, str):
        parsed = parse_datetime(value)
        if isinstance(parsed, datetime):
            return parsed.strftime(format)
        return value
    elif isinstance(value, datetime):
        return value.strftime(format)
    return str(value)

# Adicionar a função de formatação ao Jinja2
app.jinja_env.filters['format_date'] = format_date

# ==================== ROTAS PÚBLICAS ====================

@app.route('/')
def index():
    db = get_db()
    try:
        produtos_data = db.execute('''
            SELECT * FROM produtos
            WHERE ativo = 1 AND destaque = 1
            LIMIT 6
        ''').fetchall()
        produtos = rows_to_dict_list(produtos_data)
        return render_template('home.html', produtos=produtos)
    except sqlite3.Error as e:
        flash('Erro ao carregar produtos', 'danger')
        return render_template('home.html', produtos=[])
    finally:
        db.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '')

        if not email or not senha:
            flash('Por favor, preencha todos os campos', 'danger')
            return render_template('auth/login.html')

        db = get_db()
        try:
            usuario = db.execute('SELECT * FROM usuarios WHERE email = ?', (email,)).fetchone()

            if usuario and check_password_hash(usuario['senha'], senha):
                session['user_id'] = usuario['id']
                session['user_name'] = usuario['nome']
                session['user_type'] = usuario['tipo']
                flash('Login realizado com sucesso!', 'success')

                if usuario['tipo'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('index'))
            else:
                flash('Email ou senha inválidos', 'danger')
        except sqlite3.Error:
            flash('Erro no servidor. Tente novamente.', 'danger')
        finally:
            db.close()

    return render_template('auth/login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        telefone = request.form.get('telefone', '').strip()

        # Validações
        if not nome or not email or not senha:
            flash('Por favor, preencha todos os campos obrigatórios', 'danger')
            return render_template('auth/register.html')

        if len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres', 'danger')
            return render_template('auth/register.html')

        db = get_db()
        try:
            # Verificar se email já existe
            usuario_existente = db.execute('SELECT id FROM usuarios WHERE email = ?', (email,)).fetchone()
            if usuario_existente:
                flash('Email já cadastrado', 'danger')
                return render_template('auth/register.html')

            db.execute('''
                INSERT INTO usuarios (nome, email, senha, telefone, tipo, data_cadastro)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            ''', (nome, email, generate_password_hash(senha), telefone, 'cliente'))
            db.commit()
            flash('Cadastro realizado com sucesso! Faça login para continuar.', 'success')
            return redirect(url_for('login'))
        except sqlite3.Error as e:
            flash('Erro ao realizar cadastro. Tente novamente.', 'danger')
        finally:
            db.close()

    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu com sucesso', 'info')
    return redirect(url_for('index'))

@app.route('/produtos')
def produtos_lista():
    categoria_id = request.args.get('categoria')
    busca = request.args.get('busca', '').strip()

    db = get_db()
    try:
        query = '''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.ativo = 1
        '''
        params = []

        if categoria_id and categoria_id.isdigit():
            query += ' AND p.categoria_id = ?'
            params.append(int(categoria_id))
        elif busca:
            query += ' AND (p.nome LIKE ? OR p.descricao LIKE ?)'
            params.extend([f'%{busca}%', f'%{busca}%'])

        query += ' ORDER BY p.data_cadastro DESC'

        produtos_data = db.execute(query, params).fetchall()
        produtos = rows_to_dict_list(produtos_data)

        categorias_data = db.execute('SELECT * FROM categorias WHERE ativo = 1').fetchall()
        categorias = rows_to_dict_list(categorias_data)

        return render_template('products/produtos_lista.html',
                             produtos=produtos,
                             categorias=categorias,
                             categoria_selecionada=categoria_id,
                             busca=busca)
    except sqlite3.Error:
        flash('Erro ao carregar produtos', 'danger')
        return render_template('products/list.html', produtos=[], categorias=[])
    finally:
        db.close()

@app.route('/produto/<int:id>')
def produto_detalhe(id):
    db = get_db()
    try:
        produto_data = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.id = ? AND p.ativo = 1
        ''', (id,)).fetchone()

        if not produto_data:
            flash('Produto não encontrado', 'warning')
            return redirect(url_for('produtos_lista'))

        produto = row_to_dict(produto_data)

        avaliacoes_data = db.execute('''
            SELECT a.*, u.nome as usuario_nome
            FROM avaliacoes a
            JOIN usuarios u ON a.usuario_id = u.id
            WHERE a.produto_id = ?
            ORDER BY a.data_avaliacao DESC
        ''', (id,)).fetchall()
        avaliacoes = rows_to_dict_list(avaliacoes_data)

        # Produtos relacionados (mesma categoria)
        produtos_relacionados_data = db.execute('''
            SELECT id, nome, preco, preco_promocional, imagem
            FROM produtos
            WHERE categoria_id = ? AND id != ? AND ativo = 1
            LIMIT 4
        ''', (produto['categoria_id'], id)).fetchall()
        produtos_relacionados = rows_to_dict_list(produtos_relacionados_data)

        return render_template('products/detail.html',
                            produto=produto,
                            avaliacoes=avaliacoes,
                            produtos_relacionados=produtos_relacionados)
    except sqlite3.Error:
        flash('Erro ao carregar produto', 'danger')
        return redirect(url_for('produtos_lista'))
    finally:
        db.close()

@app.route('/produto/<int:id>/avaliar', methods=['POST'])
@login_required
def avaliar_produto(id):
    try:
        nota = int(request.form.get('nota', 0))
        comentario = request.form.get('comentario', '').strip()

        # Validar nota
        if nota < 1 or nota > 5:
            flash('A nota deve ser entre 1 e 5', 'warning')
            return redirect(url_for('produto_detalhe', id=id))

        # Validar comprimento do comentário
        if len(comentario) > 500:
            flash('O comentário não pode ter mais de 500 caracteres', 'warning')
            return redirect(url_for('produto_detalhe', id=id))

        db = get_db()

        # Verificar se o produto existe
        produto = db.execute('SELECT id FROM produtos WHERE id = ? AND ativo = 1', (id,)).fetchone()
        if not produto:
            flash('Produto não encontrado', 'warning')
            db.close()
            return redirect(url_for('produtos_lista'))

        # Verificar se usuário já avaliou este produto
        avaliacao_existente = db.execute('''
            SELECT id FROM avaliacoes
            WHERE produto_id = ? AND usuario_id = ?
        ''', (id, session['user_id'])).fetchone()

        if avaliacao_existente:
            flash('Você já avaliou este produto', 'warning')
        else:
            db.execute('''
                INSERT INTO avaliacoes (produto_id, usuario_id, nota, comentario, data_avaliacao)
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (id, session['user_id'], nota, comentario))
            db.commit()
            flash('Avaliação enviada com sucesso!', 'success')

        db.close()
        return redirect(url_for('produto_detalhe', id=id))

    except ValueError:
        flash('Nota inválida', 'danger')
        return redirect(url_for('produto_detalhe', id=id))
    except sqlite3.Error:
        flash('Erro ao enviar avaliação', 'danger')
        return redirect(url_for('produto_detalhe', id=id))

# ==================== ROTAS AUTENTICADAS ====================

@app.route('/carrinho')
@login_required
def carrinho():
    db = get_db()
    try:
        itens_data = db.execute('''
            SELECT c.*, p.nome, p.preco, p.preco_promocional, p.imagem, p.estoque,
                   (COALESCE(p.preco_promocional, p.preco) * c.quantidade) as subtotal
            FROM carrinho c
            JOIN produtos p ON c.produto_id = p.id
            WHERE c.usuario_id = ? AND p.ativo = 1
        ''', (session['user_id'],)).fetchall()
        itens = rows_to_dict_list(itens_data)

        total = sum(item['subtotal'] for item in itens)
        return render_template('cart/cart.html', itens=itens, total=total)
    except sqlite3.Error:
        flash('Erro ao carregar carrinho', 'danger')
        return render_template('cart/cart.html', itens=[], total=0)
    finally:
        db.close()

@app.route('/adicionar-carrinho/<int:produto_id>', methods=['POST'])
@login_required
def adicionar_carrinho(produto_id):
    try:
        quantidade = int(request.form.get('quantidade', 1))

        if quantidade <= 0:
            flash('Quantidade deve ser maior que zero', 'warning')
            return redirect(url_for('produto_detalhe', id=produto_id))

        db = get_db()

        # Verificar se produto existe e tem estoque
        produto = db.execute('''
            SELECT estoque, nome FROM produtos
            WHERE id = ? AND ativo = 1
        ''', (produto_id,)).fetchone()

        if not produto:
            flash('Produto não encontrado', 'warning')
            db.close()
            return redirect(url_for('produtos_lista'))

        if produto['estoque'] < quantidade:
            flash(f'Estoque insuficiente. Disponível: {produto["estoque"]}', 'warning')
            db.close()
            return redirect(url_for('produto_detalhe', id=produto_id))

        # Verificar item existente no carrinho
        item_existente = db.execute('''
            SELECT id, quantidade FROM carrinho
            WHERE usuario_id = ? AND produto_id = ?
        ''', (session['user_id'], produto_id)).fetchone()

        if item_existente:
            nova_quantidade = item_existente['quantidade'] + quantidade
            if nova_quantidade > produto['estoque']:
                flash(f'Quantidade excede estoque disponível. Disponível: {produto["estoque"]}', 'warning')
                db.close()
                return redirect(url_for('produto_detalhe', id=produto_id))

            db.execute('''
                UPDATE carrinho SET quantidade = ?
                WHERE id = ?
            ''', (nova_quantidade, item_existente['id']))
        else:
            db.execute('''
                INSERT INTO carrinho (usuario_id, produto_id, quantidade)
                VALUES (?, ?, ?)
            ''', (session['user_id'], produto_id, quantidade))

        db.commit()
        flash('Produto adicionado ao carrinho!', 'success')

    except ValueError:
        flash('Quantidade inválida', 'danger')
    except sqlite3.Error:
        flash('Erro ao adicionar produto ao carrinho', 'danger')
    finally:
        db.close()

    return redirect(url_for('carrinho'))

@app.route('/atualizar-carrinho/<int:item_id>', methods=['POST'])
@login_required
def atualizar_carrinho(item_id):
    try:
        quantidade = int(request.form.get('quantidade', 1))

        if quantidade <= 0:
            return redirect(url_for('carrinho'))

        db = get_db()

        # Verificar estoque
        item = db.execute('''
            SELECT c.produto_id, p.estoque, p.nome
            FROM carrinho c
            JOIN produtos p ON c.produto_id = p.id
            WHERE c.id = ? AND c.usuario_id = ?
        ''', (item_id, session['user_id'])).fetchone()

        if not item:
            flash('Item não encontrado', 'warning')
            db.close()
            return redirect(url_for('carrinho'))

        if quantidade > item['estoque']:
            flash(f'Estoque insuficiente para {item["nome"]}. Disponível: {item["estoque"]}', 'warning')
            db.close()
            return redirect(url_for('carrinho'))

        db.execute('''
            UPDATE carrinho SET quantidade = ?
            WHERE id = ? AND usuario_id = ?
        ''', (quantidade, item_id, session['user_id']))
        db.commit()
        flash('Carrinho atualizado!', 'success')

    except ValueError:
        flash('Quantidade inválida', 'danger')
    except sqlite3.Error:
        flash('Erro ao atualizar carrinho', 'danger')
    finally:
        db.close()

    return redirect(url_for('carrinho'))

@app.route('/remover-carrinho/<int:item_id>', methods=['POST'])
@login_required
def remover_carrinho(item_id):
    db = get_db()
    try:
        result = db.execute('''
            DELETE FROM carrinho
            WHERE id = ? AND usuario_id = ?
        ''', (item_id, session['user_id']))
        db.commit()

        if result.rowcount > 0:
            flash('Item removido do carrinho', 'info')
        else:
            flash('Item não encontrado', 'warning')
    except sqlite3.Error:
        flash('Erro ao remover item', 'danger')
    finally:
        db.close()

    return redirect(url_for('carrinho'))

@app.route('/finalizar-pedido', methods=['GET', 'POST'])
@login_required
def finalizar_pedido():
    if request.method == 'POST':
        endereco = request.form.get('endereco', '').strip()

        if not endereco:
            flash('Por favor, informe o endereço de entrega', 'danger')
            return redirect(url_for('carrinho'))

        db = get_db()
        try:
            # Buscar itens do carrinho com verificação de estoque
            itens_data = db.execute('''
                SELECT c.*, p.preco, p.preco_promocional, p.estoque, p.nome
                FROM carrinho c
                JOIN produtos p ON c.produto_id = p.id
                WHERE c.usuario_id = ?
            ''', (session['user_id'],)).fetchall()
            itens = rows_to_dict_list(itens_data)

            if not itens:
                flash('Carrinho vazio', 'warning')
                return redirect(url_for('carrinho'))

            # Verificar estoque antes de processar
            for item in itens:
                if item['quantidade'] > item['estoque']:
                    flash(f'Estoque insuficiente para {item["nome"]}. Disponível: {item["estoque"]}', 'warning')
                    return redirect(url_for('carrinho'))

            # Calcular total
            total = sum(
                (item['preco_promocional'] if item['preco_promocional'] else item['preco']) * item['quantidade']
                for item in itens
            )

            # Criar pedido
            cursor = db.execute('''
                INSERT INTO pedidos (usuario_id, total, endereco_entrega, status, data_pedido)
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (session['user_id'], total, endereco, 'pendente'))

            pedido_id = cursor.lastrowid

            # Adicionar itens do pedido e atualizar estoque
            for item in itens:
                preco = item['preco_promocional'] if item['preco_promocional'] else item['preco']

                db.execute('''
                    INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario)
                    VALUES (?, ?, ?, ?)
                ''', (pedido_id, item['produto_id'], item['quantidade'], preco))

                # Atualizar estoque
                db.execute('''
                    UPDATE produtos
                    SET estoque = estoque - ?
                    WHERE id = ?
                ''', (item['quantidade'], item['produto_id']))

            # Limpar carrinho
            db.execute('DELETE FROM carrinho WHERE usuario_id = ?', (session['user_id'],))
            db.commit()

            flash('Pedido realizado com sucesso!', 'success')
            return redirect(url_for('meus_pedidos'))

        except sqlite3.Error:
            db.rollback()
            flash('Erro ao processar pedido. Tente novamente.', 'danger')
            return redirect(url_for('carrinho'))
        finally:
            db.close()

    return render_template('cart/checkout.html')

@app.route('/meus-pedidos')
@login_required
def meus_pedidos():
    db = get_db()
    try:
        pedidos_data = db.execute('''
            SELECT * FROM pedidos
            WHERE usuario_id = ?
            ORDER BY data_pedido DESC
        ''', (session['user_id'],)).fetchall()
        pedidos = rows_to_dict_list(pedidos_data)
        return render_template('orders/list.html', pedidos=pedidos)
    except sqlite3.Error:
        flash('Erro ao carregar pedidos', 'danger')
        return render_template('orders/list.html', pedidos=[])
    finally:
        db.close()

@app.route('/pedido/<int:id>')
@login_required
def pedido_detalhes(id):
    db = get_db()
    try:
        pedido_data = db.execute('''
            SELECT * FROM pedidos
            WHERE id = ? AND usuario_id = ?
        ''', (id, session['user_id'])).fetchone()

        if not pedido_data:
            flash('Pedido não encontrado', 'warning')
            return redirect(url_for('meus_pedidos'))

        pedido = row_to_dict(pedido_data)

        itens_data = db.execute('''
            SELECT ip.*, p.nome, p.imagem
            FROM itens_pedido ip
            JOIN produtos p ON ip.produto_id = p.id
            WHERE ip.pedido_id = ?
        ''', (id,)).fetchall()
        itens = rows_to_dict_list(itens_data)

        return render_template('orders/detail.html', pedido=pedido, itens=itens)
    except sqlite3.Error:
        flash('Erro ao carregar pedido', 'danger')
        return redirect(url_for('meus_pedidos'))
    finally:
        db.close()

# ==================== ROTAS ADMIN ====================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = get_db()
    try:
        # Estatísticas
        stats_data = db.execute('''
            SELECT
                (SELECT COUNT(*) FROM produtos WHERE ativo=1) as total_produtos,
                (SELECT COUNT(*) FROM pedidos) as total_pedidos,
                (SELECT COUNT(*) FROM usuarios WHERE tipo='cliente') as total_clientes,
                (SELECT COALESCE(SUM(total), 0) FROM pedidos WHERE status = "entregue") as faturamento_total
        ''').fetchone()

        stats = row_to_dict(stats_data) if stats_data else {}

        # Pedidos recentes
        pedidos_recentes_data = db.execute('''
            SELECT p.*, u.nome as usuario_nome
            FROM pedidos p
            JOIN usuarios u ON p.usuario_id = u.id
            ORDER BY p.data_pedido DESC
            LIMIT 5
        ''').fetchall()
        pedidos_recentes = rows_to_dict_list(pedidos_recentes_data)

        # Produtos com baixo estoque
        produtos_baixo_estoque_data = db.execute('''
            SELECT id, nome, estoque
            FROM produtos
            WHERE estoque < 10 AND ativo = 1
            ORDER BY estoque ASC
            LIMIT 5
        ''').fetchall()
        produtos_baixo_estoque = rows_to_dict_list(produtos_baixo_estoque_data)

        return render_template('admin/dashboard.html',
                            stats=stats,
                            pedidos_recentes=pedidos_recentes,
                            produtos_baixo_estoque=produtos_baixo_estoque,
                            now=datetime.now())
    except sqlite3.Error:
        flash('Erro ao carregar dashboard', 'danger')
        return render_template('admin/dashboard.html',
                            stats={},
                            pedidos_recentes=[],
                            produtos_baixo_estoque=[],
                            now=datetime.now())
    finally:
        db.close()

@app.route('/admin/produtos', methods=['GET', 'POST'])
@admin_required
def admin_produtos():
    db = get_db()
    try:
        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'adicionar':
                nome = request.form['nome'].strip()
                descricao = request.form['descricao'].strip()
                preco = float(request.form['preco'])
                preco_promocional = request.form.get('preco_promocional')
                categoria_id = int(request.form['categoria_id'])
                estoque = int(request.form['estoque'])
                destaque = 1 if request.form.get('destaque') else 0
                ativo = 1 if request.form.get('ativo') else 0

                # Validações
                if preco <= 0:
                    flash('Preço deve ser maior que zero', 'danger')
                    return redirect(url_for('admin_produtos'))

                if estoque < 0:
                    flash('Estoque não pode ser negativo', 'danger')
                    return redirect(url_for('admin_produtos'))

                if preco_promocional:
                    preco_promocional = float(preco_promocional)
                    if preco_promocional >= preco:
                        flash('Preço promocional deve ser menor que o preço normal', 'danger')
                        return redirect(url_for('admin_produtos'))

                # Processar upload de imagem
                imagem_url = None
                if 'imagem' in request.files:
                    file = request.files['imagem']
                    if file and file.filename != '':
                        imagem_url, error = save_product_image(file)
                        if error:
                            flash(error, 'danger')
                            return redirect(url_for('admin_produtos'))

                db.execute('''
                    INSERT INTO produtos (nome, descricao, preco, preco_promocional, categoria_id,
                                        estoque, destaque, ativo, imagem, data_cadastro)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (nome, descricao, preco, preco_promocional if preco_promocional else None,
                      categoria_id, estoque, destaque, ativo, imagem_url))
                db.commit()
                flash('Produto adicionado com sucesso!', 'success')

            elif action == 'editar':
                produto_id = int(request.form['produto_id'])
                nome = request.form['nome'].strip()
                descricao = request.form['descricao'].strip()
                preco = float(request.form['preco'])
                preco_promocional = request.form.get('preco_promocional')
                categoria_id = int(request.form['categoria_id'])
                estoque = int(request.form['estoque'])
                destaque = 1 if request.form.get('destaque') else 0
                ativo = 1 if request.form.get('ativo') else 0

                # Validações
                if preco <= 0:
                    flash('Preço deve ser maior que zero', 'danger')
                    return redirect(url_for('admin_produtos'))

                if estoque < 0:
                    flash('Estoque não pode ser negativo', 'danger')
                    return redirect(url_for('admin_produtos'))

                if preco_promocional:
                    preco_promocional = float(preco_promocional)
                    if preco_promocional >= preco:
                        flash('Preço promocional deve ser menor que o preço normal', 'danger')
                        return redirect(url_for('admin_produtos'))

                db.execute('''
                    UPDATE produtos
                    SET nome=?, descricao=?, preco=?, preco_promocional=?, categoria_id=?,
                        estoque=?, destaque=?, ativo=?
                    WHERE id=?
                ''', (nome, descricao, preco, preco_promocional if preco_promocional else None,
                      categoria_id, estoque, destaque, ativo, produto_id))
                db.commit()
                flash('Produto atualizado com sucesso!', 'success')

            elif action == 'alterar_imagem':
                produto_id = int(request.form['produto_id'])

                # Verificar se é para remover imagem
                if 'remover_imagem' in request.form:
                    # Buscar imagem atual para remover arquivo físico
                    produto = db.execute('SELECT imagem FROM produtos WHERE id = ?', (produto_id,)).fetchone()
                    if produto and produto['imagem']:
                        try:
                            file_path = os.path.join(app.root_path, produto['imagem'][1:])  # Remove a barra inicial
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception as e:
                            print(f"Erro ao remover arquivo: {e}")

                    db.execute('UPDATE produtos SET imagem = NULL WHERE id = ?', (produto_id,))
                    db.commit()
                    flash('Imagem removida com sucesso!', 'success')

                else:
                    # Upload de nova imagem
                    if 'imagem' in request.files:
                        file = request.files['imagem']
                        if file and file.filename != '':
                            # Remover imagem antiga se existir
                            produto = db.execute('SELECT imagem FROM produtos WHERE id = ?', (produto_id,)).fetchone()
                            if produto and produto['imagem']:
                                try:
                                    old_path = os.path.join(app.root_path, produto['imagem'][1:])
                                    if os.path.exists(old_path):
                                        os.remove(old_path)
                                except Exception as e:
                                    print(f"Erro ao remover arquivo antigo: {e}")

                            imagem_url, error = save_product_image(file)
                            if error:
                                flash(error, 'danger')
                            else:
                                db.execute('UPDATE produtos SET imagem = ? WHERE id = ?', (imagem_url, produto_id))
                                db.commit()
                                flash('Imagem do produto atualizada com sucesso!', 'success')
                        else:
                            flash('Nenhuma imagem selecionada', 'warning')
                    else:
                        flash('Nenhuma imagem selecionada', 'warning')

            elif action == 'desativar':
                produto_id = int(request.form['produto_id'])
                db.execute('UPDATE produtos SET ativo = 0 WHERE id = ?', (produto_id,))
                db.commit()
                flash('Produto desativado com sucesso!', 'info')

            elif action == 'ativar':
                produto_id = int(request.form['produto_id'])
                db.execute('UPDATE produtos SET ativo = 1 WHERE id = ?', (produto_id,))
                db.commit()
                flash('Produto ativado com sucesso!', 'success')

            elif action == 'excluir_permanentemente':
                produto_id = int(request.form['produto_id'])

                # Buscar imagem para remover arquivo físico
                produto = db.execute('SELECT imagem FROM produtos WHERE id = ?', (produto_id,)).fetchone()
                if produto and produto['imagem']:
                    try:
                        file_path = os.path.join(app.root_path, produto['imagem'][1:])
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        print(f"Erro ao remover arquivo: {e}")

                db.execute('DELETE FROM produtos WHERE id = ?', (produto_id,))
                db.commit()
                flash('Produto excluído permanentemente!', 'success')

        # Buscar produtos e categorias
        produtos_data = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            ORDER BY p.data_cadastro DESC
        ''').fetchall()
        produtos = rows_to_dict_list(produtos_data)

        categorias_data = db.execute('SELECT * FROM categorias WHERE ativo = 1').fetchall()
        categorias = rows_to_dict_list(categorias_data)

        return render_template('admin/produtos.html', produtos=produtos, categorias=categorias)

    except (ValueError, KeyError) as e:
        flash('Dados inválidos no formulário', 'danger')
        return redirect(url_for('admin_produtos'))
    except sqlite3.Error as e:
        flash('Erro no banco de dados', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        db.close()

@app.route('/admin/pedidos')
@admin_required
def admin_pedidos():
    db = get_db()
    try:
        pedidos_data = db.execute('''
            SELECT p.*, u.nome as cliente_nome, u.email as cliente_email
            FROM pedidos p
            JOIN usuarios u ON p.usuario_id = u.id
            ORDER BY p.data_pedido DESC
        ''').fetchall()
        pedidos = rows_to_dict_list(pedidos_data)
        return render_template('admin/pedidos.html', pedidos=pedidos)
    except sqlite3.Error:
        flash('Erro ao carregar pedidos', 'danger')
        return render_template('admin/pedidos.html', pedidos=[])
    finally:
        db.close()

@app.route('/admin/pedido/<int:id>')
@admin_required
def admin_pedido_detalhes(id):
    db = get_db()
    try:
        pedido_data = db.execute('''
            SELECT p.*, u.nome as cliente_nome, u.email as cliente_email, u.telefone as cliente_telefone
            FROM pedidos p
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE p.id = ?
        ''', (id,)).fetchone()

        if not pedido_data:
            flash('Pedido não encontrado', 'warning')
            return redirect(url_for('admin_pedidos'))

        pedido = row_to_dict(pedido_data)

        itens_data = db.execute('''
            SELECT ip.*, p.nome as produto_nome
            FROM itens_pedido ip
            JOIN produtos p ON ip.produto_id = p.id
            WHERE ip.pedido_id = ?
        ''', (id,)).fetchall()
        itens = rows_to_dict_list(itens_data)

        return render_template('admin/detalhes_pedido.html', pedido=pedido, itens=itens)
    except sqlite3.Error:
        flash('Erro ao carregar pedido', 'danger')
        return redirect(url_for('admin_pedidos'))
    finally:
        db.close()

@app.route('/admin/atualizar-status-pedido', methods=['POST'])
@admin_required
def admin_atualizar_status_pedido():
    try:
        pedido_id = int(request.form['pedido_id'])
        status = request.form['status']

        db = get_db()
        db.execute('UPDATE pedidos SET status = ? WHERE id = ?', (status, pedido_id))
        db.commit()
        db.close()

        flash('Status do pedido atualizado com sucesso!', 'success')
    except (ValueError, KeyError):
        flash('Erro ao atualizar status do pedido', 'danger')
    except sqlite3.Error:
        flash('Erro no banco de dados', 'danger')

    return redirect(url_for('admin_pedidos'))

@app.route('/admin/categorias', methods=['GET', 'POST'])
@admin_required
def admin_categorias():
    db = get_db()
    try:
        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'adicionar':
                nome = request.form['nome'].strip()
                descricao = request.form['descricao'].strip()

                if not nome:
                    flash('Nome da categoria é obrigatório', 'danger')
                    return redirect(url_for('admin_categorias'))

                db.execute('INSERT INTO categorias (nome, descricao) VALUES (?, ?)',
                          (nome, descricao))
                db.commit()
                flash('Categoria adicionada com sucesso!', 'success')

            elif action == 'editar':
                categoria_id = int(request.form['categoria_id'])
                nome = request.form['nome'].strip()
                descricao = request.form['descricao'].strip()

                if not nome:
                    flash('Nome da categoria é obrigatório', 'danger')
                    return redirect(url_for('admin_categorias'))

                db.execute('UPDATE categorias SET nome=?, descricao=? WHERE id=?',
                          (nome, descricao, categoria_id))
                db.commit()
                flash('Categoria atualizada com sucesso!', 'success')

            elif action == 'excluir':
                categoria_id = int(request.form['categoria_id'])
                db.execute('UPDATE categorias SET ativo = 0 WHERE id = ?', (categoria_id,))
                db.commit()
                flash('Categoria desativada com sucesso!', 'info')

        categorias_data = db.execute('SELECT * FROM categorias WHERE ativo = 1').fetchall()
        categorias = rows_to_dict_list(categorias_data)
        return render_template('admin/categorias.html', categorias=categorias)

    except (ValueError, KeyError):
        flash('Dados inválidos no formulário', 'danger')
        return redirect(url_for('admin_categorias'))
    except sqlite3.Error:
        flash('Erro no banco de dados', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        db.close()

@app.route('/admin/clientes')
@admin_required
def admin_clientes():
    db = get_db()
    try:
        clientes_data = db.execute('''
            SELECT u.*,
                   COUNT(p.id) as pedidos_count
            FROM usuarios u
            LEFT JOIN pedidos p ON u.id = p.usuario_id
            WHERE u.tipo = 'cliente'
            GROUP BY u.id
            ORDER BY u.data_cadastro DESC
        ''').fetchall()
        clientes = rows_to_dict_list(clientes_data)
        return render_template('admin/clientes.html', clientes=clientes)
    except sqlite3.Error:
        flash('Erro ao carregar clientes', 'danger')
        return render_template('admin/clientes.html', clientes=[])
    finally:
        db.close()

@app.route('/admin/cliente/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_excluir_cliente(id):
    """Exclui um cliente e seus dados relacionados"""
    db = get_db()
    try:
        # Verificar se o cliente existe
        cliente_data = db.execute('SELECT * FROM usuarios WHERE id = ? AND tipo = "cliente"', (id,)).fetchone()

        if not cliente_data:
            flash('Cliente não encontrado', 'warning')
            return redirect(url_for('admin_clientes'))

        cliente = row_to_dict(cliente_data)

        # Verificar se o usuário está tentando excluir a si mesmo
        if cliente['id'] == session.get('user_id'):
            flash('Você não pode excluir sua própria conta', 'error')
            return redirect(url_for('admin_clientes'))

        # Verificar se o cliente tem pedidos
        pedidos = db.execute('SELECT id FROM pedidos WHERE usuario_id = ?', (id,)).fetchall()

        if pedidos:
            flash('Não é possível excluir cliente com pedidos realizados. Desative a conta instead.', 'warning')
            return redirect(url_for('admin_clientes'))

        # Iniciar transação para exclusão em cascata
        db.execute('BEGIN TRANSACTION')

        try:
            # Excluir avaliações do cliente
            db.execute('DELETE FROM avaliacoes WHERE usuario_id = ?', (id,))

            # Excluir itens do carrinho do cliente
            db.execute('DELETE FROM carrinho WHERE usuario_id = ?', (id,))

            # Finalmente, excluir o cliente
            db.execute('DELETE FROM usuarios WHERE id = ?', (id,))

            db.execute('COMMIT')
            flash(f'Cliente {cliente["nome"]} excluído com sucesso!', 'success')

        except sqlite3.Error as e:
            db.execute('ROLLBACK')
            flash('Erro ao excluir cliente. Tente novamente.', 'danger')

    except sqlite3.Error as e:
        flash('Erro no banco de dados', 'danger')
    finally:
        db.close()

    return redirect(url_for('admin_clientes'))

@app.route('/admin/cliente/<int:id>/desativar', methods=['POST'])
@admin_required
def admin_desativar_cliente(id):
    """Desativa/reativa um cliente (alternância)"""
    db = get_db()
    try:
        cliente_data = db.execute('SELECT * FROM usuarios WHERE id = ? AND tipo = "cliente"', (id,)).fetchone()

        if not cliente_data:
            flash('Cliente não encontrado', 'warning')
            return redirect(url_for('admin_clientes'))

        cliente = row_to_dict(cliente_data)

        if cliente['id'] == session.get('user_id'):
            flash('Você não pode desativar sua própria conta', 'error')
            return redirect(url_for('admin_clientes'))

        # Verificar se a tabela tem campo 'ativo'
        campos = [desc[0] for desc in db.execute('PRAGMA table_info(usuarios)').fetchall()]
        tem_campo_ativo = 'ativo' in campos

        if tem_campo_ativo:
            # Alternar status se o campo existir
            novo_status = 0 if cliente.get('ativo', 1) == 1 else 1
            db.execute('UPDATE usuarios SET ativo = ? WHERE id = ?', (novo_status, id))
            acao = "desativado" if novo_status == 0 else "reativado"
        else:
            # Se não tiver campo ativo, apenas mostrar mensagem
            flash('Funcionalidade de ativar/desativar não disponível. Adicione o campo "ativo" na tabela usuarios.', 'warning')
            return redirect(url_for('admin_clientes'))

        db.commit()
        flash(f'Cliente {cliente["nome"]} {acao} com sucesso!', 'success')

    except sqlite3.Error as e:
        flash('Erro ao alterar status do cliente', 'danger')
    finally:
        db.close()

    return redirect(url_for('admin_clientes'))

@app.route('/admin/cliente/<int:id>/detalhes')
@admin_required
def admin_cliente_detalhes(id):
    """Exibe detalhes de um cliente específico"""
    db = get_db()
    try:
        cliente_data = db.execute('''
            SELECT * FROM usuarios
            WHERE id = ? AND tipo = "cliente"
        ''', (id,)).fetchone()

        if not cliente_data:
            flash('Cliente não encontrado', 'warning')
            return redirect(url_for('admin_clientes'))

        cliente = row_to_dict(cliente_data)

        # Buscar pedidos do cliente
        pedidos_data = db.execute('''
            SELECT p.*
            FROM pedidos p
            WHERE p.usuario_id = ?
            ORDER BY p.data_pedido DESC
        ''', (id,)).fetchall()
        pedidos = rows_to_dict_list(pedidos_data)

        # Buscar avaliações do cliente
        avaliacoes_data = db.execute('''
            SELECT a.*, p.nome as produto_nome
            FROM avaliacoes a
            JOIN produtos p ON a.produto_id = p.id
            WHERE a.usuario_id = ?
            ORDER BY a.data_avaliacao DESC
        ''', (id,)).fetchall()
        avaliacoes = rows_to_dict_list(avaliacoes_data)

        # Estatísticas do cliente
        total_pedidos = len(pedidos)
        total_gasto = sum(pedido['total'] for pedido in pedidos if pedido['total'])
        total_avaliacoes = len(avaliacoes)

        return render_template('admin/cliente_detalhes.html',
                            cliente=cliente,
                            pedidos=pedidos,
                            avaliacoes=avaliacoes,
                            total_pedidos=total_pedidos,
                            total_gasto=total_gasto,
                            total_avaliacoes=total_avaliacoes)

    except sqlite3.Error as e:
        flash('Erro ao carregar detalhes do cliente', 'danger')
        return redirect(url_for('admin_clientes'))
    finally:
        db.close()
# ==================== ROTAS PARA EXCLUIR PEDIDOS ====================

@app.route('/admin/pedido/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_excluir_pedido(id):
    """Exclui um pedido e restaura o estoque dos produtos"""
    db = get_db()
    try:
        # Verificar se o pedido existe
        pedido_data = db.execute('SELECT * FROM pedidos WHERE id = ?', (id,)).fetchone()

        if not pedido_data:
            flash('Pedido não encontrado', 'warning')
            return redirect(url_for('admin_pedidos'))

        pedido = row_to_dict(pedido_data)

        # Iniciar transação para exclusão em cascata
        db.execute('BEGIN TRANSACTION')

        try:
            # Buscar itens do pedido para restaurar estoque
            itens_data = db.execute('''
                SELECT produto_id, quantidade
                FROM itens_pedido
                WHERE pedido_id = ?
            ''', (id,)).fetchall()
            itens = rows_to_dict_list(itens_data)

            # Restaurar estoque dos produtos
            for item in itens:
                db.execute('''
                    UPDATE produtos
                    SET estoque = estoque + ?
                    WHERE id = ?
                ''', (item['quantidade'], item['produto_id']))

            # Excluir itens do pedido
            db.execute('DELETE FROM itens_pedido WHERE pedido_id = ?', (id,))

            # Excluir o pedido
            db.execute('DELETE FROM pedidos WHERE id = ?', (id,))

            db.execute('COMMIT')
            flash(f'Pedido #{pedido["id"]} excluído com sucesso! Estoque dos produtos restaurado.', 'success')

        except sqlite3.Error as e:
            db.execute('ROLLBACK')
            flash('Erro ao excluir pedido. Tente novamente.', 'danger')
            print(f"Erro ao excluir pedido: {e}")

    except sqlite3.Error as e:
        flash('Erro no banco de dados', 'danger')
        print(f"Erro no banco de dados: {e}")
    finally:
        db.close()

    return redirect(url_for('admin_pedidos'))

@app.route('/admin/pedidos/limpar-cancelados', methods=['POST'])
@admin_required
def admin_limpar_pedidos_cancelados():
    """Exclui todos os pedidos cancelados"""
    db = get_db()
    try:
        # Buscar pedidos cancelados
        pedidos_cancelados_data = db.execute('SELECT id FROM pedidos WHERE status = "cancelado"').fetchall()
        pedidos_cancelados = rows_to_dict_list(pedidos_cancelados_data)

        if not pedidos_cancelados:
            flash('Nenhum pedido cancelado encontrado', 'info')
            return redirect(url_for('admin_pedidos'))

        # Iniciar transação
        db.execute('BEGIN TRANSACTION')

        try:
            contador = 0
            for pedido in pedidos_cancelados:
                # Buscar itens do pedido para restaurar estoque
                itens_data = db.execute('''
                    SELECT produto_id, quantidade
                    FROM itens_pedido
                    WHERE pedido_id = ?
                ''', (pedido['id'],)).fetchall()
                itens = rows_to_dict_list(itens_data)

                # Restaurar estoque dos produtos
                for item in itens:
                    db.execute('''
                        UPDATE produtos
                        SET estoque = estoque + ?
                        WHERE id = ?
                    ''', (item['quantidade'], item['produto_id']))

                # Excluir itens do pedido
                db.execute('DELETE FROM itens_pedido WHERE pedido_id = ?', (pedido['id'],))

                # Excluir o pedido
                db.execute('DELETE FROM pedidos WHERE id = ?', (pedido['id'],))

                contador += 1

            db.execute('COMMIT')
            flash(f'{contador} pedido(s) cancelado(s) excluído(s) com sucesso! Estoque dos produtos restaurado.', 'success')

        except sqlite3.Error as e:
            db.execute('ROLLBACK')
            flash('Erro ao excluir pedidos cancelados. Tente novamente.', 'danger')
            print(f"Erro ao excluir pedidos cancelados: {e}")

    except sqlite3.Error as e:
        flash('Erro no banco de dados', 'danger')
        print(f"Erro no banco de dados: {e}")
    finally:
        db.close()

    return redirect(url_for('admin_pedidos'))
    # ==================== ROTAS PARA EXCLUIR PRODUTOS ====================

@app.route('/admin/produto/<int:id>/excluir', methods=['POST'])
@admin_required
def admin_excluir_produto(id):
    """Exclui um produto permanentemente"""
    db = get_db()
    try:
        # Verificar se o produto existe
        produto_data = db.execute('SELECT * FROM produtos WHERE id = ?', (id,)).fetchone()

        if not produto_data:
            flash('Produto não encontrado', 'warning')
            return redirect(url_for('admin_produtos'))

        produto = row_to_dict(produto_data)

        # Verificar se o produto tem pedidos associados
        pedidos_associados = db.execute('''
            SELECT COUNT(*) as total
            FROM itens_pedido
            WHERE produto_id = ?
        ''', (id,)).fetchone()

        if pedidos_associados and pedidos_associados['total'] > 0:
            flash('Não é possível excluir produto com pedidos associados. Desative o produto instead.', 'warning')
            return redirect(url_for('admin_produtos'))

        # Iniciar transação
        db.execute('BEGIN TRANSACTION')

        try:
            # Remover imagem física se existir
            if produto['imagem']:
                try:
                    file_path = os.path.join(app.root_path, produto['imagem'][1:])  # Remove a barra inicial
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Erro ao remover arquivo de imagem: {str(e)}")

            # Remover avaliações do produto
            db.execute('DELETE FROM avaliacoes WHERE produto_id = ?', (id,))

            # Remover do carrinho dos usuários
            db.execute('DELETE FROM carrinho WHERE produto_id = ?', (id,))

            # Excluir o produto
            db.execute('DELETE FROM produtos WHERE id = ?', (id,))

            db.execute('COMMIT')
            flash(f'Produto "{produto["nome"]}" excluído permanentemente!', 'success')

        except sqlite3.Error as e:
            db.execute('ROLLBACK')
            logger.error(f"Erro ao excluir produto {id}: {str(e)}")
            flash('Erro ao excluir produto. Tente novamente.', 'danger')

    except sqlite3.Error as e:
        logger.error(f"Erro no banco de dados ao excluir produto: {str(e)}")
        flash('Erro no banco de dados', 'danger')
    finally:
        db.close()

    return redirect(url_for('admin_produtos'))

@app.route('/admin/produto/<int:id>/desativar', methods=['POST'])
@admin_required
def admin_desativar_produto(id):
    """Desativa/reativa um produto"""
    db = get_db()
    try:
        produto_data = db.execute('SELECT * FROM produtos WHERE id = ?', (id,)).fetchone()

        if not produto_data:
            flash('Produto não encontrado', 'warning')
            return redirect(url_for('admin_produtos'))

        produto = row_to_dict(produto_data)
        novo_status = 0 if produto['ativo'] == 1 else 1
        acao = "desativado" if novo_status == 0 else "reativado"

        db.execute('UPDATE produtos SET ativo = ? WHERE id = ?', (novo_status, id))
        db.commit()

        flash(f'Produto "{produto["nome"]}" {acao} com sucesso!', 'success')

    except sqlite3.Error as e:
        logger.error(f"Erro ao alterar status do produto {id}: {str(e)}")
        flash('Erro ao alterar status do produto', 'danger')
    finally:
        db.close()

    return redirect(url_for('admin_produtos'))

@app.route('/admin/produtos/limpar-inativos', methods=['POST'])
@admin_required
def admin_limpar_produtos_inativos():
    """Exclui permanentemente todos os produtos inativos sem pedidos associados"""
    db = get_db()
    try:
        # Buscar produtos inativos sem pedidos
        produtos_inativos_data = db.execute('''
            SELECT p.id, p.nome, p.imagem
            FROM produtos p
            LEFT JOIN itens_pedido ip ON p.id = ip.produto_id
            WHERE p.ativo = 0 AND ip.produto_id IS NULL
        ''').fetchall()

        produtos_inativos = rows_to_dict_list(produtos_inativos_data)

        if not produtos_inativos:
            flash('Nenhum produto inativo sem pedidos encontrado', 'info')
            return redirect(url_for('admin_produtos'))

        # Iniciar transação
        db.execute('BEGIN TRANSACTION')

        try:
            contador = 0
            for produto in produtos_inativos:
                # Remover imagem física se existir
                if produto['imagem']:
                    try:
                        file_path = os.path.join(app.root_path, produto['imagem'][1:])
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        logger.warning(f"Erro ao remover arquivo de imagem: {str(e)}")

                # Remover avaliações
                db.execute('DELETE FROM avaliacoes WHERE produto_id = ?', (produto['id'],))

                # Remover do carrinho
                db.execute('DELETE FROM carrinho WHERE produto_id = ?', (produto['id'],))

                # Excluir produto
                db.execute('DELETE FROM produtos WHERE id = ?', (produto['id'],))

                contador += 1

            db.execute('COMMIT')
            flash(f'{contador} produto(s) inativo(s) excluído(s) permanentemente!', 'success')

        except sqlite3.Error as e:
            db.execute('ROLLBACK')
            logger.error(f"Erro ao limpar produtos inativos: {str(e)}")
            flash('Erro ao excluir produtos inativos. Tente novamente.', 'danger')

    except sqlite3.Error as e:
        logger.error(f"Erro no banco de dados ao limpar produtos: {str(e)}")
        flash('Erro no banco de dados', 'danger')
    finally:
        db.close()

    return redirect(url_for('admin_produtos'))
# ==================== ROTAS DE RELATÓRIOS ====================

# Relatórios em memória (download direto)
@app.route('/admin/relatorio/produtos/excel')
@admin_required
def relatorio_produtos_excel():
    """Gera relatório de produtos em Excel (download direto)"""
    db = get_db()
    try:
        produtos_data = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.ativo = 1
            ORDER BY p.nome
        ''').fetchall()

        produtos_dict = rows_to_dict_list(produtos_data)
        excel_file = gerar_excel_produtos(produtos_dict)

        filename = f"relatorio_produtos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

        return send_file(
            excel_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
        return redirect(url_for('admin_produtos'))
    finally:
        db.close()

@app.route('/admin/relatorio/produtos/pdf')
@admin_required
def relatorio_produtos_pdf():
    """Gera relatório de produtos em PDF (download direto)"""
    db = get_db()
    try:
        produtos_data = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.ativo = 1
            ORDER BY p.nome
        ''').fetchall()

        produtos_dict = rows_to_dict_list(produtos_data)
        pdf_file = gerar_pdf_produtos(produtos_dict)

        filename = f"relatorio_produtos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        return send_file(
            pdf_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
        return redirect(url_for('admin_produtos'))
    finally:
        db.close()

@app.route('/admin/relatorio/pedidos/excel')
@admin_required
def relatorio_pedidos_excel():
    """Gera relatório de pedidos em Excel (download direto)"""
    db = get_db()
    try:
        pedidos_data = db.execute('''
            SELECT p.*, u.nome as cliente_nome, u.email as cliente_email
            FROM pedidos p
            JOIN usuarios u ON p.usuario_id = u.id
            ORDER BY p.data_pedido DESC
        ''').fetchall()

        pedidos_dict = rows_to_dict_list(pedidos_data)
        excel_file = gerar_excel_pedidos(pedidos_dict)

        filename = f"relatorio_pedidos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

        return send_file(
            excel_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
        return redirect(url_for('admin_pedidos'))
    finally:
        db.close()

@app.route('/admin/relatorio/pedidos/pdf')
@admin_required
def relatorio_pedidos_pdf():
    """Gera relatório de pedidos em PDF (download direto)"""
    db = get_db()
    try:
        pedidos_data = db.execute('''
            SELECT p.*, u.nome as cliente_nome, u.email as cliente_email
            FROM pedidos p
            JOIN usuarios u ON p.usuario_id = u.id
            ORDER BY p.data_pedido DESC
        ''').fetchall()

        pedidos_dict = rows_to_dict_list(pedidos_data)
        pdf_file = gerar_pdf_pedidos(pedidos_dict)

        filename = f"relatorio_pedidos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        return send_file(
            pdf_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
        return redirect(url_for('admin_pedidos'))
    finally:
        db.close()

@app.route('/admin/relatorio/clientes/excel')
@admin_required
def relatorio_clientes_excel():
    """Gera relatório de clientes em Excel (download direto)"""
    db = get_db()
    try:
        clientes_data = db.execute("SELECT * FROM usuarios WHERE tipo = 'cliente'").fetchall()

        clientes_dict = rows_to_dict_list(clientes_data)
        excel_file = gerar_excel_clientes(clientes_dict)

        filename = f"relatorio_clientes_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

        return send_file(
            excel_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
        return redirect(url_for('admin_clientes'))
    finally:
        db.close()

@app.route('/admin/relatorio/clientes/pdf')
@admin_required
def relatorio_clientes_pdf():
    """Gera relatório de clientes em PDF (download direto)"""
    db = get_db()
    try:
        clientes_data = db.execute("SELECT * FROM usuarios WHERE tipo = 'cliente'").fetchall()

        clientes_dict = rows_to_dict_list(clientes_data)
        pdf_file = gerar_pdf_clientes(clientes_dict)

        filename = f"relatorio_clientes_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        return send_file(
            pdf_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
        return redirect(url_for('admin_clientes'))
    finally:
        db.close()

# Relatórios salvos no servidor
@app.route('/admin/relatorio/produtos/salvar-excel')
@admin_required
def salvar_relatorio_produtos_excel():
    """Salva relatório de produtos em Excel no servidor"""
    db = get_db()
    try:
        produtos_data = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.ativo = 1
            ORDER BY p.nome
        ''').fetchall()

        produtos_dict = rows_to_dict_list(produtos_data)
        filename, filepath = gerar_excel_produtos(produtos_dict, salvar_arquivo=True)

        flash(f'Relatório salvo: {filename}', 'success')
        return redirect(url_for('admin_produtos'))

    except Exception as e:
        flash(f'Erro ao salvar relatório: {str(e)}', 'danger')
        return redirect(url_for('admin_produtos'))
    finally:
        db.close()

@app.route('/admin/relatorio/produtos/salvar-pdf')
@admin_required
def salvar_relatorio_produtos_pdf():
    """Salva relatório de produtos em PDF no servidor"""
    db = get_db()
    try:
        produtos_data = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.ativo = 1
            ORDER BY p.nome
        ''').fetchall()

        produtos_dict = rows_to_dict_list(produtos_data)
        filename, filepath = gerar_pdf_produtos(produtos_dict, salvar_arquivo=True)

        flash(f'Relatório salvo: {filename}', 'success')
        return redirect(url_for('admin_produtos'))

    except Exception as e:
        flash(f'Erro ao salvar relatório: {str(e)}', 'danger')
        return redirect(url_for('admin_produtos'))
    finally:
        db.close()

# Lista de relatórios salvos
@app.route('/admin/relatorios')
@admin_required
def lista_relatorios():
    """Lista todos os relatórios salvos"""
    relatorios = listar_relatorios()
    return render_template('admin/lista_relatorios.html', relatorios=relatorios)

@app.route('/admin/relatorios/download/<filename>')
@admin_required
def download_relatorio(filename):
    """Faz download de um relatório salvo"""
    filepath = os.path.join(RELATORIOS_DIR, secure_filename(filename))

    if os.path.exists(filepath):
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename
        )
    else:
        flash('Arquivo não encontrado', 'danger')
        return redirect(url_for('lista_relatorios'))

@app.route('/admin/relatorios/excluir/<filename>', methods=['POST'])
@admin_required
def excluir_relatorio(filename):
    """Exclui um relatório salvo"""
    filepath = os.path.join(RELATORIOS_DIR, secure_filename(filename))

    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f'Relatório {filename} excluído com sucesso', 'success')
    else:
        flash('Arquivo não encontrado', 'danger')

    return redirect(url_for('lista_relatorios'))

# ==================== TRATAMENTO DE ERROS ====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

# ==================== INICIALIZAÇÃO ====================

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
