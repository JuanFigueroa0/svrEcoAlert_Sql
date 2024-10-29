from flask import Flask, request, jsonify
import mysql.connector
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import os
from flask_cors import CORS

# Cargar variables de entorno desde el archivo .env
load_dotenv(dotenv_path="/Juan Figueroa/Descargas 2/EcoAlert/ecoalert/lib/bd.env")

# Configurar Flask
app = Flask(__name__)
CORS(app, resources={r"/report": {"origins": "*"}})  # Habilitar CORS para cualquier origen

# Configurar conexión a MySQL
db_connection = mysql.connector.connect(
    host=os.getenv('MYSQL_HOST'),
    user=os.getenv('MYSQL_USER'),
    password=os.getenv('MYSQL_PASSWORD'),
    database=os.getenv('MYSQL_DB')
)
db_cursor = db_connection.cursor(dictionary=True)

# Configurar Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Ruta para crear un nuevo reporte
@app.route('/report', methods=['POST'])
def create_report():
    try:
        # Mostrar logs para ver qué se está recibiendo desde el cliente
        print("Datos recibidos:", request.form)
        print("Archivos recibidos:", request.files)

        # Obtener la descripción desde el formulario
        description = request.form.get('description')
        if not description:
            return jsonify({'error': 'La descripción es requerida'}), 400

        # Obtener los datos de la dirección desde el formulario
        address = request.form.get('address')  # Dirección completa enviada por el frontend
        if not address:
            return jsonify({'error': 'La dirección es requerida'}), 400

        # Obtener la localidad, barrio y correo electrónico
        localidad = request.form.get('localidad')
        barrio = request.form.get('barrio')
        correo_electronico = request.form.get('correoElectronico')

        # Validar los nuevos campos
        if not localidad:
            return jsonify({'error': 'La localidad es requerida'}), 400
        if not barrio:
            return jsonify({'error': 'El barrio es requerido'}), 400
        if not correo_electronico:
            return jsonify({'error': 'El correo electrónico es requerido'}), 400

        # Subir la imagen a Cloudinary
        if 'image' not in request.files:
            return jsonify({'error': 'Imagen es requerida'}), 400

        image_file = request.files['image']
        try:
            upload_result = cloudinary.uploader.upload(image_file)
        except Exception as e:
            return jsonify({'error': f'Error al subir la imagen a Cloudinary: {e}'}), 500

        # Insertar los datos en MySQL
        sql = """
            INSERT INTO dbecoalert_sql (description, full_address, localidad, barrio, correo_electronico, image_url, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (description, address, localidad, barrio, correo_electronico, upload_result['secure_url'], upload_result['created_at'])

        db_cursor.execute(sql, values)
        db_connection.commit()
        
        report_id = db_cursor.lastrowid  # Obtener el ID generado automáticamente

        report = {
            'id': report_id,
            'description': description,
            'full_address': address,
            'localidad': localidad,
            'barrio': barrio,
            'correo_electronico': correo_electronico,
            'image_url': upload_result['secure_url'],
            'created_at': upload_result['created_at']
        }

        return jsonify({'message': 'Reporte creado correctamente', 'report': report}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para obtener todos los reportes
@app.route('/reports', methods=['GET'])
def get_reports():
    try:
        sql = "SELECT id, description, image_url, created_at, full_address, localidad, barrio, correo_electronico FROM dbecoalert_sql"
        db_cursor.execute(sql)
        reports = db_cursor.fetchall()
        
        return jsonify(reports), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
