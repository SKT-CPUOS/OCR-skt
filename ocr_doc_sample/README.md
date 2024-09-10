# 文档标注小程序

## 环境要求

python版本：3.8 (linux和windows)

CUDA版本：建议10.2

其他依赖：见requirement.txt

## 程序及目录描述（详细见Details.docx文档）

### 文件夹目录classify_dataset用途：分类后的路径，包括手写、印刷、数字

### 原始图像目录doc：把要处理的图像的文件夹复制到doc下，按照每个人一个文件夹，文件夹内是图片

### 结果存放目录result：分割识别后的输出，结果包含图片、json文件（内容+坐标，坐标顺序是左上，右上，右下，左下）和txt文本。

### 服务器监听程序flask_http.py：服务器启动，修改BASE_DIR和监听端口

### 客户端程序http_test.py：是windows下的图形化应用， 同样修改BASE_DIR和监听端口

### 分割识别程序main_ocr.py： 第一次运行会自动下载权重，确保服务器联网（在当前用户home目录下的.craft_text_detector/weights）

## 权重下载

cd ./model/hand-write

下载权重链接：https://pan.baidu.com/s/10UsQcmOyEOCTXceOhkJDtg?pwd=xj7l 提取码：xj7l

