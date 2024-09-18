from flask import Flask, jsonify, send_file, request, abort
import os
import json
import shutil
from main_ocr import trocr_recognize, rename_images_in_folders
import threading
import traceback 

app = Flask(__name__)

with open('config.json', 'r') as file:
    config = json.load(file)

# 从JSON中提取字段
UPLOAD_FOLDER = config.get('UPLOAD_FOLDER')
RESULT_FOLDER = config.get('RESULT_FOLDER')
CLASS_FOLDER = config.get('CLASS_FOLDER')
IP_ADDRESS = config.get("IP_ADDRESS") 
PORT = config.get("PORT")
# 打印结果以确认
print("UPLOAD_FOLDER:", UPLOAD_FOLDER)
print("RESULT_FOLDER:", RESULT_FOLDER)
print("CLASS_FOLDER:", CLASS_FOLDER)
print("IP_ADDRESS", IP_ADDRESS)
print("PORT", PORT)

# os.makedirs(UPLOAD_FOLDER)
# os.makedirs(RESULT_FOLDER)
# os.makedirs(CLASS_FOLDER)


@app.route('/ocr_doc_sample/result/', defaults={'subpath': ''})
@app.route('/ocr_doc_sample/result/<path:subpath>', methods=['GET', 'PUT']) #put是修改内容
def handle_result_files(subpath):
    full_path = os.path.join(RESULT_FOLDER, subpath)
    # print('full_path', full_path)
    if request.method == 'GET':
        if os.path.isdir(full_path):
            # 列出目录中的文件和文件夹
            files = [f for f in os.listdir(full_path) if not f.startswith('.')]  # 排除隐藏文件和文件夹
            return jsonify(files)
        elif os.path.isfile(full_path):
            # 处理图片和 JSON 文件的请求
            if full_path.endswith(('.png', '.jpg', '.jpeg', '.json', '.txt')):
                return send_file(full_path)
            else:
                abort(404, description="File format not supported")
        else:
            abort(404, description="Resource not found")
    
    elif request.method == 'PUT':
        if full_path.endswith('.json') or full_path.endswith('.txt'):
            if full_path.endswith('.json'):
                data = request.get_json()
                if data is None:
                    abort(400, description="Invalid JSON data")
                with open(full_path, 'w', encoding='utf-8') as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
            else:
                data = request.data.decode('utf-8')
                with open(full_path, 'w', encoding='utf-8') as file:
                    file.write(data)
            return jsonify({"message": "File saved successfully"}), 200
        else:
            abort(400, description="Unsupported file type")

@app.route('/source_doc/<path:subpath>', methods=['GET'])
def handle_doc_files(subpath):
    full_path = os.path.join(UPLOAD_FOLDER, subpath)
    print('full_path_handle_doc', full_path)
    if os.path.isfile(full_path):
        # 处理 /doc 下的文件请求
        if full_path.endswith(('.png', '.jpg', '.jpeg')):
            return send_file(full_path)
        else:
            abort(404, description="File format not supported")
    else:
        abort(404, description="Resource not found")

