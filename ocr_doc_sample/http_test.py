import os
import tkinter as tk
from tkinter import filedialog, Listbox, Scrollbar, Label, simpledialog, Toplevel, messagebox, Menu, Canvas
from PIL import Image, ImageTk, ImageDraw
import json
import requests
from io import BytesIO
from bs4 import BeautifulSoup
import shutil
from datetime import datetime
from natsort import natsorted


BASE_DIR = '/mnt/zt/ocr_doc_sample'     #跟http服务器的一样

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
        self.source_image_width = None
        self.source_image_height = None
        self.display_image_width = None
        self.display_image_height = None
        self.root.geometry("1200x800")
        self.root.title("Remote Image Viewer")
        window_width=1200
        window_height=800
        self.root.resizable(False, False)
        # self.root.overrideredirect(True)
        self.center_window(window_width, window_height)
        self.create_widgets()

        # 绑定鼠标滚轮和键盘左右键事件
        self.root.bind("<Left>", self.show_prev_image)  # 绑定左箭头键
        self.root.bind("<Right>", self.show_next_image)  # 绑定右箭头键
        self.root.bind("<MouseWheel>", self.on_mouse_wheel)  # 绑定鼠标滚轮

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
        # Folder selection
        self.select_button = tk.Button(self.root, text="选择文件夹", command=self.open_folder_selection)
        self.select_button.pack(side=tk.TOP, pady=10)

        # Image display area
        self.left_image_label = tk.Label(self.root)
        self.left_image_label.pack(side=tk.LEFT, padx=0, pady=0, expand=True, fill=tk.BOTH)

        # 添加一个新的按钮到 left_image_label 下方
        self.select_region_button = tk.Button(self.root, text="选择区域", command=self.start_region_selection)
        self.select_region_button.pack(side=tk.LEFT, padx=10, pady=5)

        self.right_frame = tk.Frame(self.root)
        self.right_frame.pack(side=tk.LEFT, padx=50, pady=10, expand=False, anchor='center')

        self.right_image_label = tk.Label(self.right_frame)
        self.right_image_label.pack(side=tk.TOP, padx=10, pady=10, expand=True)

        # 为右键点击右侧图片绑定事件
        self.right_image_label.bind("<Button-3>", self.show_context_menu)

        # 创建右键菜单
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="保存到手写文件夹", command=lambda: self.move_image_to_folder('handwriting'))
        self.context_menu.add_command(label="保存到印刷文件夹", command=lambda: self.move_image_to_folder('print'))
        self.context_menu.add_command(label="保存到数字文件夹", command=lambda: self.move_image_to_folder('number'))
        self.context_menu.add_command(label="删除", command=self.delete_image_from_server)

        # Create a frame to hold the content_text and buttons below the right_image_label
        self.bottom_frame = tk.Frame(self.right_frame)
        self.bottom_frame.pack(side=tk.TOP, padx=10, pady=10, fill=tk.X)

        # Text widget for displaying and editing JSON content
        self.content_text = tk.Text(self.bottom_frame, wrap=tk.WORD, height=2, width=40)
        # self.content_text.pack(side=tk.TOP, padx=5, pady=5, fill=tk.BOTH)
        self.content_text.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        self.bottom_frame.pack_propagate(False)
        self.bottom_frame.config(width=400, height=150)

        # Save button to save the edited content back to the JSON file
        self.save_button = tk.Button(self.bottom_frame, text="保存修改", command=self.save_content)
        # self.save_button.pack(side=tk.TOP, pady=5)
        self.save_button.grid(row=1, column=0, columnspan=2, pady=5)

        # Place the buttons for navigating images below the content_text
        self.buttons_frame = tk.Frame(self.bottom_frame)
        # self.buttons_frame.pack(side=tk.TOP, pady=5, fill=tk.X)
        self.buttons_frame.grid(row=2, column=0, columnspan=2, pady=5)

        self.prev_button = tk.Button(self.buttons_frame, text="上一张", command=self.show_prev_image)
        self.prev_button.pack(side=tk.LEFT, padx=5)

        self.next_button = tk.Button(self.buttons_frame, text="下一张", command=self.show_next_image)
        self.next_button.pack(side=tk.RIGHT, padx=5)

        self.bottom_frame.grid_rowconfigure(0, weight=1)
        self.bottom_frame.grid_columnconfigure(0, weight=1)

        # 显示当前图片编号的标签
        self.image_index_label = tk.Label(self.right_frame, text="第 1 张")
        self.image_index_label.pack(side=tk.TOP, pady=5)

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


    def show_image(self, index):
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
        if self.current_image_index == 0:
            self.current_image_index = len(self.image_list) - 1  # Loop to last image
        else:
            self.current_image_index -= 1
        self.show_image(self.current_image_index)

    def show_next_image(self, event=None):
        if self.current_image_index == len(self.image_list) - 1:
            self.current_image_index = 0  # Loop to first image
        else:
            self.current_image_index += 1
        self.show_image(self.current_image_index)


    def display_images(self, image_url, image_name):
        # 确保没有在 URL 末尾添加错误的斜杠
        response = requests.get(image_url)
        if response.status_code == 200:
            img_data = BytesIO(response.content)
            img = Image.open(img_data)

            display_width = 500
            display_height = 700
            img.thumbnail((display_width, display_height), Image.LANCZOS)

            img_tk = ImageTk.PhotoImage(img)
            self.right_image_label.config(image=img_tk)
            self.right_image_label.image = img_tk

            json_filename = os.path.splitext(image_name)[0] + '.json'
            json_url = f"{self.server_url}/ocr_doc_sample/result/{self.current_folder}/{json_filename}"
            self.current_json_path = json_url

            json_response = requests.get(json_url)
            if json_response.status_code == 200:
                try:
                    data = json_response.json()
                    source_image_path = data.get('source_image_path')
                    self.source_image_path = source_image_path
                    content = data.get('content', '')
                    coordinates = data.get('coordinates', '')
                    if source_image_path:
                        self.display_source_image(source_image_path, coordinates)
                    else:
                        self.left_image_label.config(text="JSON中没有找到原图路径")

                    self.content_text.delete(1.0, tk.END)
                    self.content_text.insert(tk.END, content)

                except json.JSONDecodeError:
                    self.left_image_label.config(text="JSON解析失败")
            else:
                self.left_image_label.config(text="未找到JSON文件")


    def display_source_image(self, source_image_path, coordinates):
        # 显示原图
        relative_source_path = source_image_path.replace(BASE_DIR, "ocr_doc_sample")    #需要将/mnt/zt/xxx修改为http服务代码的BASE_DIR
        response = requests.get(f"{self.server_url}/{relative_source_path}")
        if response.status_code == 200:
            img_data = BytesIO(response.content)
            img_source = Image.open(img_data)

            self.source_image = img_source.copy()
            original_width, original_height = img_source.size
            self.source_image_width, self.source_image_height = img_source.size

            # 缩放图片但保持比例
            display_width = 500  # 左右各占一半空间
            display_height = 700  # 高度不变
            img = img_source.copy()
            img.thumbnail((display_width, display_height), Image.LANCZOS)


            # 获取缩放后的尺寸
            scaled_width, scaled_height = img.size

            # 计算缩放比例
            scale_x = scaled_width / original_width
            scale_y = scaled_height / original_height
            # 如果提供了坐标，则绘制矩形框
            if coordinates:
                # 将字符串坐标拆分并转换为整数列表
                coordinates = list(map(int, coordinates.split(',')))

                # 按照缩放比例调整坐标
                adjusted_coordinates = [
                    int(coordinates[0] * scale_x), int(coordinates[1] * scale_y),
                    int(coordinates[2] * scale_x), int(coordinates[3] * scale_y),
                    int(coordinates[4] * scale_x), int(coordinates[5] * scale_y),
                    int(coordinates[6] * scale_x), int(coordinates[7] * scale_y),
                ]

                # 计算矩形的左上角和右下角坐标
                x_coordinates = adjusted_coordinates[::2]  # 提取 x 坐标: [x0, x1, x2, x3]
                y_coordinates = adjusted_coordinates[1::2]  # 提取 y 坐标: [y0, y1, y2, y3]

                x0, y0 = min(x_coordinates), min(y_coordinates)
                x1, y1 = max(x_coordinates), max(y_coordinates)

                # 使用计算出的左上角和右下角坐标绘制矩形
                draw = ImageDraw.Draw(img)
                draw.rectangle([x0, y0, x1, y1], outline="red", width=2)


            img_tk = ImageTk.PhotoImage(img)
            self.left_image_label.config(image=img_tk)
            self.left_image_label.image = img_tk
        else:
            self.left_image_label.config(text="加载原图失败")

    def save_content(self):
        # 保存修改后的 content 内容到服务器上的 JSON 文件和同名 TXT 文件
        new_content = self.content_text.get(1.0, tk.END).strip()
        try:
            # 更新服务器上的 JSON 文件
            print(f"JSON URL: {self.current_json_path}")  # 打印服务器上的 JSON 文件路径以确认
            response = requests.get(self.current_json_path)
            if response.status_code == 200:
                data = response.json()
                data['content'] = new_content
                # print("data[content]", data['content'])
                # 将修改后的数据上传回服务器
                response = requests.put(self.current_json_path, json=data)
                if response.status_code == 200:
                    # 更新同名 TXT 文件
                    txt_url = self.current_json_path.replace('.json', '.txt')
                    response = requests.put(txt_url, data=new_content)
                    if response.status_code == 200:
                        messagebox.showinfo("保存成功", "内容已成功保存到服务器上的 JSON 和 TXT 文件")
                    else:
                        messagebox.showerror("保存失败", "无法保存 TXT 文件到服务器")
                else:
                    messagebox.showerror("保存失败", "无法保存 JSON 文件到服务器")
            else:
                messagebox.showerror("保存失败", "无法访问服务器上的 JSON 文件")
        except Exception as e:
            messagebox.showerror("保存失败", f"保存时出错: {e}")

    def show_context_menu(self, event):
        # 显示右键菜单
        self.context_menu.post(event.x_root, event.y_root)

    def move_image_to_folder(self, target_folder):
        # 获取当前图片的URL
        # 获取当前图片的文件名
        current_image_name = self.image_list[self.current_image_index]
        current_image_base = os.path.splitext(current_image_name)[0]

        # 构造相关文件的路径
        source_image_path = f'/ocr_doc_sample/result/{self.current_folder}/{current_image_name}'
        source_json_path = f'/ocr_doc_sample/result/{self.current_folder}/{current_image_base}.json'
        source_txt_path = f'/ocr_doc_sample/result/{self.current_folder}/{current_image_base}.txt'
    
        # 构造目标文件夹的URL
        move_url = f"{self.server_url}/ocr_doc_sample/move_image"

        try:
            response = requests.post(move_url, json={
                'source_image_path': source_image_path,
                'source_json_path': source_json_path,
                'source_txt_path': source_txt_path,
                'target_folder': f'ocr_doc_sample/classify_dataset/{target_folder}/'
            })
            if response.status_code == 200:
                messagebox.showinfo("操作成功", f"文件已移动到 {target_folder} 文件夹")
            else:
                messagebox.showerror("错误", f"无法移动文件：{response.status_code}")

            self.current_image_index += 1
            self.show_image(self.current_image_index)
        except Exception as e:
            messagebox.showerror("错误", f"无法移动文件：{str(e)}")


    def delete_image_from_server(self):
        image_name = self.current_image_name  # 假设你有方法获取当前的图片名称
        folder_name = self.current_folder
        
        delete_url = f"{self.server_url}/ocr_doc_sample/result/{folder_name}/{image_name}"
        print(delete_url)

        response = requests.delete(delete_url)

        if response.status_code == 200:
            messagebox.showinfo("操作成功", f"文件 {image_name} 已成功删除。")
        else:
            messagebox.showerror("删除失败", f"无法删除文件 {image_name}，状态码：{response.status_code}")


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

        # # 创建 Canvas 显示原图
        # self.region_canvas = Canvas(self.region_window, width=self.source_image_width, height=self.source_image_height)
        # self.region_canvas.pack()
        self.region_canvas = Canvas(self.region_window, width=window_width, height=window_height)
        self.region_canvas.pack()
        img_resized = self.source_image.copy()
        img_resized.thumbnail((window_width, window_height), Image.LANCZOS)

        # # 将原图显示到 Canvas 上
        # self.region_img_tk = ImageTk.PhotoImage(self.source_image)
        # self.region_canvas.create_image(0, 0, anchor=tk.NW, image=self.region_img_tk)
        # 将调整后的图像显示到 Canvas 上
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
        region = self.source_image.crop((x0, y0, x1, y1))

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
                    'image_dir': f"{BASE_DIR}/result/dataset_addarea"
                }
                ocr_response = requests.post(ocr_request_url, json=ocr_request_data)
                messagebox.showinfo("操作成功", "区域已保存并上传到服务器,已经识别完成")
            else:
                messagebox.showerror("错误", f"无法保存区域信息到服务器：{response.status_code}")
        else:
            messagebox.showerror("错误", f"无法上传选定区域的图片：{response.status_code}")

        self.region_window.destroy()


        

if __name__ == "__main__":
    server_url = "http://172.31.221.249:8099"  # 替换为你的Linux服务器的URL
    root = tk.Tk()
    app = RemoteImageViewerApp(root, server_url)
    root.mainloop()
