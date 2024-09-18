import os
from PIL import Image
from craft_text_detector import (
    read_image,
    load_craftnet_model,
    load_refinenet_model,
    get_prediction,
    export_detected_regions,
    export_extra_results,
    empty_cuda_cache
)
import shutil
import cv2
from natsort import natsorted
import json
import argparse
from transformers import TrOCRProcessor, VisionEncoderDecoderModel, BertTokenizer
from model.dataset import decode_text
import torch
import torch.nn.functional as F
import sys
from datetime import datetime


UPLOAD_FOLDER = '/mnt/zt/doc_upload'
RESULT_FOLDER = '/mnt/zt/doc_result'

with open('config.json', 'r') as file:
    config = json.load(file)

# 从JSON中提取字段
UPLOAD_FOLDER = config.get('UPLOAD_FOLDER')
RESULT_FOLDER = config.get('RESULT_FOLDER')
# split_by_people_num = config.get('split_by_people_num')


# 预先加载模型到内存
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = VisionEncoderDecoderModel.from_pretrained('./model/hand-write')
processor = TrOCRProcessor.from_pretrained('./model/hand-write')
model = model.to(device)

refine_net = load_refinenet_model(cuda=True, weight_path='./model/craft_model/craft_refiner_CTW1500.pth')
craft_net = load_craftnet_model(cuda=True, weight_path='./model/craft_model/craft_mlt_25k.pth')


def rename_images_in_folders(doc_folder):
    # 获取主文件夹内的所有子文件夹
    print(doc_folder)
    subfolders = [f.path for f in os.scandir(doc_folder) if f.is_dir()]
    print(subfolders)
    if not os.path.exists(f"{RESULT_FOLDER}"):
        os.makedirs(f"{RESULT_FOLDER}")
        
    folder_count = 1
    dataset_index = 0
    
    for folder_index, folder in enumerate(natsorted(subfolders), start=1):
        folder_name = os.path.basename(folder)   

        # 检查文件夹内是否存在处理标记文件
        processed_flag = os.path.join(folder, '.processed')
        if os.path.exists(processed_flag):
            print(f"Skipping already processed folder: {folder_name}")
            continue

        print(f"Processing folder: {folder_name}")

        # 获取子文件夹内的所有图片文件
        images = [f for f in os.listdir(folder) if f.endswith(('.png', '.jpg', '.jpeg'))]
        
        for image_index, image_name in enumerate(natsorted(images), start=1):
            image_path = os.path.join(folder, image_name)
            print("image_path :", image_path)
            # 生成新的文件名
            new_image_name = f"{folder_name}_image_{folder_index}_{image_index}"
            new_image_path = f"{RESULT_FOLDER}/dataset_batch_{folder_name}_{folder_count}"
            # print(new_image_path)
            if not os.path.exists(new_image_path):
                os.makedirs(new_image_path)


            detect_text(image_path)
            #读取坐标文件
            coordinates_file = './outputs/image_text_detection.txt'
            coordinates = []
            with open(coordinates_file, 'r') as f:
                coordinates = f.readlines()

            for crop_index, cropname in enumerate(natsorted(os.listdir('./outputs/image_crops'))):
                if cropname.endswith(('.png', '.jpg', '.jpeg')):
                    source_crop_path = os.path.join('./outputs/image_crops', cropname)
                    new_cropname_prefix = f"{folder_name}_image_{folder_index}_{image_index}_{crop_index}"
                    new_cropname = f"{folder_name}_image_{folder_index}_{image_index}_{crop_index}.png"
                    dest_crop_path = os.path.join(new_image_path, new_cropname)
                    shutil.move(source_crop_path, dest_crop_path)
                    if crop_index < len(coordinates):
                        coordinate_data = coordinates[crop_index].strip()

                        # 创建JSON文件并保存坐标信息
                        source_image_path = os.path.join(folder, image_name)
                        json_data = {
                            "source_image_path": os.path.abspath(source_image_path),
                            "coordinates": coordinate_data,
                            "content": ""
                        }
                        json_filename = os.path.join(new_image_path, f"{new_cropname_prefix}.json")
                        with open(json_filename, 'w') as json_file:
                            json.dump(json_data, json_file, indent=4)
        # 处理完成后创建标记文件
        with open(processed_flag, 'w') as flag_file:
            flag_file.write('This folder has been processed.\n')
        cur_dir = f'{RESULT_FOLDER}/dataset_batch_{folder_name}_{folder_count}'
        trocr_recognize(cur_dir)                
        folder_count += 1
        # 处理完成后重命名文件夹，添加后缀
        # processed_folder_name = f"{folder}_processed"
        # os.rename(folder, processed_folder_name)
        # print(f"Renamed folder to {processed_folder_name}")

    # trocr_recognize(f'{RESULT_FOLDER}/dataset_batch_last_{timestamp}')

                    



