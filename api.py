from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
import re  # Importar o módulo de expressões regulares
import os
import json
import qrcode


app = Flask(__name__, static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})

def gerar_qr_code(trabalhador_id):
    # Certifica-se de que o diretório para os QR Codes existe
    os.makedirs('static/qr_codes', exist_ok=True)
    conteudo = f"trabalhador_{trabalhador_id}"

    qr = qrcode.QRCode(
        version=1,  # Tamanho do QR Code (1 é o menor)
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,  # Tamanho da caixa
        border=4,  # Tamanho da borda
        
    )
    qr.add_data(conteudo)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Salva a imagem do QR Code
    img.save(f"static/qr_codes/qr_trabalhador_{trabalhador_id}.png")

@app.route('/qr_codes/<filename>', methods=['GET'])
def get_qr_code(filename):
    return send_from_directory('static/qr_codes', filename)


#criar cartão trabalhador
def criar_cartao(trabalhador_id, nome_trabalhador, secao, cor="white", pasta="trabalhadores"):
    os.makedirs(f'static/cartoes/{pasta}', exist_ok=True)

    # Caminho do QR Code gerado
    qr_code_path = f"static/qr_codes/qr_trabalhador_{trabalhador_id}.png"

    # Abrir o QR Code
    qr_code_img = Image.open(qr_code_path)

    # Criar uma imagem para o cartão
    largura, altura = 400, 600
    cartao = Image.new('RGB', (largura, altura), cor)
    draw = ImageDraw.Draw(cartao)

    # Adicionar o QR Code ao cartão
    qr_code_tamanho = 200
    qr_code_img = qr_code_img.resize((qr_code_tamanho, qr_code_tamanho))
    cartao.paste(qr_code_img, (100, 100))

    # Configurar a fonte
    fonte = ImageFont.truetype("arial.ttf", size=24)

    # Centralizar o texto do nome
    texto_nome = f"Nome: {nome_trabalhador}"
    largura_texto_nome = draw.textbbox((0, 0), texto_nome, font=fonte)[2]  # Obter largura do texto
    pos_x_nome = (largura - largura_texto_nome) // 2
    draw.text((pos_x_nome, 320), texto_nome, fill="black", font=fonte)

    # Centralizar o texto da seção
    texto_secao = f"Seção: {secao}"
    largura_texto_secao = draw.textbbox((0, 0), texto_secao, font=fonte)[2]  # Obter largura do texto
    pos_x_secao = (largura - largura_texto_secao) // 2
    draw.text((pos_x_secao, 360), texto_secao, fill="black", font=fonte)

    # Salvar o cartão na pasta específica
    caminho_cartao = f"static/cartoes/{pasta}/cartao_{trabalhador_id}.png"
    cartao.save(caminho_cartao)

    return caminho_cartao





@app.route('/cartoes/<pasta>/<filename>', methods=['GET'])
def get_cartao(pasta, filename):
    # Certifique-se de que a pasta seja 'trabalhadores' ou 'chefes'
    if pasta not in ['trabalhadores', 'chefes']:
        return jsonify({"message": "Pasta inválida"}), 400
    return send_from_directory(f'static/cartoes/{pasta}', filename)



# Rota para o index.html
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# Rota para outros arquivos estáticos (CSS, JS, etc.)
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# Configuração do banco de dados
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, 'database', 'novo_fabrica.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelo Trabalhador
class Trabalhador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    secao = db.Column(db.String(100), nullable=False)
    chefe = db.Column(db.Boolean, default=False)  # Indica se é chefe
    senha_hash = db.Column(db.String(200), nullable=True)  # Senha protegida (hash)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)






# Criar tabelas automaticamente
with app.app_context():
    try:
        db.create_all()
        print(f"Banco de dados configurado em: {db_path}")
    except Exception as e:
        print(f"Erro ao configurar o banco de dados: {e}")


