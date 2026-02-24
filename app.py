import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template, flash, redirect, url_for
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.secret_key = 'brh'

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / 'storage'
UPLOADS_DIR = STORAGE_DIR / 'uploads'
METADATA_DIR = STORAGE_DIR / 'metadata'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'zip'}

STORAGE_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
METADATA_DIR.mkdir(exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_date_folder():
    now = datetime.now()
    return now.strftime("%Y/%m/%d")

def save_metadata(file_info):
    metadata_file = METADATA_DIR / f"{file_info['file_id']}.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(file_info, f, ensure_ascii=False, indent=2)

def get_all_metadata():
    files = []
    for metadata_file in METADATA_DIR.glob("*.json"):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                files.append(data)
        except Exception as e:
            print(f"ошибка чтения метаданных {metadata_file}: {e}")
    
    return sorted(files, key=lambda x: x.get('upload_date', ''), reverse=True)

def get_file_category(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    categories = {
        'images': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg'],
        'documents': ['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'],
        'spreadsheets': ['xls', 'xlsx', 'csv', 'ods'],
        'archives': ['zip', 'rar', '7z', 'tar', 'gz'],
        'code': ['py', 'js', 'html', 'css', 'cpp', 'java', 'php']
    }
    
    for category, extensions in categories.items():
        if ext in extensions:
            return category
    return 'other'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload')
def upload_form():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            flash('файл не выбран', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('файл не выбран', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{original_filename}"
            
            date_path = get_date_folder()
            
            date_folder = UPLOADS_DIR / date_path
            date_folder.mkdir(parents=True, exist_ok=True)
            
            file_path = date_folder / filename
            file.save(str(file_path))
            
            file_info = {
                'file_id': str(uuid.uuid4()),
                'original_filename': original_filename,
                'filename': filename,
                'size': os.path.getsize(file_path),
                'upload_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'file_type': file.content_type,
                'storage_path': str(file_path.relative_to(BASE_DIR)),
                'date_folder': date_path
            }
            
            save_metadata(file_info)
            
            flash(f'файл {original_filename} успешно загружен!', 'success')
            return redirect(url_for('files_list'))
        else:
            flash('недопустимый тип файла', 'error')
            return redirect(request.url)
            
    except Exception as e:
        flash(f'ошибка при загрузке файла: {str(e)}', 'error')
        return redirect(request.url)

@app.route('/list')
def list_files_json():
    files = get_all_metadata()
    return jsonify(files)

@app.route('/files-list')
def files_list():
    files = get_all_metadata()
    return render_template('files.html', files=files)

@app.route('/files/<filename>')
def download_file(filename):
    try:
        metadata_list = get_all_metadata()
        file_metadata = next((f for f in metadata_list if f['filename'] == filename), None)
        
        if file_metadata:
            file_path = BASE_DIR / file_metadata['storage_path']
            if file_path.exists():
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=file_metadata['original_filename']
                )
        
        for root, dirs, files in os.walk(UPLOADS_DIR):
            if filename in files:
                file_path = os.path.join(root, filename)
                return send_file(file_path, as_attachment=True)
        
        return jsonify({'error': 'файл не найден'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stats')
def storage_stats():
    files = get_all_metadata()
    
    total_size = sum(f['size'] for f in files)
    total_files = len(files)
    
    categories = {}
    for f in files:
        cat = f.get('category', 'other')
        categories[cat] = categories.get(cat, 0) + 1
    
    return jsonify({
        'total_files': total_files,
        'total_size': total_size,
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'files_by_date': {
            'today': len([f for f in files if f['upload_date'].startswith(datetime.now().strftime("%Y-%m-%d"))]),
            'this_week': len([f for f in files if f['upload_date'] >= (datetime.now().replace(day=datetime.now().day-7)).strftime("%Y-%m-%d")])
        }
    })

@app.route('/search')
def search_files():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])
    
    files = get_all_metadata()
    results = [f for f in files if query in f['original_filename'].lower()]
    
    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)