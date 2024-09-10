from flask import Flask, jsonify, send_file, request, abort
import os
import json
import shutil
from main_ocr import trocr_recognize

app = Flask(__name__)

BASE_DIR = '/mnt/zt/ocr_doc_sample' #需要修改

@app.route('/ocr_doc_sample/result/', defaults={'subpath': ''})
@app.route('/ocr_doc_sample/result/<path:subpath>', methods=['GET', 'PUT'])
def handle_result_files(subpath):
    full_path = os.path.join(BASE_DIR, 'result', subpath)
    
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

@app.route('/ocr_doc_sample/doc/<path:subpath>', methods=['GET'])
def handle_doc_files(subpath):
    full_path = os.path.join(BASE_DIR, 'doc', subpath)
    
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
        if target_folder.startswith('ocr_doc_sample'):
            target_folder = target_folder.replace('ocr_doc_sample/', '')
        # 确定完整的源路径和目标路径
        base_dir = "/mnt/zt/ocr_doc_sample"
        full_source_image_path = os.path.join(base_dir, source_image_path.replace('/ocr_doc_sample/', ''))
        full_target_folder = os.path.join(base_dir, target_folder)

    
        # 创建目标文件夹及其子文件夹（如果不存在）
        os.makedirs(full_target_folder, exist_ok=True)

        # 移动图片文件
        target_image_path = os.path.join(full_target_folder, os.path.basename(full_source_image_path))
        shutil.move(full_source_image_path, target_image_path)
        app.logger.debug(f"Image moved to {target_image_path}")

        # 移动 JSON 文件
        if source_json_path:
            full_source_json_path = os.path.join(base_dir, source_json_path.replace('/ocr_doc_sample/', ''))
            if os.path.exists(full_source_json_path):
                target_json_path = os.path.join(full_target_folder, os.path.basename(full_source_json_path))
                shutil.move(full_source_json_path, target_json_path)
                app.logger.debug(f"JSON moved to {target_json_path}")

        # 移动 TXT 文件
        if source_txt_path:
            full_source_txt_path = os.path.join(base_dir, source_txt_path.replace('/ocr_doc_sample/', ''))
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
        target_folder = os.path.join(BASE_DIR, 'result/dataset_addarea')
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
    file_path = os.path.join('./result/', folder_name, filename)
    txt_path = file_path.replace('.png', '.txt')
    json_path = file_path.replace('.png', '.json')
    if os.path.exists(file_path):
        os.remove(file_path)
        os.remove(txt_path)
        os.remove(json_path)
        return jsonify({"message": "File deleted successfully"}), 200
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8099, debug=True)  #端口
