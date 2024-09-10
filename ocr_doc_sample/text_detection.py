# import craft functions
from craft_text_detector import (
    read_image,
    load_craftnet_model,
    load_refinenet_model,
    get_prediction,
    export_detected_regions,
    export_extra_results,
    empty_cuda_cache
)
import os
import shutil
import cv2


# set image path and export folder directory
# image = './figures/Image_00023.jpg' # can be filepath, PIL image or numpy array
# output_dir = 'outputs/'

def detect_text(image_path, output_dir='outputs/'):
    #清空output文件夹，避免有残留
    try:
        shutil.rmtree(output_dir)
        print(f"文件夹 '{output_dir}' 已清空。")
    except FileNotFoundError:
        print(f"文件夹 '{output_dir}' 不存在,自动创建")
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
    refine_net = load_refinenet_model(cuda=True)
    craft_net = load_craftnet_model(cuda=True)

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
    empty_cuda_cache()