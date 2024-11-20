from flask import Flask, request, jsonify
import mysql.connector
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import os
from flask_cors import CORS
from flask_mail import Mail, Message
import jwt
from datetime import datetime, timedelta
from functools import wraps

# Cargar variables de entorno desde el archivo .env
#load_dotenv()

# Configurar Flask
app = Flask(__name__)
CORS(app)  # Habilitar CORS para cualquier origen

# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Usando Gmail, pero puedes cambiar esto si usas otro proveedor
app.config['MAIL_PORT'] = 465  # Puerto SSL
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')  # Tu correo electrónico
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')  # Tu contraseña de correo
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')  # El remitente por defecto

mail = Mail(app)

SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'v$I~W8<P0~6e')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Token mal formateado'}), 401

        if not token:
            return jsonify({'error': 'Token no proporcionado'}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user = data['usuario']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token inválido'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/verify-token', methods=['POST'])
def verify_token():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Token no proporcionado"}), 401

        try:
            token = auth_header.split(" ")[1]
        except IndexError:
            return jsonify({"error": "Token mal formateado"}), 401

        # Decodificar el token con manejo explícito de la expiración
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            
            # Verificar expiración manualmente
            exp_timestamp = decoded.get("exp")
            if exp_timestamp:
                now = datetime.utcnow().timestamp()
                if now > exp_timestamp:
                    return jsonify({"error": "Token expirado"}), 401

            return jsonify({
                "mensaje": "Token válido",
                "usuario": decoded["usuario"]
            }), 200

        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401

    except Exception as e:
        return jsonify({"error": f"Error al verificar token: {str(e)}"}), 500


# Función para crear una nueva conexión a MySQL
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DB')
    )

# Configurar Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Función para enviar un correo de confirmación
def send_confirmation_email(correo_electronico, report_id, created_at):
    try:
        msg = Message('Confirmación de Creación de Reporte - EcoAlert',
                      recipients=[correo_electronico])
        msg.body = f"""
        Estimado/a usuario/a,

        Gracias por utilizar EcoAlert. Nos complace informarte que tu reporte ha sido creado exitosamente en nuestro sistema.

        A continuación, te proporcionamos los detalles del reporte:

        ID de Reporte: {report_id}
        Fecha de Creación: {created_at.strftime('%d/%m/%Y %H:%M:%S')}

        Nuestro equipo comenzará a revisar tu reporte a la mayor brevedad posible. Te notificaremos cualquier actualización sobre el estado del mismo.

        Si tienes alguna pregunta o necesitas más información, no dudes en ponerte en contacto con nosotros.

        Atentamente,
        El equipo de EcoAlert

        Este es un mensaje automático, por favor no respondas a este correo.
        """
        
        mail.send(msg)
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        return jsonify({'error': f'No se pudo enviar el correo: {str(e)}'}), 500


def send_state_change_email(correo_electronico, report_id):
    try:
        msg = Message('Estado de tu Reporte - EcoAlert',
                      recipients=[correo_electronico])
        msg.body = f"""
        Estimado/a usuario/a,

        Nos complace informarte que el estado de tu reporte ha sido actualizado a 'Solucionado' en nuestro sistema.

        A continuación, te proporcionamos los detalles del reporte:

        ID de Reporte: {report_id}

        Nuestro equipo ha concluido con la revisión de tu reporte y se considera Solucionado.

        Si tienes alguna pregunta o necesitas más información, no dudes en ponerte en contacto con nosotros.

        Atentamente,
        El equipo de EcoAlert

        Este es un mensaje automático, por favor no respondas a este correo.
        """
        
        mail.send(msg)
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        return jsonify({'error': f'No se pudo enviar el correo: {str(e)}'}), 500

