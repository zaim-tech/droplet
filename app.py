import os
import uuid
import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_path, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jwt

app = Flask(__name__)

# --- Configurations ---
VAULT_DIR = os.path.join(os.getcwd(), 'cloud_vault')
os.makedirs(VAULT_DIR, exist_ok=True)

app.config['UPLOAD_FOLDER'] = VAULT_DIR
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cloud_service.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'super-secret-zaim-tech-key-change-this-in-production'

db = SQLAlchemy(app)

# --- Database Models ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class Folder(db.Model):
    __tablename__ = 'folders'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.String(36), db.ForeignKey('folders.id'), nullable=True)

class FileMetadata(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_name = db.Column(db.String(255), nullable=False)
    secure_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    folder_id = db.Column(db.String(36), db.ForeignKey('folders.id'), nullable=True)

with app.app_context():
    db.create_all()

# --- Authentication Decorator ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({"error": "Token is missing!"}), 401
        try:
            # Expecting format: "Bearer <token>"
            actual_token = token.split(" ")[1] if " " in token else token
            data = jwt.decode(actual_token, app.config['SECRET_KEY'], algorithms=["HS256"])
            g.current_user = User.query.filter_by(id=data['user_id']).first()
            if not g.current_user:
                return jsonify({"error": "User invalid"}), 401
        except Exception as e:
            return jsonify({"error": "Token is invalid or expired!"}), 401
        return f(*args, **kwargs)
    return decorated

# --- Routes ---

@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400
        
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400
        
    hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
    new_user = User(username=username, password_hash=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully"}), 201

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid username or password"}), 401
        
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")
    
    return jsonify({"token": token, "username": user.username}), 200

@app.route('/folders', methods=['POST'])
@token_required
def create_folder():
    data = request.get_json() or {}
    folder_name = data.get('name')
    parent_id = data.get('parent_id') # Can be null for root
    
    if not folder_name:
        return jsonify({"error": "Folder name required"}), 400
        
    new_folder = Folder(name=folder_name, user_id=g.current_user.id, parent_id=parent_id)
    db.session.add(new_folder)
    db.session.commit()
    return jsonify({"message": "Folder created", "id": new_folder.id}), 201

@app.route('/explorer', methods=['GET'])
@token_required
def explorer():
    # If folder_id parameter is completely missing or empty, it means we are in the Root directory
    current_folder_id = request.args.get('folder_id')
    if current_folder_id == "null" or current_folder_id == "":
        current_folder_id = None

    # Fetch items strictly owned by the verified token user
    folders = Folder.query.filter_by(user_id=g.current_user.id, parent_id=current_folder_id).all()
    files = FileMetadata.query.filter_by(user_id=g.current_user.id, folder_id=current_folder_id).all()
    
    return jsonify({
        "current_folder_id": current_folder_id,
        "folders": [{"id": f.id, "name": f.name} for f in folders],
        "files": [{"id": fl.id, "name": fl.original_name, "size": fl.file_size} for fl in files]
    }), 200

@app.route('/upload', methods=['POST'])
@token_required
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file stream payload found"}), 400
    
    file = request.files['file']
    folder_id = request.form.get('folder_id')
    if folder_id == "null" or folder_id == "":
        folder_id = None
        
    if file.filename == '':
        return jsonify({"error": "Empty selection filename"}), 400

    orig_name = file.filename
    cleaned_name = secure_filename(orig_name)
    
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(cleaned_name)[1]
    unique_storage_name = f"{file_id}{file_ext}"
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_storage_name)
    file.save(file_path)
    
    meta = FileMetadata(
        id=file_id,
        original_name=orig_name,
        secure_name=unique_storage_name,
        file_size=os.path.getsize(file_path),
        user_id=g.current_user.id,
        folder_id=folder_id
    )
    db.session.add(meta)
    db.session.commit()
    
    return jsonify({"message": "File written safely", "id": file_id}), 201

@app.route('/download/<file_id>', methods=['GET'])
@token_required
def download(file_id):
    # Enforce strictly user isolated queries to block unauthorized access drops
    file_record = FileMetadata.query.filter_by(id=file_id, user_id=g.current_user.id).first()
    if not file_record:
        return jsonify({"error": "Resource unavailable or denied"}), 404
        
    return send_from_path(
        app.config['UPLOAD_FOLDER'], 
        file_record.secure_name, 
        as_attachment=True, 
        download_name=file_record.original_name
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)