def detect_text(image_path, output_dir='outputs/'):
    #清空output文件夹，避免有残留
    try:
        shutil.rmtree(output_dir)
        # print(f"文件夹 '{output_dir}' 已清空。")
    except OSError as e:
        print(f"删除文件夹 '{output_dir}' 时发生错误：{e}")

    # read image
    image = read_image(image_path)
    if image is None:
        print("failed to read image")
        return 

    # 下面是将图片二值化
    # _, image = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)

    # load models
    # refine_net = load_refinenet_model(cuda=True)
    # craft_net = load_craftnet_model(cuda=True)

    # perform prediction
    prediction_result = get_prediction(
        image=image,
        craft_net=craft_net,
        refine_net=refine_net,
        text_threshold=0.7,
        link_threshold=0.4,
        low_text=0.4,
        cuda=True,
        long_size=1280
    )

    # export detected text regions
    exported_file_paths = export_detected_regions(
        image=image,
        regions=prediction_result["boxes"],
        output_dir=output_dir,
        rectify=True
    )

    # export heatmap, detection points, box visualization
    export_extra_results(
        image=image,
        regions=prediction_result["boxes"],
        heatmaps=prediction_result["heatmaps"],
        output_dir=output_dir
    )

    # unload models from gpu
    # empty_cuda_cache()

def trocr_recognize(image_dir):
    # device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # processor = TrOCRProcessor.from_pretrained('./model/hand-write')
    vocab = processor.tokenizer.get_vocab() #从processor中获取词汇表
    vocab_inp = {vocab[key]: key for key in vocab}
    # model = VisionEncoderDecoderModel.from_pretrained('./model/hand-write')
    # model = model.to(device)
    model.eval()
    model.config.decoder_start_token_id = processor.tokenizer.cls_token_id
    model.config.pad_token_id = processor.tokenizer.pad_token_id
    model.config.vocab_size = model.config.decoder.vocab_size
    model.config.eos_token_id = processor.tokenizer.sep_token_id
    model.config.max_length = 100        #单句长度限制
    model.config.early_stopping = True  
    model.config.num_beams = 2

    for image_name in os.listdir(image_dir):
        txt_name = os.path.splitext(image_name)[0] + '.txt'
        if image_name.endswith('.png') and not os.path.exists(txt_name):
            image_path = os.path.join(image_dir, image_name)
            img = Image.open(image_path).convert('RGB')
            pixel_values = processor([img], return_tensors="pt").pixel_values   #保存为pytorch张量
            pixel_values = pixel_values.to(device)  #将数据放到GPU上
            with torch.no_grad():
                generated_ids = model.generate(pixel_values[:, :, :].cuda())
            generated_text = decode_text(generated_ids[0].cpu().numpy(), vocab, vocab_inp)
            txt_filename = os.path.splitext(image_name)[0] + '.txt'
            txt_path = os.path.join(image_dir, txt_filename)
            with open(txt_path, 'w') as txt_file:
                txt_file.write(generated_text)

            json_filename = os.path.splitext(image_name)[0] + '.json'
            json_filepath = os.path.join(image_dir, json_filename)
            if os.path.exists(json_filepath):
                with open(json_filepath, 'r+') as json_file:
                    content = json_file.read()
                    json_file.seek(0)
                    try:
                        data = json.load(json_file)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON: {e}")
                        return
                    data['content'] = generated_text
                    json_file.seek(0)
                    json.dump(data, json_file, ensure_ascii=False, indent=4)
                    json_file.truncate()
            else:
                print(f"Warning: JSON file {json_filename} not found.")
    
    print('完成一批档案识别\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='trocr detection')
    parser.add_argument('--doc_path', default=f"{UPLOAD_FOLDER}", type=str, help="document main folder path")
    args = parser.parse_args()

    doc_folder = args.doc_path  # 主文件夹路径，替换为你的文件夹路径
    rename_images_in_folders(doc_folder)
    empty_cuda_cache()