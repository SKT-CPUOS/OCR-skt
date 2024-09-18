### 程序描述（详细见docx）
流程：通过客户端程序将windows上的文档图片上传到服务器，并自动分割识别。待服务器分割识别后，再通过客户端程序选择查看服务器上的文件夹，进行文本内容检查和分类。

config.json：配置文件

flask_http.py：服务器上的http服务器

http_test.py：windows端上的客户端程序。

requirements：linux环境依赖。windows环境见文档开头描述。

model：包含分割模型权重和识别模型，识别模型权重需要另外下载自行放入，见下面下载权重。

### 下载权重
cd model/hand-write 将下载的权重放进去

链接：https://pan.baidu.com/s/10UsQcmOyEOCTXceOhkJDtg 

提取码：xj7l 