# Rota para listar trabalhadores
@app.route('/trabalhadores', methods=['GET'])
def get_trabalhadores():
    trabalhadores = Trabalhador.query.all()
    output = [
        {
            'id': t.id,
            'nome': t.nome,
            'secao': t.secao,
            'chefe': t.chefe  # Inclui a informação se é chefe
        } 
        for t in trabalhadores
    ]
    return jsonify(output)




# Rota para adicionar trabalhador
@app.route('/trabalhadores', methods=['POST'])
def add_trabalhador():
    try:
        data = request.get_json()
        nome = data.get('nome')
        secao = data.get('secao')
        is_chefe = data.get('chefe', False)

        if not nome or not secao:
            return jsonify({'message': 'Nome e seção são obrigatórios.'}), 400

        # Criar trabalhador
        trabalhador = Trabalhador(nome=nome, secao=secao, chefe=is_chefe)
        db.session.add(trabalhador)
        db.session.flush()  # Gera o ID do trabalhador sem commit ainda

        # Gerar QR Code com informações detalhadas do trabalhador
        conteudo = (
            f"ID: {trabalhador.id}\n"
            f"Nome: {trabalhador.nome}\n"
            f"Secção: {trabalhador.secao}\n"
        )
        os.makedirs('static/qr_codes', exist_ok=True)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(conteudo)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        qr_code_path = f"static/qr_codes/qr_trabalhador_{trabalhador.id}.png"
        img.save(qr_code_path)

        # Criar cartão do trabalhador
        criar_cartao(trabalhador.id, trabalhador.nome, trabalhador.secao)

        if is_chefe:
            # Criar cartão de chefe em uma pasta separada
            criar_cartao(trabalhador.id, trabalhador.nome, trabalhador.secao, cor="red", pasta="chefes")

        db.session.commit()

        mensagem = 'Trabalhador e chefe de secção adicionados com sucesso!' if is_chefe else 'Trabalhador adicionado com sucesso!'
        return jsonify({'message': mensagem, 'id': trabalhador.id}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao adicionar trabalhador: {e}")
        return jsonify({'message': 'Erro ao adicionar trabalhador.', 'details': str(e)}), 500




    
    # Rota para remover trabalhador
@app.route('/trabalhadores/<int:id>', methods=['DELETE'])
def delete_trabalhador(id):
    try:
        trabalhador = Trabalhador.query.get(id)
        if not trabalhador:
            return jsonify({'message': 'Trabalhador não encontrado'}), 404

        # Caminho do QR Code associado
        qr_code_path = os.path.join('static', 'qr_codes', f"qr_trabalhador_{trabalhador.id}.png")

        # Remove o arquivo de QR Code, se existir
        if os.path.exists(qr_code_path):
            os.remove(qr_code_path)
            print(f"QR Code removido: {qr_code_path}")
        else:
            print(f"QR Code não encontrado para exclusão: {qr_code_path}")





        #caminho para cartao associado ao trabalhador
        cartao_path = os.path.join('static', 'cartoes', 'trabalhadores', f"cartao_{trabalhador.id}.png")

        # Remove o arquivo de cartoes de trabalhador, se existir
        if os.path.exists(cartao_path):
            os.remove(cartao_path)
            print(f"Cartão removido: {cartao_path}")
        else:
            print(f"Cartão não encontrado para exclusão: {cartao_path}")

            #caminho para cartao associado ao chefe
        cartao_chefe_path = os.path.join('static', 'cartoes', 'chefes', f"cartao_{trabalhador.id}.png")

        # Remove o arquivo de cartoes de chefe, se existir
        if os.path.exists(cartao_chefe_path):
            os.remove(cartao_chefe_path)
            print(f"Cartão removido: {cartao_chefe_path}")
        else:
            print(f"Cartão não encontrado para exclusão: {cartao_chefe_path}")



        # Remove o trabalhador da base de dados
        db.session.delete(trabalhador)
        db.session.commit()

        return jsonify({'message': 'Trabalhador removido com sucesso!'}), 200
    except Exception as e:
        print(f"Erro ao remover trabalhador: {e}")
        return jsonify({'message': 'Erro ao remover trabalhador', 'details': str(e)}), 500


    





    





       # Modelo Palete
# Definição do modelo Palete antes de RegistroTrabalho
class Palete(db.Model):
    __tablename__ = 'palete'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data_entrega = db.Column(db.String(100), nullable=False)
    op = db.Column(db.String(100), nullable=False)
    referencia = db.Column(db.String(100), nullable=False)
    nome_produto = db.Column(db.String(100), nullable=False)
    medida = db.Column(db.String(100), nullable=False)
    cor_botao = db.Column(db.String(100), nullable=False)
    cor_ribete = db.Column(db.String(100), nullable=False)
    leva_embalagem = db.Column(db.Boolean, nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False)
    numero_lote = db.Column(db.String(100), nullable=False)
    qr_code_path = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"<Palete {self.id}, Produto: {self.nome_produto}>"




    # Agora o RegistroTrabalho pode referenciar Palete
class RegistroTrabalho(db.Model):
    __tablename__ = 'registro_trabalho'
    id = db.Column(db.Integer, primary_key=True)
    trabalhador_id = db.Column(db.Integer, db.ForeignKey('trabalhador.id'), nullable=False)
    palete_id = db.Column(db.Integer, db.ForeignKey('palete.id'), nullable=False)
    horario_inicio = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    horario_fim = db.Column(db.DateTime, nullable=True)

    trabalhador = db.relationship('Trabalhador', backref=db.backref('registros', lazy=True))
    palete = db.relationship('Palete', backref=db.backref('registros', lazy=True))

    def __repr__(self):
        return f"<RegistroTrabalho ID: {self.id}, Trabalhador ID: {self.trabalhador_id}>"


# Função para gerar QR code da palete
def gerar_qr_code_palete(palete):
    # Certifica-se de que o diretório de QR codes existe
    os.makedirs('static/qr_codes_paletes', exist_ok=True)

    # Conteúdo do QR Code com os dados da palete
    conteudo = (
        f"ID: {palete.id}\n"
        f"Data de Entrega: {palete.data_entrega}\n"
        f"OP: {palete.op}\n"
        f"Referência: {palete.referencia}\n"
        f"Nome do Produto: {palete.nome_produto}\n"
        f"Medida: {palete.medida}\n"
        f"Cor do Botão: {palete.cor_botao}\n"
        f"Cor do Ribete: {palete.cor_ribete}\n"
        f"Leva Embalagem: {'Sim' if palete.leva_embalagem else 'Não'}\n"
        f"Quantidade: {palete.quantidade}\n"
        f"Data e Hora: {palete.data_hora}\n"
        f"Número do Lote: {palete.numero_lote}"
    )

    # Gera o QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(conteudo)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Caminho para salvar o QR Code
    qr_code_path = f"static/qr_codes_paletes/qr_palete_{palete.id}.png"
    img.save(qr_code_path)

    return qr_code_path




       
       
# Rota para listar todas as paletes
@app.route('/paletes', methods=['GET'])
def get_paletes():
    try:
        # Obter todas as paletes do banco de dados
        paletes = Palete.query.all()

        # Verificar se existem paletes
        if not paletes:
            return jsonify({'message': 'Nenhuma palete encontrada.'}), 404

        # Preparar os dados para resposta
        output = [
            {
                'id': p.id,
                'data_entrega': p.data_entrega,
                'op': p.op,
                'referencia': p.referencia,
                'nome_produto': p.nome_produto,
                'medida': p.medida,
                'cor_botao': p.cor_botao,
                'cor_ribete': p.cor_ribete,
                'leva_embalagem': p.leva_embalagem,
                'quantidade': p.quantidade,
                'data_hora': p.data_hora,
                'numero_lote': p.numero_lote,
                'qr_code_path': p.qr_code_path,
            }
            for p in paletes
        ]

        # Log para depuração
        print(f"GET /paletes - {len(paletes)} paletes encontradas")

        # Retornar a resposta com os dados
        return jsonify(output), 200

    except Exception as e:
        # Log de erro e resposta para o cliente
        print(f"Erro ao obter paletes: {e}")
        return jsonify({'message': 'Erro ao obter paletes.', 'details': str(e)}), 500




# Rota para adicionar palete com geração de QR code
@app.route('/paletes', methods=['POST'])
def add_palete():
    try:
        data = request.get_json()
        
        # Validar os campos obrigatórios
        required_fields = ['data_entrega', 'op', 'referencia', 'nome_produto', 
                           'medida', 'cor_botao', 'cor_ribete', 
                           'leva_embalagem', 'quantidade', 'data_hora', 'numero_lote']
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        if missing_fields:
            return jsonify({'message': f'Campos obrigatórios ausentes: {", ".join(missing_fields)}'}), 400
        
        # Converter data_hora para datetime
        try:
            data_hora = datetime.fromisoformat(data['data_hora'])  # Converte o valor para um objeto datetime
        except ValueError:
            return jsonify({'message': 'Formato inválido para data e hora.'}), 400

        # Criar a nova palete
        nova_palete = Palete(
            data_entrega=data['data_entrega'],
            op=data['op'],
            referencia=data['referencia'],
            nome_produto=data['nome_produto'],
            medida=data['medida'],
            cor_botao=data['cor_botao'],
            cor_ribete=data['cor_ribete'],
            leva_embalagem=data['leva_embalagem'],
            quantidade=int(data['quantidade']),
            data_hora=data_hora,  # Agora é um objeto datetime
            numero_lote=data['numero_lote'],
        )
        
        db.session.add(nova_palete)
        db.session.flush()  # Gera o ID para a nova palete sem fazer commit ainda

        # Gerar QR Code com as informações da palete
        qr_code_path = gerar_qr_code_palete(nova_palete)
        nova_palete.qr_code_path = qr_code_path  # Atualiza o caminho do QR code na palete

        #gerar PDF palete
        pdf_path = gerar_folha_palete(nova_palete)


        db.session.commit()

        return jsonify({'message': 'Palete adicionada com sucesso!', 'id': nova_palete.id}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao adicionar palete: {e}")
        return jsonify({'message': 'Erro ao adicionar palete.', 'details': str(e)}), 500



@app.route('/FolhaPalete/<filename>', methods=['GET'])
def get_pdf(filename):
    return send_from_directory('static/FolhaPalete', filename)




        
# Rota para remover palete
@app.route('/paletes/<int:id>', methods=['DELETE'])
def delete_palete(id):
    try:
        # Buscar a palete pelo ID
        palete = Palete.query.get(id)
        if not palete:
            return jsonify({'message': 'Palete não encontrada'}), 404

        # Caminho do arquivo de QR Code associado
        qr_code_path = os.path.join('static', 'qr_codes_paletes', f"qr_palete_{palete.id}.png")

        # Remove o arquivo de QR Code, se existir
        if os.path.exists(qr_code_path):
            os.remove(qr_code_path)
            print(f"QR Code removido: {qr_code_path}")
        else:
            print(f"QR Code não encontrado para exclusão: {qr_code_path}")


             # Caminho do arquivo de PDF associado
        pdf_path = os.path.join('static', 'FolhaPalete', f"folha_palete_{palete.id}.pdf")

        # Remover o arquivo de PDF, se existir
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            print(f"PDF removido: {pdf_path}")
        else:
            print(f"PDF não encontrado para exclusão: {pdf_path}")

        # Remover a palete da base de dados
        db.session.delete(palete)
        db.session.commit()

        return jsonify({'message': 'Palete removida com sucesso!'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao remover palete: {e}")
        return jsonify({'message': 'Erro ao remover palete', 'details': str(e)}), 500


def gerar_folha_palete(palete):
    try:
        # Pasta onde os QR codes estão armazenados
        qr_code_path = os.path.join('static', 'qr_codes_paletes', f"qr_palete_{palete.id}.png")

        # Verificar se o QR code existe
        if not os.path.exists(qr_code_path):
            raise FileNotFoundError(f"QR Code não encontrado para a palete {palete.id}")

        # Nome do arquivo PDF
        output_pdf_path = f"static/FolhaPalete/folha_palete_{palete.id}.pdf"

        # Criar diretório para os PDFs, se necessário
        os.makedirs("static/FolhaPalete", exist_ok=True)

        # Configuração do PDF
        pdf = canvas.Canvas(output_pdf_path, pagesize=A4)
        width, height = A4

        # Adicionar QR code
        qr_code_img = ImageReader(qr_code_path)
        pdf.drawImage(qr_code_img, x=173, y=height - 300, width=250, height=250)

        # Título
        # Define a fonte e o tamanho
        pdf.setFont("Helvetica-Bold", 25)

        # Texto e largura da página
        texto = "Folha de Palete"
        largura_pagina = 595.27

        # Calcula a largura do texto
        largura_texto = pdf.stringWidth(texto, "Helvetica-Bold", 25)

        # Calcula a posição x centralizada
        x = (largura_pagina - largura_texto) / 2

        # Desenha o texto centralizado
        pdf.drawString(x, height - 50, texto)

        # Informações da palete
        pdf.setFont("Helvetica", 12)
        y = height - 350  # Posição inicial
        line_height = 20

        dados = [
            f"Data de Entrega: {palete.data_entrega}",
            f"OP: {palete.op}",
            f"Referência: {palete.referencia}",
            f"Nome do Produto: {palete.nome_produto}",
            f"Medida: {palete.medida}",
            f"Cor do Botão: {palete.cor_botao}",
            f"Cor do Ribete: {palete.cor_ribete}",
            f"Leva Embalagem: {'Sim' if palete.leva_embalagem else 'Não'}",
            f"Quantidade: {palete.quantidade}",
            f"Data e Hora: {palete.data_hora}",
            f"Número do Lote: {palete.numero_lote}",
        ]

        for dado in dados:
            pdf.drawString(50, y, dado)
            y -= line_height

        # Seção de preenchimento manual
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, "Seções de destino inicial e próximas:")
        y -= line_height

        secoes = [
            "Corte e vinco",
            "Seção da cola",
            "Acabamento",
            "Confeção",
            "Acabamento",
        ]

        pdf.setFont("Helvetica", 12)
        for secao in secoes:
            pdf.drawString(70, y, f"(   ) {secao}")
            y -= line_height

        # Finalizar o PDF
        pdf.save()

        print(f"PDF gerado com sucesso: {output_pdf_path}")
        return output_pdf_path

    except Exception as e:
        print(f"Erro ao gerar folha da palete: {e}")
        return None


    




# Rota para listar todos os registros de trabalho
@app.route('/registro_trabalho', methods=['GET'])
def get_registro_trabalho():
    registros = RegistroTrabalho.query.all()
    output = []
    for r in registros:
        output.append({
            'id': r.id,
            'trabalhador': {'id': r.trabalhador.id, 'nome': r.trabalhador.nome},
            'horario_inicio': r.horario_inicio.isoformat(),
            'horario_fim': r.horario_fim.isoformat() if r.horario_fim else None
        })
    print(f"GET /registro_trabalho - {len(registros)} registros encontrados")
    return jsonify(output)


# Rota para registrar início ou fim de trabalho
@app.route('/registro_trabalho', methods=['POST'])
def registro_trabalho():
    try:
        data = request.get_json()

        # Extração do ID do Trabalhador a partir do QR Code
        trabalhador_info = data.get('trabalhador_qr')  # Conteúdo do QR Code do Trabalhador
        if not trabalhador_info:
            return jsonify({'message': 'QR Code do trabalhador não fornecido.'}), 400

        # Extração do ID da Palete a partir do QR Code
        palete_info = data.get('palete_qr')  # Conteúdo do QR Code da Palete
        if not palete_info:
            return jsonify({'message': 'QR Code da palete não fornecido.'}), 400

        # Extrair ID do Trabalhador
        try:
            trabalhador_id = int(trabalhador_info.split(';')[0].replace('ID', '').strip())
        except (IndexError, ValueError):
            return jsonify({'message': 'QR Code do trabalhador inválido.'}), 400

        # Validar Trabalhador
        trabalhador = Trabalhador.query.get(trabalhador_id)
        if not trabalhador:
            return jsonify({'message': f'Trabalhador com ID {trabalhador_id} não encontrado.'}), 404

        # Extrair ID da Palete
        try:
            palete_id = int(palete_info.split(';')[0].replace('ID', '').strip())
        except (IndexError, ValueError):
            return jsonify({'message': 'QR Code da palete inválido.'}), 400

        # Validar Palete
        palete = Palete.query.get(palete_id)
        if not palete:
            return jsonify({'message': f'Palete com ID {palete_id} não encontrada.'}), 404

        # Verificar se já há um trabalho em andamento para o trabalhador
        registro_existente = RegistroTrabalho.query.filter_by(
            trabalhador_id=trabalhador.id,
            horario_fim=None
        ).first()

        # Se houver um registro em andamento, finaliza o trabalho
        if registro_existente:
            registro_existente.horario_fim = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify({
                'registro_id': registro_existente.id,
                'trabalhador': trabalhador.nome,
                'palete': palete.nome_produto,
                'horario_inicio': registro_existente.horario_inicio,
                'horario_fim': registro_existente.horario_fim,
                'message': 'Trabalho finalizado com sucesso.'
            }), 200

        # Caso contrário, cria um novo registro para iniciar o trabalho
        novo_registro = RegistroTrabalho(
            trabalhador_id=trabalhador.id,
            palete_id=palete.id,
            horario_inicio=datetime.now(timezone.utc)
        )
        db.session.add(novo_registro)
        db.session.commit()

        return jsonify({
            'registro_id': novo_registro.id,
            'trabalhador': trabalhador.nome,
            'palete': palete.nome_produto,
            'horario_inicio': novo_registro.horario_inicio,
            'horario_fim': None,
            'message': 'Trabalho iniciado com sucesso.'
        }), 201

    except Exception as e:
        print(f"Erro ao registrar trabalho: {e}")
        db.session.rollback()
        return jsonify({'message': 'Erro ao registrar trabalho.', 'details': str(e)}), 500



@app.route('/chefes/definir_senha', methods=['POST'])
def definir_senha_chefe():
    try:
        data = request.get_json()
        id_trabalhador = data.get('id')
        nova_senha = data.get('senha')

        if not nova_senha or len(nova_senha) < 6:
            return jsonify({'message': 'A senha deve ter pelo menos 6 caracteres.'}), 400

        trabalhador = Trabalhador.query.get(id_trabalhador)
        if not trabalhador or not trabalhador.chefe:
            return jsonify({'message': 'Chefe não encontrado ou não autorizado.'}), 404

        if trabalhador.senha_hash is not None:
            return jsonify({'message': 'Senha já definida.'}), 400

        trabalhador.set_senha(nova_senha)
        db.session.commit()

        return jsonify({'message': 'Senha definida com sucesso!'}), 200
    except Exception as e:
        print(f"Erro ao definir senha: {e}")
        return jsonify({'message': 'Erro ao definir senha.', 'details': str(e)}), 500





#rota para autenticar chefe
@app.route('/chefes/login', methods=['POST'])
def login_chefe():
    try:
        data = request.get_json()
        id_trabalhador = data.get('id')
        senha = data.get('senha')

        trabalhador = Trabalhador.query.get(id_trabalhador)
        if not trabalhador or not trabalhador.chefe:
            return jsonify({'message': 'Chefe não encontrado ou não autorizado.'}), 404

        if trabalhador.senha_hash is None:
            return jsonify({'message': 'Senha não definida. Por favor, defina uma senha.'}), 400

        if not trabalhador.verificar_senha(senha):
            return jsonify({'message': 'Senha incorreta.'}), 401

        return jsonify({'message': 'Login bem-sucedido!', 'nome': trabalhador.nome, 'secao': trabalhador.secao}), 200
    except Exception as e:
        print(f"Erro ao autenticar chefe: {e}")
        return jsonify({'message': 'Erro ao autenticar chefe.', 'details': str(e)}), 500










if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)