# Ruta para crear un nuevo reporte
@app.route('/report', methods=['POST'])
def create_report():
    try:
        # Obtener datos del formulario
        description = request.form.get('description')
        address = request.form.get('address')
        localidad = request.form.get('localidad')
        barrio = request.form.get('barrio')
        correo_electronico = request.form.get('correoElectronico')

        # Validación
        if not description:
            return jsonify({'error': 'La descripción es requerida'}), 400
        if not address:
            return jsonify({'error': 'La dirección es requerida'}), 400
        if not localidad:
            return jsonify({'error': 'La localidad es requerida'}), 400
        if not barrio:
            return jsonify({'error': 'El barrio es requerido'}), 400
        if not correo_electronico:
            return jsonify({'error': 'El correo electrónico es requerido'}), 400
        if 'image' not in request.files:
            return jsonify({'error': 'Imagen es requerida'}), 400

        image_file = request.files['image']
        upload_result = cloudinary.uploader.upload(image_file)

        # Insertar datos en MySQL, con state como True por defecto
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor()
        
        sql = """
            INSERT INTO dbecoalert_sql (description, full_address, localidad, barrio, correo_electronico, image_url, created_at, state)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
        """
        values = (description, address, localidad, barrio, correo_electronico, upload_result['secure_url'], True)
        db_cursor.execute(sql, values)
        db_connection.commit()

        report_id = db_cursor.lastrowid
        
        # Obtener el valor de 'created_at' desde la base de datos
        db_cursor.execute("SELECT created_at FROM dbecoalert_sql WHERE id = %s", (report_id,))
        created_at = db_cursor.fetchone()[0]
        
        db_cursor.close()
        db_connection.close()

        # Enviar correo de confirmación
        send_confirmation_email(correo_electronico, report_id, created_at)

        # Devolver respuesta con el reporte
        report = {
            'id': report_id,
            'description': description,
            'full_address': address,
            'localidad': localidad,
            'barrio': barrio,
            'correo_electronico': correo_electronico,
            'image_url': upload_result['secure_url'],
            'created_at': created_at,
            'state': True
        }
        return jsonify({'message': 'Reporte creado correctamente', 'report': report}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para obtener todos los reportes
@app.route('/reports', methods=['GET'])
def get_reports():
    try:
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor()

        sql = "SELECT id, description, full_address, localidad, barrio, correo_electronico, image_url, created_at, state FROM dbecoalert_sql"
        db_cursor.execute(sql)
        reports = db_cursor.fetchall()
        
        results = []
        for report in reports:
            results.append({
                'id': report[0],
                'description': report[1],
                'full_address': report[2],
                'localidad': report[3],
                'barrio': report[4],
                'correo_electronico': report[5],
                'image_url': report[6],
                'created_at': report[7],
                'state': report[8]
            })
        
        db_cursor.close()
        db_connection.close()
        return jsonify(results), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para alternar el estado de un reporte
@app.route('/report/<int:report_id>/toggle_state', methods=['PUT'])
def toggle_report_state(report_id):
    try:
        db_connection = get_db_connection()
        cursor = db_connection.cursor()
        cursor.execute("SELECT * FROM dbecoalert_sql WHERE id = %s", (report_id,))
        report = cursor.fetchone()
        if not report:
            return jsonify({'error': 'Reporte no encontrado'}), 404
        
        new_state = not report[8]  # Cambiar entre True y False (suponiendo que el índice 8 es 'state')
        
        # Si el nuevo estado es False, enviar un correo al usuario
        if new_state == False:
            correo_electronico = report[5]  # Suponiendo que el índice 5 es 'correo_electronico'
            send_state_change_email(correo_electronico, report_id)
        
        cursor.execute("UPDATE dbecoalert_sql SET state = %s WHERE id = %s", (new_state, report_id))
        db_connection.commit()

        return jsonify({'message': 'Estado del reporte actualizado'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para eliminar un reporte
@app.route('/report/<int:report_id>', methods=['DELETE'])
def delete_report(report_id):
    try:
        db_connection = get_db_connection()
        cursor = db_connection.cursor()
        
        # Comprobar si el reporte existe
        sql = "SELECT * FROM dbecoalert_sql WHERE id = %s"
        cursor.execute(sql, (report_id,))
        report = cursor.fetchone()

        if report is None:
            return jsonify({'error': 'Reporte no encontrado'}), 404

        # Eliminar la imagen de Cloudinary (opcional)
        image_url = report[6]  # Suponiendo que el índice 6 es 'image_url'
        if image_url:
            public_id = image_url.split('/')[-1].split('.')[0]
            try:
                cloudinary.uploader.destroy(public_id)
            except Exception as e:
                print(f"Error al eliminar la imagen de Cloudinary: {e}")

        # Eliminar el reporte de la base de datos
        delete_sql = "DELETE FROM dbecoalert_sql WHERE id = %s"
        cursor.execute(delete_sql, (report_id,))
        db_connection.commit()

        return jsonify({'message': 'Reporte eliminado correctamente'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
# Ruta para verificar usuario y generar JWT
TOKEN_EXPIRATION_HOURS = 24

@app.route('/verificar', methods=['POST'])
def verificar_usuario():
    try:
        datos = request.json
        usuario = datos.get("usuario")
        contrasena = datos.get("contrasena")

        if not usuario or not contrasena:
            return jsonify({"error": "Usuario y contraseña son requeridos"}), 400

        db_connection = get_db_connection()
        cursor = db_connection.cursor()

        consulta = "SELECT * FROM usuarios WHERE usuario = %s AND contrasena = %s"
        cursor.execute(consulta, (usuario, contrasena))
        resultado = cursor.fetchone()

        cursor.close()
        db_connection.close()

        if resultado:
            # Crear el payload con tiempo de expiración más largo
            payload = {
                "usuario": usuario,
                "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRATION_HOURS),
                "iat": datetime.utcnow()
            }

            # Generar token
            token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

            return jsonify({
                "mensaje": "Usuario autenticado",
                "token": token,
                "usuario": usuario
            }), 200
        else:
            return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