@app.route('/ocr_doc_sample/move_image', methods=['POST'])
def move_image():
    try:
        data = request.json
        source_image_path = data['source_image_path']
        source_json_path = data.get('source_json_path')
        source_txt_path = data.get('source_txt_path')
        target_folder = data['target_folder']

        # 获取配置文件中的基础路径
        base_dir = RESULT_FOLDER
        # 确定完整的源路径和目标路径
        full_source_image_path = source_image_path
        full_target_folder = target_folder

    
        # 创建目标文件夹及其子文件夹（如果不存在）
        os.makedirs(full_target_folder, exist_ok=True)
        print('full_target_folder', full_target_folder)

        # 移动图片文件
        target_image_path = os.path.join(full_target_folder, os.path.basename(full_source_image_path))
        shutil.move(full_source_image_path, target_image_path)
        app.logger.debug(f"Image moved to {target_image_path}")

        # 移动 JSON 文件
        if source_json_path:
            full_source_json_path = source_json_path
            if os.path.exists(full_source_json_path):
                target_json_path = os.path.join(full_target_folder, os.path.basename(full_source_json_path))
                shutil.move(full_source_json_path, target_json_path)
                app.logger.debug(f"JSON moved to {target_json_path}")

        # 移动 TXT 文件
        if source_txt_path:
            full_source_txt_path = source_txt_path
            if os.path.exists(full_source_txt_path):
                target_txt_path = os.path.join(full_target_folder, os.path.basename(full_source_txt_path))
                shutil.move(full_source_txt_path, target_txt_path)
                app.logger.debug(f"TXT moved to {target_txt_path}")

        return jsonify({"message": "Files moved successfully"}), 200
    except Exception as e:
        app.logger.error(f"Error occurred: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/ocr_doc_sample/result/dataset_addarea/<path:filename>', methods=['PUT'])
def save_area_image(filename):
    try:
        # 构建目标路径
        target_folder = os.path.join(RESULT_FOLDER, 'dataset_addarea')
        os.makedirs(target_folder, exist_ok=True)
        full_path = os.path.join(target_folder, filename)
        # print('full path', full_path)
        # 接收并保存文件
        file_data = request.data
        # print('file_Data', file_data)
        if not file_data:
            abort(400, description="No file data received")
        # 根据文件扩展名处理不同类型的文件
        # json文件以二进制写入的话默认unicode编码，中文变成转义字符，txt似乎两种都一样
        if filename.endswith('.json'):
            json_data = json.loads(file_data.decode('utf-8'))
            with open(full_path, 'w', encoding='utf-8') as file:
                json.dump(json_data, file, ensure_ascii=False, indent=4)
        else:
            # 文本文件需要先解码
            with open(full_path, 'wb') as file:
                            file.write(file_data)

        return jsonify({"message": "File uploaded successfully"}), 200
    except Exception as e:
        app.logger.error(f"Error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/run_ocr', methods=['POST'])
def run_ocr():
    # 从请求中获取图片目录路径
    data = request.json
    image_dir = data.get('image_dir')
    if not image_dir or not os.path.exists(image_dir):
        print("Invalid image directory")
        return jsonify({"error": "Invalid image directory"}), 400

    # 调用 trocr_recognize 方法
    result = trocr_recognize(image_dir)
    
    return jsonify({"result": result})

@app.route('/ocr_doc_sample/result/<folder_name>/<filename>', methods=['DELETE'])
def delete_file(folder_name, filename):
    file_path = os.path.join(RESULT_FOLDER, folder_name, filename)
    print('delete file path', file_path)
    txt_path = file_path.replace('.png', '.txt')
    json_path = file_path.replace('.png', '.json')
    if os.path.exists(file_path):
        os.remove(file_path)
        os.remove(txt_path)
        os.remove(json_path)
        return jsonify({"message": "File deleted successfully"}), 200
    else:
        return jsonify({"error": "File not found"}), 404

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    # 获取文件夹路径
    path = request.form.get('path', '')
    save_path = os.path.join(UPLOAD_FOLDER, path)
    os.makedirs(save_path, exist_ok=True)

    # 保存文件
    file.save(os.path.join(save_path, file.filename))

    # start_rename_thread(save_path)
    return jsonify({'message': 'File uploaded successfully'}), 200

@app.route('/rename', methods=['POST'])
def rename_files():
    folder_path = request.form.get('folder_path')
    print('rename folder_path is ', folder_path)
    if not folder_path:
        return jsonify({'message': 'No folder path provided'}), 400
    
    # 启动重命名线程
    start_rename_thread(folder_path)

    return jsonify({'message': f'Rename operation started for {folder_path}'}), 200

def start_rename_thread(doc_folder):
    rename_thread = threading.Thread(target=rename_images_in_folders, args=(doc_folder,))
    rename_thread.start()

if __name__ == '__main__':
    app.run(host=IP_ADDRESS, port=PORT, debug=False)  #端口
