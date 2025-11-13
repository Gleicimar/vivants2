import sqlite3
from werkzeug.security import generate_password_hash

def get_db():
    conn = sqlite3.connect('vivants.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.executescript('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            telefone TEXT,
            tipo TEXT DEFAULT 'cliente',
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT,
            ativo INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT,
            preco REAL NOT NULL,
            preco_promocional REAL,
            categoria_id INTEGER,
            estoque INTEGER DEFAULT 0,
            imagem TEXT,
            ativo INTEGER DEFAULT 1,
            destaque INTEGER DEFAULT 0,
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        );

        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pendente',
            endereco_entrega TEXT,
            data_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS itens_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL,
            FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        );

        CREATE TABLE IF NOT EXISTS carrinho (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER DEFAULT 1,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        );

        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            nota INTEGER CHECK(nota >= 1 AND nota <= 5),
            comentario TEXT,
            data_avaliacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (produto_id) REFERENCES produtos(id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );
    ''')

    try:
        conn.execute('''
            INSERT INTO usuarios (nome, email, senha, tipo)
            VALUES (?, ?, ?, ?)
        ''', ('Administrador', 'admin@vivants.com',
              generate_password_hash('admin123'), 'admin'))

        categorias = [
            ('Skincare', 'Cuidados com a pele'),
            ('Maquiagem', 'Produtos de maquiagem'),
            ('Cabelos', 'Tratamentos capilares'),
            ('Corpo', 'Cuidados corporais'),
            ('Perfumaria', 'Perfumes e colônias')
        ]

        for cat in categorias:
            conn.execute('INSERT INTO categorias (nome, descricao) VALUES (?, ?)', cat)

        produtos = [
            ('Creme Facial Hidratante', 'Hidratação profunda para pele seca', 89.90, 79.90, 1, 50, 1),
            ('Batom Líquido Matte', 'Alta pigmentação e longa duração', 45.90, None, 2, 100, 1),
            ('Shampoo Revitalizante', 'Para cabelos danificados', 32.90, 28.90, 3, 75, 0),
            ('Perfume Florais', 'Fragrância suave e duradoura', 129.90, None, 5, 30, 1),
            ('Loção Corporal', 'Hidratação 24h', 55.90, 49.90, 4, 60, 0),
            ('Paleta de Sombras', 'Cores neutras e pigmentadas', 78.90, 69.90, 2, 40, 1)
        ]

        for produto in produtos:
            conn.execute('''
                INSERT INTO produtos (nome, descricao, preco, preco_promocional, categoria_id, estoque, destaque)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', produto)

        conn.commit()
    except:
        pass

    conn.close()
