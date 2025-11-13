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

# Funções auxiliares para converter Row para dicionário
def row_to_dict(row):
    """Converte uma linha SQLite Row para dicionário"""
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}

def rows_to_dict_list(rows):
    """Converte uma lista de linhas SQLite Row para lista de dicionários"""
    return [row_to_dict(row) for row in rows]

# ==================== ROTAS PÚBLICAS ====================

@app.route('/')
def index():
    db = get_db()
    try:
        produtos = db.execute('''
            SELECT * FROM produtos
            WHERE ativo = 1 AND destaque = 1
            LIMIT 6
        ''').fetchall()
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

        produtos = db.execute(query, params).fetchall()
        categorias = db.execute('SELECT * FROM categorias WHERE ativo = 1').fetchall()

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
        produto = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.id = ? AND p.ativo = 1
        ''', (id,)).fetchone()

        if not produto:
            flash('Produto não encontrado', 'warning')
            return redirect(url_for('produtos_lista'))

        avaliacoes = db.execute('''
            SELECT a.*, u.nome as usuario_nome
            FROM avaliacoes a
            JOIN usuarios u ON a.usuario_id = u.id
            WHERE a.produto_id = ?
            ORDER BY a.data_avaliacao DESC
        ''', (id,)).fetchall()

        # Produtos relacionados (mesma categoria)
        produtos_relacionados = db.execute('''
            SELECT id, nome, preco, preco_promocional, imagem
            FROM produtos
            WHERE categoria_id = ? AND id != ? AND ativo = 1
            LIMIT 4
        ''', (produto['categoria_id'], id)).fetchall()

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
        itens = db.execute('''
            SELECT c.*, p.nome, p.preco, p.preco_promocional, p.imagem, p.estoque,
                   (COALESCE(p.preco_promocional, p.preco) * c.quantidade) as subtotal
            FROM carrinho c
            JOIN produtos p ON c.produto_id = p.id
            WHERE c.usuario_id = ? AND p.ativo = 1
        ''', (session['user_id'],)).fetchall()

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
            itens = db.execute('''
                SELECT c.*, p.preco, p.preco_promocional, p.estoque, p.nome
                FROM carrinho c
                JOIN produtos p ON c.produto_id = p.id
                WHERE c.usuario_id = ?
            ''', (session['user_id'],)).fetchall()

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
        pedidos = db.execute('''
            SELECT * FROM pedidos
            WHERE usuario_id = ?
            ORDER BY data_pedido DESC
        ''', (session['user_id'],)).fetchall()
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
        pedido = db.execute('''
            SELECT * FROM pedidos
            WHERE id = ? AND usuario_id = ?
        ''', (id, session['user_id'])).fetchone()

        if not pedido:
            flash('Pedido não encontrado', 'warning')
            return redirect(url_for('meus_pedidos'))

        itens = db.execute('''
            SELECT ip.*, p.nome, p.imagem
            FROM itens_pedido ip
            JOIN produtos p ON ip.produto_id = p.id
            WHERE ip.pedido_id = ?
        ''', (id,)).fetchall()

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
        pedidos_recentes = rows_to_dict_list(db.execute('''
            SELECT p.*, u.nome as usuario_nome
            FROM pedidos p
            JOIN usuarios u ON p.usuario_id = u.id
            ORDER BY p.data_pedido DESC
            LIMIT 5
        ''').fetchall())

        # Produtos com baixo estoque
        produtos_baixo_estoque = rows_to_dict_list(db.execute('''
            SELECT id, nome, estoque
            FROM produtos
            WHERE estoque < 10 AND ativo = 1
            ORDER BY estoque ASC
            LIMIT 5
        ''').fetchall())

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
        produtos = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            ORDER BY p.data_cadastro DESC
        ''').fetchall()

        categorias = db.execute('SELECT * FROM categorias WHERE ativo = 1').fetchall()

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
        pedidos = db.execute('''
            SELECT p.*, u.nome as cliente_nome, u.email as cliente_email
            FROM pedidos p
            JOIN usuarios u ON p.usuario_id = u.id
            ORDER BY p.data_pedido DESC
        ''').fetchall()
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
        pedido = db.execute('''
            SELECT p.*, u.nome as cliente_nome, u.email as cliente_email, u.telefone as cliente_telefone
            FROM pedidos p
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE p.id = ?
        ''', (id,)).fetchone()

        if not pedido:
            flash('Pedido não encontrado', 'warning')
            return redirect(url_for('admin_pedidos'))

        itens = db.execute('''
            SELECT ip.*, p.nome as produto_nome
            FROM itens_pedido ip
            JOIN produtos p ON ip.produto_id = p.id
            WHERE ip.pedido_id = ?
        ''', (id,)).fetchall()

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

        categorias = db.execute('SELECT * FROM categorias WHERE ativo = 1').fetchall()
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
        clientes = db.execute("SELECT * FROM usuarios WHERE tipo = 'cliente'").fetchall()
        return render_template('admin/clientes.html', clientes=clientes)
    except sqlite3.Error:
        flash('Erro ao carregar clientes', 'danger')
        return render_template('admin/clientes.html', clientes=[])
    finally:
        db.close()

# ==================== ROTAS DE RELATÓRIOS ====================

# Relatórios em memória (download direto)
@app.route('/admin/relatorio/produtos/excel')
@admin_required
def relatorio_produtos_excel():
    """Gera relatório de produtos em Excel (download direto)"""
    db = get_db()
    try:
        produtos = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.ativo = 1
            ORDER BY p.nome
        ''').fetchall()

        produtos_dict = [dict(produto) for produto in produtos]
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
        produtos = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.ativo = 1
            ORDER BY p.nome
        ''').fetchall()

        produtos_dict = [dict(produto) for produto in produtos]
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
        pedidos = db.execute('''
            SELECT p.*, u.nome as cliente_nome, u.email as cliente_email
            FROM pedidos p
            JOIN usuarios u ON p.usuario_id = u.id
            ORDER BY p.data_pedido DESC
        ''').fetchall()

        pedidos_dict = [dict(pedido) for pedido in pedidos]
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
        pedidos = db.execute('''
            SELECT p.*, u.nome as cliente_nome, u.email as cliente_email
            FROM pedidos p
            JOIN usuarios u ON p.usuario_id = u.id
            ORDER BY p.data_pedido DESC
        ''').fetchall()

        pedidos_dict = [dict(pedido) for pedido in pedidos]
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
        clientes = db.execute("SELECT * FROM usuarios WHERE tipo = 'cliente'").fetchall()

        clientes_dict = [dict(cliente) for cliente in clientes]
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
        clientes = db.execute("SELECT * FROM usuarios WHERE tipo = 'cliente'").fetchall()

        clientes_dict = [dict(cliente) for cliente in clientes]
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
        produtos = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.ativo = 1
            ORDER BY p.nome
        ''').fetchall()

        produtos_dict = [dict(produto) for produto in produtos]
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
        produtos = db.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.ativo = 1
            ORDER BY p.nome
        ''').fetchall()

        produtos_dict = [dict(produto) for produto in produtos]
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
