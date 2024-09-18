import os
import tkinter as tk
from tkinter import filedialog, Listbox, Scrollbar, Label, simpledialog, Toplevel, messagebox, Menu, Canvas, font, Radiobutton
from PIL import Image, ImageTk, ImageDraw, ImageOps
import json
import requests
from io import BytesIO
from bs4 import BeautifulSoup
import shutil
from datetime import datetime
from natsort import natsorted
from threading import Thread
import threading

BASE_DIR = '/mnt/zt/ocr_doc_sample'     #跟http服务器的一样
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

class RemoteImageViewerApp:
    def __init__(self, root, server_url):
        self.root = root
        self.root.title("Remote Image Viewer")
        self.server_url = server_url  # Linux 服务器的 URL
        self.current_folder = ""
        self.image_list = []
        self.current_image_index = 0
        self.current_image_name = None
        self.current_image_basename = None
        self.source_image_path = ""
        self.source_image = None
        self.original_source_image = None
        self.source_image_width = None
        self.source_image_height = None
        self.display_image_width = None
        self.display_image_height = None
        self.image_cache = {}  # 创建一个缓存字典
        self.current_source_image_path = None
        self.rectangles_info = []
        self.json_cache = {}  # 用于缓存JSON数据
        self.global_row_idx = 0
        self.last_image_source_path = None

        # 获取屏幕的宽度和高度
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        window_width = int(screen_width * 0.9)
        window_height = int(screen_height * 0.9)
        self.window_width = window_width
        self.window_height = window_height
        self.root.geometry(f"{window_width}x{window_height}")
        self.center_window(window_width, window_height)
        self.root.resizable(False, False)
        self.center_window(window_width, window_height)
        self.root.title("Remote Image Viewer")

        self.create_widgets()

        # 绑定鼠标滚轮和键盘左右键事件
        self.root.bind("<Left>", self.show_prev_image)  # 绑定左箭头键
        self.root.bind("<Right>", self.show_next_image)  # 绑定右箭头键
        # self.root.bind("<MouseWheel>", self.on_mouse_wheel)  # 绑定鼠标滚轮

        self.region_start = None
        self.region_end = None
        self.selected_region = None  

    def center_window(self, width, height):
        # 获取屏幕的宽度和高度
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # 计算窗口左上角的 x 和 y 坐标，使其居中
        x = int((screen_width - width) / 2)
        y = int((screen_height - height) / 2)

        # 设置窗口的位置和大小
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):

        main_frame = tk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")

        # 主框架分为两列，左侧和右侧区域
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # 左侧区域
        left_frame = tk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsew")

        # 上传文件夹按钮
        upload_button = tk.Button(left_frame, text="选择本地文件夹并上传", command=self.select_folder)
        upload_button.grid(row=0, column=0, pady=10)

        # 选择服务器文件夹按钮
        self.select_button = tk.Button(left_frame, text="选择服务器文件夹查看", command=self.open_folder_selection)
        self.select_button.grid(row=1, column=0, pady=10)
 
        # 显示左侧图片的标签
        self.left_image_label = tk.Label(left_frame, text="左侧图片区域", anchor="center", bd=0, highlightthickness=0)
        self.left_image_label.grid(row=2, column=0, padx=0, pady=0, sticky="nsew")

        # self.left_image_label.bind("<Button-3>", self.on_source_right_click)
        # 选择区域按钮
        self.select_region_button = tk.Button(left_frame, text="选择区域", command=self.start_region_selection)
        self.select_region_button.grid(row=3, column=0, pady=10)

        # 右侧区域
        right_frame = tk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew")

        # 显示右侧图片的标签
        self.right_image_label = tk.Label(right_frame, text="右侧图片区域", anchor="center")
        self.right_image_label.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        # 确保 right_image_label 充满剩余的空间
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=0)  # 保存按钮不占用多余空间
        right_frame.grid_rowconfigure(2, weight=0)  # 导航按钮不占用多余空间
        right_frame.grid_rowconfigure(3, weight=0)  # 图片编号标签不占用多余空间
        right_frame.grid_columnconfigure(0, weight=1, minsize=400)

        # right_frame.grid_propagate(False)

        # 创建一个Canvas用于实现可滚动区域
        canvas = tk.Canvas(right_frame)
        canvas.grid(row=1, column=0, sticky="nsew")

        # 创建一个垂直滚动条，绑定到Canvas上
        scrollbar = tk.Scrollbar(right_frame, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 创建一个Frame放在Canvas里面，用于显示多个内容
        self.scrollable_frame = tk.Frame(canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        # self.scrollable_frame.config(height=400)
        # canvas.config(width=400)  # 400 是一个示例值，根据需要调整
        # 将scrollable_frame放在Canvas上
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # 为右键点击右侧图片绑定事件
        self.right_image_label.bind("<Button-3>", self.show_delete_menu)


        # 放置导航按钮
        buttons_frame = tk.Frame(right_frame)
        buttons_frame.grid(row=2, column=0, pady=5)

        self.prev_button = tk.Button(buttons_frame, text="上一张", command=self.show_prev_image)
        self.prev_button.pack(side=tk.LEFT, padx=5)

        self.next_button = tk.Button(buttons_frame, text="下一张", command=self.show_next_image)
        self.next_button.pack(side=tk.LEFT, padx=5)

        self.save_button = tk.Button(buttons_frame, text="保存修改", command=self.save_current_content)
        self.save_button.pack(side=tk.LEFT, padx=5)

        # 显示当前图片编号的标签
        self.image_index_label = tk.Label(right_frame, text="第 1 张")
        self.image_index_label.grid(row=2, column=0, pady=5, sticky="e")

        # 配置grid布局的权重，使组件随窗口大小变化
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=3)
        left_frame.grid_rowconfigure(2, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)


    def on_mouse_wheel(self, event):
        if event.delta > 0:  # 滚轮向上滚动
            self.show_prev_image()
        elif event.delta < 0:  # 滚轮向下滚动
            self.show_next_image()

    def open_folder_selection(self):
        # Create a new window for folder selection
        folder_window = Toplevel(self.root)
        folder_window.title("选择文件夹")


        # Calculate the position to center the new window on the main window
        self.root.update_idletasks()  # Ensure the main window is updated
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (folder_window.winfo_reqwidth() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (folder_window.winfo_reqheight() // 2)
        folder_window.geometry(f"+{x}+{y}")

        # Listbox to display available folders
        folder_listbox = Listbox(folder_window, width=50)
        folder_listbox.pack(side=tk.LEFT, padx=10, pady=10)
        folder_listbox.bind('<<ListboxSelect>>', lambda event: self.on_folder_select(event, folder_listbox, folder_window))

        # Add a scrollbar to the folder listbox
        folder_scrollbar = Scrollbar(folder_window, orient=tk.VERTICAL)
        folder_scrollbar.config(command=folder_listbox.yview)
        folder_scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        folder_listbox.config(yscrollcommand=folder_scrollbar.set)

        # Load available folders into the listbox
        self.load_folders(folder_listbox)

    def load_folders(self, listbox):
        result_url = f"{self.server_url}/ocr_doc_sample/result/"
        response = requests.get(result_url)
        if response.status_code == 200:
            folders = response.json()
            for folder in folders:
                if not folder.startswith('.'):  # 排除隐藏文件和文件夹
                    listbox.insert(tk.END, folder)
        else:
            messagebox.showerror("错误", f"无法加载文件夹列表：{response.status_code}")

    def on_folder_select(self, event, listbox, window):
        # Get the selected folder name and close the selection window
        self.current_folder = listbox.get(listbox.curselection())
        window.destroy()
        #     # 清理所有缓存
        # self.json_cache.clear()
        # self.image_cache.clear()
        # self.rectangles_info.clear()
        if self.current_folder:
            self.load_images()
            self.show_image(0)  # 默认显示第一张图片

    def load_images(self):
        folder_url = f"{self.server_url}/ocr_doc_sample/result/{self.current_folder}/"
        response = requests.get(folder_url)
        if response.status_code == 200:
            self.image_list = natsorted([f for f in response.json() if f.endswith(('.png', '.jpg', '.jpeg'))])
        else:
            messagebox.showerror("错误", f"无法加载图片列表：{response.status_code}")

    def find_previous_image_index(self, current_index):
        """
        通过文件名的前两个数字，找到上一张图片的索引。
        当前两个数字不同（如 `1_1` 和 `1_2`）时，返回上一张图片的索引。
        """
        if current_index <= 0:
            return len(self.image_list) - 1  # 如果已经是第一张图片，返回最后一张图片的索引

        # 获取当前图片的前两个数字 (1_1)
        current_image_name = self.image_list[current_index]
        current_parts = current_image_name.split("_")
        current_first_two_numbers = f"{current_parts[2]}_{current_parts[3]}"

        # 从当前索引向前搜索
        for i in range(current_index - 1, -1, -1):
            image_name = self.image_list[i]
            parts = image_name.split("_")
            first_two_numbers = f"{parts[2]}_{parts[3]}"
            
            # 当前两个数字不同时，返回该索引
            if first_two_numbers != current_first_two_numbers:
                return i

        # 如果没有找到，返回最后一张图片的索引
        return len(self.image_list) - 1

    def find_next_image_index(self, current_index):
        """
        通过文件名的前两个数字，找到下一张图片的索引。
        当前两个数字不同（如 `1_1` 和 `1_2`）时，返回下一张图片的索引。
        """
        if current_index >= len(self.image_list) - 1:
            return 0  # 如果已经是最后一张图片，返回第一张图片的索引

        # 获取当前图片的前两个数字 (1_1)
        current_image_name = self.image_list[current_index]
        current_parts = current_image_name.split("_")
        current_first_two_numbers = f"{current_parts[2]}_{current_parts[3]}"

        # 从当前索引向后搜索
        for i in range(current_index + 1, len(self.image_list)):
            image_name = self.image_list[i]
            parts = image_name.split("_")
            first_two_numbers = f"{parts[2]}_{parts[3]}"

            # 当前两个数字不同时，返回该索引
            if first_two_numbers != current_first_two_numbers:
                return i

        # 如果没有找到，返回第一张图片的索引
        return 0

    def show_image(self, index):
        # 清空矩形框缓存
        self.rectangles_info.clear()
        
        # 清空并重新初始化与当前图片相关的变量
        self.current_image_index = index
        self.current_image_name = None
        self.current_image_basename = None
        if 0 <= index < len(self.image_list):
            image_name = self.image_list[index]
            image_url = f"{self.server_url}/ocr_doc_sample/result/{self.current_folder}/{image_name}"
            self.display_images(image_url, image_name)
            self.current_image_index = index
            current_image_base = os.path.splitext(image_name)[0]
            self.current_image_basename = current_image_base
            self.current_image_name = image_name
            self.image_index_label.config(text=f"第 {index + 1} 张 (共 {len(self.image_list)} 张)")

    def show_prev_image(self, event=None):
        self.show_image(self.find_previous_image_index(self.current_image_index))

    def show_next_image(self, event=None):
        self.show_image(self.find_next_image_index(self.current_image_index))

    def display_images(self, image_url, image_name):
        # 加载并显示右侧的图片
        response = requests.get(image_url)
        print('image url', image_url)
        if response.status_code == 200:
            img_data = BytesIO(response.content)
            img = Image.open(img_data)
            display_width = self.window_width * 0.5
            display_height = self.window_height * 0.6
            img.thumbnail((display_width, display_height), Image.LANCZOS)

            img_tk = ImageTk.PhotoImage(img)
            self.right_image_label.config(image=img_tk)
            self.right_image_label.image = img_tk

        # self.json_cache.clear()  # 清除缓存，以确保每次都重新加载
        # 清除以前的内容
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        

        base_name, _ = os.path.splitext(image_name)
        prefix = "_".join(base_name.split("_")[:-1])
        prefix = prefix+'_'
        accumulated_coordinates = []
        current_image_source_path = None

        # 遍历所有具有相同前缀的文件并缓存其JSON数据
        for file_name in self.image_list:
            if file_name.startswith(prefix):
                json_filename = os.path.splitext(file_name)[0] + '.json'
                print(json_filename)
                # print('json filename', json_filename)
                if json_filename not in self.json_cache:
                    json_url = f"{self.server_url}/ocr_doc_sample/result/{self.current_folder}/{json_filename}"
                    json_response = requests.get(json_url)
                    if json_response.status_code == 200:
                        try:
                            data = json_response.json()
                            self.json_cache[json_filename] = data  # 缓存JSON数据
                        except json.JSONDecodeError:
                            continue

                # 获取缓存的数据
                data = self.json_cache.get(json_filename)
                if data:
                    source_image_path = data.get('source_image_path')
                    content = data.get('content', '')
                    coordinates = data.get('coordinates', '')
                    # 如果这是第一次加载或者切换到新图片，更新原图
                    if current_image_source_path is None:
                        current_image_source_path = source_image_path
                    # 累积所有的坐标
                    accumulated_coordinates.append((coordinates, file_name == image_name))

                    # 显示内容和坐标
                    # content_label = tk.Label(self.scrollable_frame, text=f"{content}", anchor="w", justify="left")
                    # content_label.pack(fill=tk.X, padx=10, pady=5)
                    # 将文件内容一行一行地显示并允许编辑
                    # print(f"Creating Entry for line {global_row_idx}: {line}")  # 调试信息
                    custom_font = font.Font(family="Helvetica", size=14)
                    entry = tk.Entry(self.scrollable_frame, width=60, font=custom_font)
                    entry.insert(0, content)
                    entry.grid(column=0, padx=10, pady=2, sticky="w")
                    entry.json_filename = json_filename 
                    # print(f"Grid info: row={idx}, column=0")  # 添加调试信息
                    

                    # 获取当前行
                    current_row = entry.grid_info()['row']
                    # 用于表示选中的状态变量
                    classification_var = tk.StringVar(value="")
                    # 在循环中创建每个 Checkbutton 的时候，恢复状态

                    # Checkbutton 替代 Radiobutton，默认不选中
                    checkbutton1 = tk.Checkbutton(self.scrollable_frame, text="印刷", variable=classification_var, onvalue="print", offvalue="", command=lambda j=json_filename: self.handle_classification("print", j, classification_var))
                    checkbutton1.grid(row=current_row, column=1, padx=3)

                    checkbutton2 = tk.Checkbutton(self.scrollable_frame, text="手写", variable=classification_var, onvalue="handwriting", offvalue="", command=lambda j=json_filename: self.handle_classification("handwriting", j, classification_var))
                    checkbutton2.grid(row=current_row, column=2, padx=3)

                    checkbutton3 = tk.Checkbutton(self.scrollable_frame, text="数字", variable=classification_var, onvalue="number", offvalue="", command=lambda j=json_filename: self.handle_classification("number", j, classification_var))
                    checkbutton3.grid(row=current_row, column=3, padx=3)


                    # entry.bind("<FocusOut>", lambda e, json_filename=json_filename, entry=entry: self.save_line_change(json_filename, entry.get()))
                    # entry.bind("<Return>", lambda e, json_filename=json_filename, entry=entry: self.save_line_change(json_filename, entry.get()))


        # 如果找到了原图路径，显示左侧的原图和标记
        # 检查是否需要切换原图
        if current_image_source_path:
            if current_image_source_path != self.last_image_source_path:
                # 如果切换了原图，先保存当前内容
                for entry in self.scrollable_frame.winfo_children():
                    if isinstance(entry, tk.Entry):
                        json_filename = entry.json_filename  # 从Entry属性获取关联的JSON文件名
                        self.save_line_change(json_filename, entry.get())
                # 更新左侧显示的原图
                self.last_image_source_path = current_image_source_path
            self.display_source_image(current_image_source_path, accumulated_coordinates)
        else:
            print("Error: No source image path found.")

    def save_line_change(self, json_filename, new_text):
        """保存修改后的内容到 JSON 缓存中，并更新服务器上的 JSON 和 TXT 文件"""
        data = self.json_cache.get(json_filename)
        if data:
            old_text = data.get('content', '')
            if old_text != new_text:  
                data['content'] = new_text  # 更新内容
                self.json_cache[json_filename] = data

                json_url = f"{self.server_url}/ocr_doc_sample/result/{self.current_folder}/{json_filename}"
                try:
                    response = requests.put(json_url, json=data)
                    if response.status_code == 200:
                        txt_url = json_url.replace('.json', '.txt')
                        response = requests.put(txt_url, data=new_text)
                        if response.status_code == 200:
                            print(f"Content saved successfully to JSON and TXT files on the server.")
                        else:
                            print(f"Failed to save TXT file on the server. Status code: {response.status_code}")
                    else:
                        print(f"Failed to save JSON file on the server. Status code: {response.status_code}")
                except Exception as e:
                    print(f"Error occurred while saving to the server: {e}")

    def save_current_content(self):
        for entry in self.scrollable_frame.winfo_children():
                    if isinstance(entry, tk.Entry):
                        json_filename = entry.json_filename  # 从Entry属性获取关联的JSON文件名
                        self.save_line_change(json_filename, entry.get())

    def display_source_image(self, source_image_path, coordinates_list):
        self.source_image_path = source_image_path
        if source_image_path in self.image_cache:
            # 如果图片已经缓存，直接使用缓存的数据
            print(f"Using cached image for: {source_image_path}")
            img, (scale_x, scale_y) = self.image_cache[source_image_path]
        else:
            relative_source_path = source_image_path.replace(UPLOAD_FOLDER, '').lstrip('/')
            image_url = f"{self.server_url}/source_doc/{relative_source_path}"
            print("Constructed image_url:", image_url)
            response = requests.get(image_url)
            if response.status_code == 200:
                img_data = BytesIO(response.content)
                img = Image.open(img_data)

                # 自动调整图片方向
                img = ImageOps.exif_transpose(img)

                original_width, original_height = img.size
                self.source_image_height = original_height
                self.source_image_width = original_width
                self.original_source_image = img.copy()
                display_width = self.window_width * 0.8
                display_height = self.window_height * 0.7
                img.thumbnail((display_width, display_height), Image.LANCZOS)

                # 缩放后的尺寸
                scaled_width, scaled_height = img.size
                scale_x = scaled_width / original_width
                scale_y = scaled_height / original_height
                self.scale_x = scale_x
                self.scale_y = scale_y

                # 缓存图片和缩放比例
                self.image_cache[source_image_path] = (img, (scale_x, scale_y))
            else:
                self.left_image_label.config(text="加载原图失败")
                return 
        # 清除先前的矩形框信息
        self.rectangles_info = []
        img_with_boxes = img.copy()
        draw = ImageDraw.Draw(img_with_boxes)
        for coordinates, is_current in coordinates_list:
            if coordinates:
                coordinates = list(map(int, coordinates.split(',')))
                adjusted_coordinates = [
                    int(coordinates[0] * scale_x), int(coordinates[1] * scale_y),
                    int(coordinates[2] * scale_x), int(coordinates[3] * scale_y),
                    int(coordinates[4] * scale_x), int(coordinates[5] * scale_y),
                    int(coordinates[6] * scale_x), int(coordinates[7] * scale_y),
                ]
                x_coordinates = adjusted_coordinates[::2]  # 提取 x 坐标: [x0, x1, x2, x3]
                y_coordinates = adjusted_coordinates[1::2]  # 提取 y 坐标: [y0, y1, y2, y3]
                x0, y0 = min(x_coordinates), min(y_coordinates)
                x1, y1 = max(x_coordinates), max(y_coordinates)

                # 保存矩形框的坐标和关联的文件名
                self.rectangles_info.append({
                    'rect': (x0, y0, x1, y1),
                    'coordinates': coordinates  # 假设 coordinates 可以关联到文件名
                })
                color = "blue" if is_current else "red"
                draw.rectangle([x0, y0, x1, y1], outline=color, width=2)

        img_tk = ImageTk.PhotoImage(img_with_boxes)
        self.left_image_label.config(image=img_tk)
        self.left_image_label.image = img_tk
        
        self.left_image_label.bind("<Button-1>", self.on_image_click)

    def on_image_click(self, event):
        # 获取点击的位置
        click_x, click_y = event.x, event.y
        print(click_x, click_y)

        # 获取图像在Label中的实际位置
        img_label_x = (self.left_image_label.winfo_width() - self.left_image_label.image.width()) // 2
        img_label_y = (self.left_image_label.winfo_height() - self.left_image_label.image.height()) // 2
        print(f"Image label offset: ({img_label_x}, {img_label_y})")

        # 将点击坐标转换为相对于图像左上角的坐标
        click_x -= img_label_x
        click_y -= img_label_y
        print(f"Adjusted click position: ({click_x}, {click_y})")
        
        # 遍历矩形框信息，判断点击的位置是否在某个框内
        for rect_info in self.rectangles_info:
            x0, y0, x1, y1 = rect_info['rect']

            # 将矩形框的坐标也映射回原图的坐标范围
            if x0 <= click_x <= x1 and y0 <= click_y <= y1:
                # 找到点击的框，更新右侧显示的图片
                selected_coordinates = rect_info['coordinates']
                # print(f"Selected coordinates: {selected_coordinates}")
                for file_name in self.image_list:
                    json_filename = os.path.splitext(file_name)[0] + '.json'
                    data = self.json_cache.get(json_filename)
                    # print(f"Checking file: {file_name}, Data: {data}")
                    if data:
                        json_coords = list(map(int, data.get('coordinates').split(',')))
                        # print(f"Checking file: {file_name}, Data coordinates: {json_coords}")
                        
                        if self.compare_coordinates(json_coords, selected_coordinates):
                            print(f"Matched file: {file_name}, Showing image.")
                            self.show_image(self.image_list.index(file_name))
                            break
                break
            # else:
                # print("No matching rect found.")

    def compare_coordinates(self, coords1, coords2, tolerance=5):
        """比较两个坐标列表,如果坐标差异在容差范围内,则返回True"""
        return all(abs(c1 - c2) <= tolerance for c1, c2 in zip(coords1, coords2))

    def show_context_menu(self, event):
        # 显示右键菜单
        self.context_menu.post(event.x_root, event.y_root)

    def handle_classification(self, classification, json_filename, classification_var):
        print(f"Attempting to classify {json_filename} as {classification}") 

        self.save_current_content()
        var_value = classification_var.get()
        
        # 获取当前的 JSON 数据
        data = self.json_cache.get(json_filename, {})
        
        # 更新 JSON 数据中的分类状态
        if var_value == classification:
            if 'classification' in data and data['classification'] == classification:
                del data['classification']  # 如果用户取消选中，则删除分类信息
        else:
            data['classification'] = classification  # 保存新的分类状态
            self.move_image_to_folder(classification, json_filename)
        
        # 更新 JSON 缓存
        self.json_cache[json_filename] = data
        
        # 保存更新后的 JSON 数据到服务器
        json_url = f"{self.server_url}/ocr_doc_sample/result/{self.current_folder}/{json_filename}"
        try:
            response = requests.put(json_url, json=data)
            if response.status_code != 200:
                print(f"Failed to update JSON file on server. Status code: {response.status_code}")
        except Exception as e:
            print(f"Error occurred while saving to the server: {e}")

    def move_image_to_folder(self, classification, json_filename):
        # 获取 JSON 文件的基名
        json_base = os.path.splitext(json_filename)[0]
        
        # 获取当前图片的文件名
        current_image_name = f"{json_base}.png"
        current_image_base = os.path.splitext(current_image_name)[0]
        # print('cueent image name', current_image_name)

        # 构造相关文件的路径
        source_image_path = f'{RESULT_FOLDER}/{self.current_folder}/{current_image_name}'
        source_json_path = f'{RESULT_FOLDER}/{self.current_folder}/{current_image_base}.json'
        source_txt_path = f'{RESULT_FOLDER}/{self.current_folder}/{current_image_base}.txt'
    
        # 确定目标文件夹
        if classification == "print":
            target_folder = f"{CLASS_FOLDER}/print/"
        elif classification == "handwriting":
            target_folder = f"{CLASS_FOLDER}/handwriting/"
        elif classification == "number":
            target_folder = f"{CLASS_FOLDER}/number/"
        # 构造目标文件夹的URL
        move_url = f"{self.server_url}/ocr_doc_sample/move_image"

        try:
            response = requests.post(move_url, json={
                'source_image_path': source_image_path,
                'source_json_path': source_json_path,
                'source_txt_path': source_txt_path,
                'target_folder': target_folder
            })
            if response.status_code == 200:
                # messagebox.showinfo("操作成功", f"文件已移动到 {target_folder} 文件夹")
                print(f'文件已移动到 {target_folder} 文件夹')
                if current_image_name in self.image_list:
                    self.image_list.remove(current_image_name)
                    
                    if len(self.image_list) > 0:
                        self.remove_rectangle_by_image_name(current_image_name)
                        self.current_image_index = min(self.current_image_index, len(self.image_list) - 1)
                        self.show_image(self.current_image_index)
                    else:
                        # self.show_next_image
                        self.clear_image_display()
                        messagebox.showinfo("分类完成", f"已将最后一张图片分类到 {target_folder}")
                
            else:
                messagebox.showerror("错误", f"无法移动文件：{response.status_code}")

            
        except Exception as e:
            messagebox.showerror("错误", f"无法移动文件：{str(e)}")

    def clear_image_display(self):
        # 清空图片显示区域
        self.right_image_label.config(image='')
        self.image_index_label.config(text='没有更多图片')
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

    def delete_image_from_server(self):
        image_name = self.current_image_name  # 假设你有方法获取当前的图片名称
        folder_name = self.current_folder
        
        delete_url = f"{self.server_url}/ocr_doc_sample/result/{folder_name}/{image_name}"
        print(delete_url)

        response = requests.delete(delete_url)

        if response.status_code == 200:
            messagebox.showinfo("操作成功", f"文件 {image_name} 已成功删除。")
            if image_name in self.image_list:
                self.image_list.remove(image_name)
            self.remove_rectangle_by_image_name(image_name)

        # 显示下一张图片
            if self.current_image_index >= len(self.image_list):
                self.current_image_index = 0  # 如果已到最后一张，循环到第一张
            self.show_image(self.current_image_index)
        else:
            messagebox.showerror("删除失败", f"无法删除文件 {image_name}，状态码：{response.status_code}")

    def remove_rectangle_by_image_name(self, image_name):
        """
        根据图片名称，移除左侧原图中对应的矩形框。
        """
        for rect_info in self.rectangles_info:
            coordinates = rect_info['coordinates']
            rect_image_name = f"{os.path.splitext(image_name)[0]}.json"
            rect_json_filename = f"{rect_image_name}.json"
            
            if rect_json_filename in self.json_cache:
                cached_data = self.json_cache[rect_json_filename]
                if cached_data['source_image_path'].endswith(image_name):
                    # 找到对应的矩形框
                    self.rectangles_info.remove(rect_info)
                    self.display_source_image(self.last_image_source_path, self.rectangles_info)  # 重新绘制原图，移除矩形框
                    break

    def start_region_selection(self):
        # 在一个新窗口中显示原图并进行区域选择
        self.region_window = Toplevel(self.root)
        self.region_window.title("选择区域")
        # 获取屏幕的宽度和高度
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # 设置窗口的初始尺寸为图像的尺寸
        window_width, window_height = self.source_image_width, self.source_image_height
        scale_ratio = 1
        # 限制窗口的最大尺寸为屏幕的尺寸
        if window_width > screen_width or window_height > screen_height:
            scale_ratio = min(screen_width / window_width, screen_height / window_height)/2
            window_width = int(window_width * scale_ratio)
            window_height = int(window_height * scale_ratio)
        # self.region_window.geometry(f"{self.source_image_width}x{self.source_image_height}")
        self.region_window.geometry(f"{window_width}x{window_height}")

        # 确保新窗口在主窗口内居中显示
        # window_width, window_height = self.source_image_width, self.source_image_height
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_width = self.root.winfo_width()
        parent_height = self.root.winfo_height()

        # 计算弹出窗口的位置，使其居中于主窗口
        position_right = parent_x + int(parent_width/2 - window_width/2)
        position_down = parent_y + int(parent_height/2 - window_height/2)

        self.region_window.geometry(f"{window_width}x{window_height}+{position_right}+{position_down}")

        # 创建 Canvas 显示原图
        img_resized = self.original_source_image.resize((window_width, window_height), Image.LANCZOS)

        self.region_canvas = Canvas(self.region_window, width=img_resized.width, height=img_resized.height)
        self.region_canvas.pack()
        
        self.region_img_tk = ImageTk.PhotoImage(img_resized)
        self.region_canvas.create_image(0, 0, anchor=tk.NW, image=self.region_img_tk)
        # 绑定鼠标事件
        self.region_canvas.bind("<ButtonPress-1>", self.on_region_start)
        self.region_canvas.bind("<B1-Motion>", self.on_region_drag)
        self.region_canvas.bind("<ButtonRelease-1>", lambda event: self.on_region_end(event, scale_ratio))

    def on_region_start(self, event):
        # Record the start coordinates
        self.region_start = (event.x, event.y)

    def on_region_drag(self, event):
        # Update the selected region as the mouse is dragged
        self.region_end = (event.x, event.y)
        self.update_region_display()

    def on_region_end(self, event, scale_ratio):
        # Record the end coordinates and finalize the selection
        self.region_end = (event.x, event.y)
        self.update_region_display()

        # Adjust coordinates back to the original image size
        x0, y0 = self.region_start
        x1, y1 = self.region_end
        original_x0, original_y0 = int(x0 / scale_ratio), int(y0 / scale_ratio)
        original_x1, original_y1 = int(x1 / scale_ratio), int(y1 / scale_ratio)

        # Save the selected region with original coordinates
        self.save_selected_region(original_x0, original_y0, original_x1, original_y1)

    def update_region_display(self):
        # 在 Canvas 上绘制选择框
        self.region_canvas.delete("region")
        if self.region_start and self.region_end:
            x0, y0 = self.region_start
            x1, y1 = self.region_end
            self.region_canvas.create_rectangle(x0, y0, x1, y1, outline="red", width=2, tag="region")

    def save_selected_region(self, x0, y0, x1, y1):
        # Ensure coordinates are correct
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0

        # Crop the selected region from the original image
        region = self.original_source_image.crop((x0, y0, x1, y1))

        # Save the region and the original coordinates
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = self.current_image_basename
        new_image_name = f"{base_name}_add_{timestamp}.png"
        new_json_name = f"{base_name}_add_{timestamp}.json"

        region_url = f"{self.server_url}/ocr_doc_sample/result/dataset_addarea/{new_image_name}"
        region_data = BytesIO()
        region.save(region_data, format="PNG")
        region_data.seek(0)

        response = requests.put(region_url, data=region_data.getvalue())

        if response.status_code == 200:
            json_data = {
                'source_image_path': self.source_image_path,
                'coordinates': f"{x0},{y0},{x1},{y0},{x1},{y1},{x0},{y1}",
                'content': "null"
            }
            json_url = f"{self.server_url}/ocr_doc_sample/result/dataset_addarea/{new_json_name}"
            response = requests.put(json_url, json=json_data)
            if response.status_code == 200:
                ocr_request_url = f"{self.server_url}/run_ocr"
                ocr_request_data = {
                    'image_dir': f"{RESULT_FOLDER}/dataset_addarea"
                }
                ocr_response = requests.post(ocr_request_url, json=ocr_request_data)
                messagebox.showinfo("操作成功", "区域已保存并上传到服务器,已经识别完成")
            else:
                messagebox.showerror("错误", f"无法保存区域信息到服务器：{response.status_code}")
        else:
            messagebox.showerror("错误", f"无法上传选定区域的图片：{response.status_code}")

        self.region_window.destroy()

    def select_folder(self, event=None):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.upload_folder(folder_path)

    def upload_folder(self, folder_path):
        def upload_task():
            relative_path = ""
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(root, folder_path)
                    if relative_path == ".":
                        relative_path = ""
                    with open(file_path, 'rb') as f:
                        response = requests.post(f"{self.server_url}/upload", 
                                                files={'file': f}, 
                                                data={'path': relative_path})
                    print(f"Uploaded {file} with status {response.status_code}, now run_ocr")

                response = requests.post(f"{self.server_url}/rename", data={'folder_path': f"{UPLOAD_FOLDER}"})
                print(response.json())

        # 在新的线程中运行上传任务
        threading.Thread(target=upload_task).start()

    def on_source_right_click(self, event):
        # 获取点击的位置
        click_x, click_y = event.x, event.y

        # 获取图像在Label中的实际位置
        img_label_x = (self.left_image_label.winfo_width() - self.left_image_label.image.width()) // 2
        img_label_y = (self.left_image_label.winfo_height() - self.left_image_label.image.height()) // 2

        # 将点击坐标转换为相对于图像左上角的坐标
        click_x -= img_label_x
        click_y -= img_label_y

        # 遍历矩形框信息，判断点击的位置是否在某个框内
        for rect_info in self.rectangles_info:
            x0, y0, x1, y1 = rect_info['rect']
            if x0 <= click_x <= x1 and y0 <= click_y <= y1:
                # 找到点击的框，弹出菜单
                print(rect_info)
                self.selected_region = rect_info  # 记录选中的区域
                json_filename = rect_info.get('json_filename', '')  # 获取关联的JSON文件名
                print('on_source_right_click json name',json_filename )
                self.show_context_menu(event, json_filename)
                return
        # 如果点击不在任何框内，取消选中区域
        self.selected_region = None      

        print('selected_region', select_region)

    def show_context_menu(self, event, json_filename):
        # 创建右键菜单
        context_menu = Menu(self.root, tearoff=0)
        context_menu.add_command(label="分类到手写文件夹", command=lambda: self.move_image_to_folder('handwriting', json_filename))
        context_menu.add_command(label="分类到印刷文件夹", command=lambda: self.move_image_to_folder('print', json_filename))
        context_menu.add_command(label="分类到数字文件夹", command=lambda: self.move_image_to_folder('number', json_filename))
        context_menu.add_command(label="删除", command=self.delete_image_from_server)

        # 显示右键菜单
        context_menu.post(event.x_root, event.y_root)

    def show_delete_menu(self, event):
        # 创建右键菜单
        context_delete_menu = Menu(self.root, tearoff=0)
        context_delete_menu.add_command(label="删除", command=self.delete_image_from_server)

        # 显示右键菜单
        context_delete_menu.post(event.x_root, event.y_root)

if __name__ == "__main__":
    # server_url = ""  # 替换为你的Linux服务器的URL
    server_ipadd = IP_ADDRESS
    server_port = PORT
    server_url = f"http://{server_ipadd}:{server_port}"
    root = tk.Tk()
    app = RemoteImageViewerApp(root, server_url)
    root.mainloop()
