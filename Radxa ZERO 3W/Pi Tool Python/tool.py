from PIL import Image, ImageDraw, ImageFont
import os
import time
import psutil
import socket
import fcntl
import struct
import subprocess
import gpiod
import signal
import binascii

# 设置字体
try:
    # font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font_path = "DejaVuSansYuanTi-Regular.ttf"
    font = ImageFont.truetype(font_path, size=18)  # 调整字体大小为18
except IOError:
    print("字体文件未找到，使用默认字体。")
    font = ImageFont.load_default()

# 设置屏幕大小
WIDTH, HEIGHT = 240, 240
ROWS = 8
ROW_HEIGHT = HEIGHT // ROWS

# 按钮配置 (简化版，根据实际情况修改)
buttons = {
    "Left": ("gpiochip3", 11),     # 左按键
    "Right": ("gpiochip1", 4),     # 右按键
    "Down": ("gpiochip3", 4),      # 下按键
    "Up": ("gpiochip3", 12),       # 上按键
    "KEY1": ("gpiochip3", 5),      # 输入按键
    "KEY2": ("gpiochip3", 6),      # 退出按键
    "KEY3": ("gpiochip3", 7)       # 刷新按键
}

# 定义软键盘布局
keyboard_layout = [
    ["0", "1", "2", "3", "4", "5", "6", "7"],
    ["8", "9", "a", "b", "c", "d", "e", "f"],
    ["g", "h", "i", "j", "k", "l", "m", "n"],
    ["o", "p", "q", "r", "s", "t", "u", "v"],
    ["w", "x", "y", "z", "A", "B", "C", "D"],
    ["E", "F", "G", "H", "I", "J", "K", "L"],
    ["M", "N", "O", "P", "Q", "R", "S", "T"],
    ["U", "V", "W", "X", "Y", "Z", "!", "@"],
    ["#", "$", "%", "^", "&", "*", "(", ")"]
]

# GPIO初始化
chips = {}
lines = {}
prev_values = {}  # 用于存储每个按钮的前一个状态

# 当前页面索引 (0:设备状态页, 1:网络信息页, 2:Wi-Fi列表页)
current_page = 0

# 新增密码输入相关变量
current_page = 0  # 当前页面索引
selected_wifi_index = 0  # 当前选中的Wi-Fi索引
start_wifi_index = 0  # 用于滚动显示Wi-Fi列表
wifi_list_scanned = False  # 标志是否已经扫描过Wi-Fi列表
current_wifi_name = ""  # 当前连接的Wi-Fi名称
current_wifi_password = ""  # 当前输入的密码
selected_key_row = 0  # 当前选中的软键盘行索引
selected_key_col = 0  # 当前选中的软键盘列索引
start_key_row = 0  # 软键盘滚动显示的起始行
selected_cmd_index = 0
start_cmd_index = 0
cmd_list = []
cmd_dict = {}

# 关闭光标闪烁
try:
    with open('/sys/class/graphics/fbcon/cursor_blink', 'w') as f:
        f.write('0')
except IOError:
    print("无法关闭光标闪烁，请检查权限或路径是否正确。")

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 将16进制的UTF-8编码转换为中文
def hex_to_chinese(hex_str):
    try:
        # 移除可能的引号
        hex_str = hex_str.strip('"')
        # 将字符串转换为字节
        bytes_obj = bytes.fromhex(hex_str)
        # 解码为UTF-8字符串
        chinese_str = bytes_obj.decode('utf-8')
        return chinese_str
    except (ValueError, UnicodeDecodeError):
        return hex_str

# 获取网络接口IP地址
def get_ip_address(ifname):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', bytes(ifname[:15], 'utf-8'))
        )[20:24])
    except:
        return "N/A"

# 获取网关IP地址
def get_gateway():
    try:
        result = subprocess.run(['ip', 'route'], stdout=subprocess.PIPE)
        routes = result.stdout.decode().split('\n')
        for route in routes:
            if 'default' in route:
                gateway = route.split()[2]
                return gateway
        return "N/A"
    except:
        return "N/A"

# 获取无线网络信息
def get_wireless_info():
    try:
        output = subprocess.check_output(['iwconfig', 'wlan0'])
        output = output.decode('utf-8', errors='replace')  # 处理中文转义问题
        
        # 获取 ESSID
        essid_start = output.find('ESSID:"') + 7
        essid_end = output.find('"', essid_start)
        essid = output[essid_start:essid_end]
        
        # 使用echo -e处理转义字符
        try:
            decoded_essid = subprocess.check_output(['echo', '-e', essid])
            decoded_essid = decoded_essid.decode('utf-8').strip()
        except:
            decoded_essid = essid
        
        # 尝试将ESSID从16进制转换为中文
        if all(c in '0123456789abcdefABCDEF' for c in decoded_essid):
            decoded_essid = hex_to_chinese(decoded_essid)
        
        # 获取 Bit Rate
        bit_rate_start = output.find('Bit Rate=') + 9
        bit_rate_end = output.find(' ', bit_rate_start)
        bit_rate = output[bit_rate_start:bit_rate_end] + ' Mb/s'
        
        # 获取 Link Quality
        link_quality_start = output.find('Link Quality=') + 13
        link_quality_end = output.find(' ', link_quality_start)
        link_quality = output[link_quality_start:link_quality_end]
        
        # 获取 Signal level
        signal_level_start = output.find('Signal level=') + 13
        signal_level_end = output.find(' ', signal_level_start)
        signal_level = output[signal_level_start:signal_level_end] + ' dBm'
        
        return {
            'essid': decoded_essid,
            'bit_rate': bit_rate,
            'link_quality': link_quality,
            'signal_level': signal_level
        }
    except:
        return {
            'essid': "N/A",
            'bit_rate': "N/A",
            'link_quality': "N/A",
            'signal_level': "N/A"
        }

# 连接Wi-Fi函数
def connect_wifi(ssid, password):
    try:
        # 这里是一个简单的示例，实际连接Wi-Fi的代码可能需要根据你的系统进行调整
        # 例如，可以使用`nmcli`命令来连接Wi-Fi
        # nmcli device wifi connect <SSID> password <密码>
        # 请根据你的系统环境修改此部分代码
        command = f"nmcli device wifi connect '{ssid}' password '{password}'"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except:
        return False

# 扫描周围Wi-Fi
def scan_wifi():
    try:
        output = subprocess.check_output(['iwlist', 'wlan0', 'scan'])
        output = output.decode('utf-8', errors='replace')  # 处理中文转义问题
        
        # 解析Wi-Fi列表
        wifi_entries = output.split('Cell ')
        wifi_names = []
        
        for entry in wifi_entries:
            if 'ESSID:' in entry:
                essid_start = entry.find('ESSID:"') + 7
                essid_end = entry.find('"', essid_start)
                essid = entry[essid_start:essid_end]
                
                # 如果ESSID为空，跳过此Wi-Fi
                if not essid:
                    continue
                
                # 使用echo -e处理转义字符
                try:
                    decoded_essid = subprocess.check_output(['echo', '-e', essid])
                    decoded_essid = decoded_essid.decode('utf-8').strip()
                except:
                    decoded_essid = essid
                
                wifi_names.append(decoded_essid)
        
        # 过滤掉重复和当前连接的Wi-Fi
        unique_wifi_names = list(set(wifi_names))
        if current_wifi_name in unique_wifi_names:
            unique_wifi_names.remove(current_wifi_name)
        
        return unique_wifi_names
    except:
        return []

# 将图像转换为RGB565格式，确保字节序正确
def rgb_to_rgb565(image):
    result = bytearray()
    for pixel in image.getdata():
        # 处理不同模式的图像数据
        if len(pixel) == 4:  # RGBA 模式
            r, g, b, _ = pixel
        else:  # RGB 模式
            r, g, b = pixel
        
        # 确保RGB值在有效范围内
        r = min(max(r, 0), 255)
        g = min(max(g, 0), 255)
        b = min(max(b, 0), 255)
        
        # 根据fbset的输出使用正确的位掩码
        # 格式: rgba 5/11,6/5,5/0,0/0
        red = (r >> 3) & 0x1F
        green = (g >> 2) & 0x3F
        blue = (b >> 3) & 0x1F
        
        # 组合成16位RGB565值，并确保字节序正确
        rgb565 = (red << 11) | (green << 5) | blue
        
        # 确保字节序正确（低字节在前，高字节在后）
        result.append(rgb565 & 0xFF)
        result.append((rgb565 >> 8) & 0xFF)
    return result

# 更新设备状态页
def update_system_display():
    image = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))  # 黑色背景
    draw = ImageDraw.Draw(image)

    # 绘制深粉色边框
    draw.rectangle([(0, 0), (WIDTH-1, HEIGHT-1)], outline=(255, 105, 180), width=1)

    # 绘制水平网格线（深粉色）
    for i in range(1, ROWS):
        y = i * ROW_HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=(255, 105, 180), width=1)

    # 第一行 - 系统信息
    try:
        with open('/etc/issue', 'r') as f:
            system_info = f.read().strip()
        system_info = system_info.replace(r'\n', '').replace(r'\l', '')
    except:
        system_info = "Debian GNU/Linux 11"
    bbox = font.getbbox(system_info)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (WIDTH - text_width) // 2
    y = (ROW_HEIGHT - text_height) // 2
    draw.text((x, y), system_info, font=font, fill=(255, 255, 255))

    # 第二行 - 运行时间
    uptime = time.time() - psutil.boot_time()
    days = int(uptime // 86400)
    hours = int((uptime % 86400) // 3600)
    minutes = int((uptime % 3600) // 60)
    seconds = int(uptime % 60)
    for i in range(1, 4):
        x = WIDTH // 4 * i
        draw.line([(x, ROW_HEIGHT*1), (x, ROW_HEIGHT*2)], fill=(255, 105, 180), width=1)
    y_center = ROW_HEIGHT*1 + (ROW_HEIGHT - text_height) // 2
    time_segments = [f"{days}D", f"{hours}H", f"{minutes}M", f"{seconds}S"]
    for i in range(4):
        segment = time_segments[i]
        segment_bbox = font.getbbox(segment)
        segment_width = segment_bbox[2] - segment_bbox[0]
        x_pos = WIDTH // 8 * (2 * i + 1) - segment_width // 2
        draw.text((x_pos, y_center), segment, font=font, fill=(255, 255, 255))

    # 第三行 - CPU使用率和温度
    cpu_usage = psutil.cpu_percent(interval=0.1)
    cpu_temp = get_cpu_temp()
    x = WIDTH // 2
    draw.line([(x, ROW_HEIGHT*2), (x, ROW_HEIGHT*3)], fill=(255, 105, 180), width=1)
    y_center = ROW_HEIGHT*2 + (ROW_HEIGHT - text_height) // 2
    cpu_text = f"CPU {cpu_usage}%"
    temp_text = f"Temp {cpu_temp}"
    cpu_bbox = font.getbbox(cpu_text)
    temp_bbox = font.getbbox(temp_text)
    cpu_text_width = cpu_bbox[2] - cpu_bbox[0]
    temp_text_width = temp_bbox[2] - temp_bbox[0]
    draw.text((WIDTH//4 - cpu_text_width//2, y_center), cpu_text, font=font, fill=(255, 255, 255))
    draw.text((3*WIDTH//4 - temp_text_width//2, y_center), temp_text, font=font, fill=(255, 255, 255))

    # 第四行 - 每个核心的使用率
    per_cpu_usage = psutil.cpu_percent(percpu=True)
    if len(per_cpu_usage) < 4:
        per_cpu_usage.extend([0.0] * (4 - len(per_cpu_usage)))
    for i in range(1, 4):
        x = WIDTH // 4 * i
        draw.line([(x, ROW_HEIGHT*3), (x, ROW_HEIGHT*4)], fill=(255, 105, 180), width=1)
    y_center = ROW_HEIGHT*3 + (ROW_HEIGHT - text_height) // 2
    for i in range(4):
        core_text = f"{per_cpu_usage[i]:.0f}%"
        core_bbox = font.getbbox(core_text)
        core_text_width = core_bbox[2] - core_bbox[0]
        draw.text((WIDTH//8*(2*i + 1) - core_text_width//2, y_center), core_text, font=font, fill=(255, 255, 255))

    # 第五行 - RAM占用
    ram_usage = psutil.virtual_memory().percent
    free_memory = psutil.virtual_memory().free / 1024**2  # MB
    x = WIDTH // 2
    draw.line([(x, ROW_HEIGHT*4), (x, ROW_HEIGHT*5)], fill=(255, 105, 180), width=1)
    y_center = ROW_HEIGHT*4 + (ROW_HEIGHT - text_height) // 2
    ram_text = f"RAM {ram_usage}%"
    free_text = f"Free {free_memory:.0f}M"
    ram_bbox = font.getbbox(ram_text)
    free_bbox = font.getbbox(free_text)
    ram_text_width = ram_bbox[2] - ram_bbox[0]
    free_text_width = free_bbox[2] - free_bbox[0]
    draw.text((WIDTH//4 - ram_text_width//2, y_center), ram_text, font=font, fill=(255, 255, 255))
    draw.text((3*WIDTH//4 - free_text_width//2, y_center), free_text, font=font, fill=(255, 255, 255))

    # 第六行 - 内存类型标签
    labels = ["Mem", "Cache", "Swap"]
    for i in range(1, 3):
        x = WIDTH // 3 * i
        draw.line([(x, ROW_HEIGHT*5), (x, ROW_HEIGHT*6)], fill=(255, 105, 180), width=1)
    y_center = ROW_HEIGHT*5 + (ROW_HEIGHT - text_height) // 2
    for i in range(3):
        label_bbox = font.getbbox(labels[i])
        label_text_width = label_bbox[2] - label_bbox[0]
        draw.text((WIDTH//6*(2*i + 1) - label_text_width//2, y_center), labels[i], font=font, fill=(255, 255, 255))

    # 第七行 - 内存使用情况
    memory_info = psutil.virtual_memory()
    swap_memory = psutil.swap_memory().used / 1024**2  # MB
    mem_used = (memory_info.total - memory_info.available) / 1024**2  # MB
    cache_memory = memory_info.cached / 1024**2  # MB
    for i in range(1, 3):
        x = WIDTH // 3 * i
        draw.line([(x, ROW_HEIGHT*6), (x, ROW_HEIGHT*7)], fill=(255, 105, 180), width=1)
    y_center = ROW_HEIGHT*6 + (ROW_HEIGHT - text_height) // 2
    mem_text = f"{mem_used:.0f}M"
    cache_text = f"{cache_memory:.0f}M"
    swap_text = f"{swap_memory:.0f}M"
    mem_bbox = font.getbbox(mem_text)
    cache_bbox = font.getbbox(cache_text)
    swap_bbox = font.getbbox(swap_text)
    mem_text_width = mem_bbox[2] - mem_bbox[0]
    cache_text_width = cache_bbox[2] - cache_bbox[0]
    swap_text_width = swap_bbox[2] - swap_bbox[0]
    draw.text((WIDTH//6 - mem_text_width//2, y_center), mem_text, font=font, fill=(255, 255, 255))
    draw.text((WIDTH//6*3 - cache_text_width//2, y_center), cache_text, font=font, fill=(255, 255, 255))
    draw.text((WIDTH//6*5 - swap_text_width//2, y_center), swap_text, font=font, fill=(255, 255, 255))

    # 第八行 - 磁盘使用情况
    disk_usage = psutil.disk_usage('/').percent
    disk_free = psutil.disk_usage('/').free / 1024**3  # GB
    x = WIDTH // 2
    draw.line([(x, ROW_HEIGHT*7), (x, ROW_HEIGHT*8)], fill=(255, 105, 180), width=1)
    y_center = ROW_HEIGHT*7 + (ROW_HEIGHT - text_height) // 2
    disk_text = f"Disk {disk_usage}%"
    free_text = f"Free {disk_free:.1f}G"
    disk_bbox = font.getbbox(disk_text)
    free_bbox = font.getbbox(free_text)
    disk_text_width = disk_bbox[2] - disk_bbox[0]
    free_text_width = free_bbox[2] - free_bbox[0]
    draw.text((WIDTH//4 - disk_text_width//2, y_center), disk_text, font=font, fill=(255, 255, 255))
    draw.text((3*WIDTH//4 - free_text_width//2, y_center), free_text, font=font, fill=(255, 255, 255))

    return image

# 更新网络信息页
def update_network_display():
    image = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))  # 黑色背景
    draw = ImageDraw.Draw(image)

    # 绘制深粉色边框
    draw.rectangle([(0, 0), (WIDTH-1, HEIGHT-1)], outline=(255, 105, 180), width=1)

    # 绘制水平网格线（深粉色）
    for i in range(1, ROWS):
        y = i * ROW_HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=(255, 105, 180), width=1)

    # 获取无线网络信息
    wireless_info = get_wireless_info()

    # 第一行 - wlan0
    text = "wlan0"
    y_center = ROW_HEIGHT // 2
    draw.text((WIDTH // 2 - font.getlength(text) // 2, y_center - font.size // 2), text, font=font, fill=(255, 255, 255))

    # 第二行 - wlan0的IPv4地址
    ip_address = get_ip_address('wlan0')
    y_center = 2 * ROW_HEIGHT - ROW_HEIGHT // 2
    draw.text((WIDTH // 2 - font.getlength(ip_address) // 2, y_center - font.size // 2), ip_address, font=font, fill=(255, 255, 255))

    # 第三行 - gateway
    text = "gateway"
    y_center = 3 * ROW_HEIGHT - ROW_HEIGHT // 2
    draw.text((WIDTH // 2 - font.getlength(text) // 2, y_center - font.size // 2), text, font=font, fill=(255, 255, 255))

    # 第四行 - 网关IP地址
    gateway = get_gateway()
    y_center = 4 * ROW_HEIGHT - ROW_HEIGHT // 2
    draw.text((WIDTH // 2 - font.getlength(gateway) // 2, y_center - font.size // 2), gateway, font=font, fill=(255, 255, 255))

    # 第五行 - ESSID
    essid = wireless_info['essid']
    y_center = 5 * ROW_HEIGHT - ROW_HEIGHT // 2
    text = f"ESSID: {essid}"
    draw.text((WIDTH // 2 - font.getlength(text) // 2, y_center - font.size // 2), text, font=font, fill=(255, 255, 255))

    # 第六行 - Bit Rate
    bit_rate = wireless_info['bit_rate']
    y_center = 6 * ROW_HEIGHT - ROW_HEIGHT // 2
    text = f"Bit Rate: {bit_rate}"
    draw.text((WIDTH // 2 - font.getlength(text) // 2, y_center - font.size // 2), text, font=font, fill=(255, 255, 255))

    # 第七行 - Link Quality
    link_quality = wireless_info['link_quality']
    y_center = 7 * ROW_HEIGHT - ROW_HEIGHT // 2
    text = f"Link Quality: {link_quality}"
    draw.text((WIDTH // 2 - font.getlength(text) // 2, y_center - font.size // 2), text, font=font, fill=(255, 255, 255))

    # 第八行 - Signal level
    signal_level = wireless_info['signal_level']
    y_center = 8 * ROW_HEIGHT - ROW_HEIGHT // 2
    text = f"Signal level: {signal_level}"
    draw.text((WIDTH // 2 - font.getlength(text) // 2, y_center - font.size // 2), text, font=font, fill=(255, 255, 255))

    return image

# 更新Wi-Fi列表页
def update_wifi_list_display():
    image = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))  # 黑色背景
    draw = ImageDraw.Draw(image)

    # 绘制深粉色边框
    draw.rectangle([(0, 0), (WIDTH-1, HEIGHT-1)], outline=(255, 105, 180), width=1)

    # 绘制水平网格线（深粉色）
    for i in range(1, ROWS):
        y = i * ROW_HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=(255, 105, 180), width=1)

    # 获取当前连接的Wi-Fi名称，并解码
    wireless_info = get_wireless_info()  # 获取无线网络信息
    current_wifi_name = wireless_info['essid']  # 使用get_wireless_info()获取的ESSID，该函数内部已经处理了echo -e和解码逻辑

    # 第一行 - 当前连接的Wi-Fi
    text = f"Connected: {current_wifi_name}"
    y_center = ROW_HEIGHT // 2
    draw.text((WIDTH // 2 - font.getlength(text) // 2, y_center - font.size // 2), text, font=font, fill=(255, 255, 255))

    # 如果还没有扫描Wi-Fi列表，显示提示信息
    global wifi_list, wifi_list_scanned, selected_wifi_index, start_wifi_index
    if not wifi_list_scanned:
        # 只显示一条提示信息
        for i in range(1, 8):
            y_center = (i + 1) * ROW_HEIGHT - ROW_HEIGHT // 2
            if i == 1:
                text = "Press KEY3 to scan Wi-Fi"
                draw.text((WIDTH // 2 - font.getlength(text) // 2, y_center - font.size // 2), text, font=font, fill=(255, 255, 255))
            else:
                # 其他行保持空白
                pass
        return image

    # 计算当前显示的Wi-Fi范围
    max_displayed_wifi = 7  # 每页显示7个Wi-Fi
    if len(wifi_list) > max_displayed_wifi:
        if selected_wifi_index < start_wifi_index:
            start_wifi_index = selected_wifi_index
        elif selected_wifi_index >= start_wifi_index + max_displayed_wifi:
            start_wifi_index = selected_wifi_index - max_displayed_wifi + 1

    end_wifi_index = start_wifi_index + max_displayed_wifi
    if end_wifi_index > len(wifi_list):
        end_wifi_index = len(wifi_list)
        start_wifi_index = max(0, end_wifi_index - max_displayed_wifi)

    # 显示周围的Wi-Fi列表
    for i, wifi in enumerate(wifi_list[start_wifi_index:end_wifi_index]):
        if i == selected_wifi_index - start_wifi_index:
            # 选中的Wi-Fi，背景为白色，文字为黑色
            draw.rectangle([(0, (i+2)*ROW_HEIGHT - ROW_HEIGHT), (WIDTH, (i+2)*ROW_HEIGHT)], fill=(255, 255, 255))
            draw.text((WIDTH // 2 - font.getlength(wifi) // 2, (i+2)*ROW_HEIGHT - ROW_HEIGHT // 2 - font.size // 2), wifi, font=font, fill=(0, 0, 0))
        else:
            # 未选中的Wi-Fi，背景为黑色，文字为白色
            draw.text((WIDTH // 2 - font.getlength(wifi) // 2, (i+2)*ROW_HEIGHT - ROW_HEIGHT // 2 - font.size // 2), wifi, font=font, fill=(255, 255, 255))

    return image

# Wi-Fi密码输入页显示
def update_password_input_display():
    global start_key_row  # 声明全局变量
    
    image = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))  # 黑色背景
    draw = ImageDraw.Draw(image)

    # 绘制深粉色边框
    draw.rectangle([(0, 0), (WIDTH-1, HEIGHT-1)], outline=(255, 105, 180), width=1)

    # 绘制水平网格线（深粉色）
    for i in range(1, ROWS):
        y = i * ROW_HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=(255, 105, 180), width=1)

    # 绘制垂直网格线（深粉色）从第二行开始
    for i in range(1, 9):  # 8列
        x = i * (WIDTH // 8)
        for j in range(1, ROWS):  # 从第二行开始
            y_start = j * ROW_HEIGHT
            y_end = (j + 1) * ROW_HEIGHT
            draw.line([(x, y_start), (x, y_end)], fill=(255, 105, 180), width=1)

    # 第一行 - 密码显示区或连接状态区
    if connection_status:
        # 显示连接状态
        text = connection_status
        text_color = (0, 255, 0) if connection_status == "连接成功" else (255, 0, 0)  # 绿色或红色
    else:
        # 显示密码
        text = current_wifi_password
        text_color = (255, 255, 255)  # 白色

    # 计算文本位置
    text_width = font.getlength(text)
    text_height = font.size
    x = (WIDTH - text_width) // 2
    y = (ROW_HEIGHT - text_height) // 2

    draw.text((x, y), text, font=font, fill=text_color)

    # 绘制软键盘
    max_displayed_rows = ROWS - 1  # 最多显示7行软键盘（从第二行开始）
    if len(keyboard_layout) > max_displayed_rows:
        # 检查是否需要滚动
        if selected_key_row < start_key_row:
            start_key_row = selected_key_row
        elif selected_key_row >= start_key_row + max_displayed_rows:
            start_key_row = selected_key_row - max_displayed_rows + 1

    end_key_row = start_key_row + max_displayed_rows
    if end_key_row > len(keyboard_layout):
        end_key_row = len(keyboard_layout)
        start_key_row = max(0, end_key_row - max_displayed_rows)

    for row_idx in range(start_key_row, end_key_row):
        for col_idx, key in enumerate(keyboard_layout[row_idx]):
            x = col_idx * (WIDTH // 8)
            y = (row_idx - start_key_row + 1) * ROW_HEIGHT  # 调整行索引

            # 计算文本的起始位置，确保其居中显示
            key_text_width = font.getlength(key)
            key_text_height = font.size
            key_text_x = x + (WIDTH // 8 - key_text_width) // 2
            key_text_y = y + (ROW_HEIGHT - key_text_height) // 2

            # 是否选中当前键
            if row_idx == selected_key_row and col_idx == selected_key_col:
                # 选中的键，背景为白色，文字为黑色
                draw.rectangle([(x, y), (x + WIDTH // 8, y + ROW_HEIGHT)], fill=(255, 255, 255))
                draw.text((key_text_x, key_text_y), key, font=font, fill=(0, 0, 0))
            else:
                # 未选中的键，背景为黑色，文字为白色
                draw.text((key_text_x, key_text_y), key, font=font, fill=(255, 255, 255))

    return image

# 加载便携命令
def load_commands():
    global cmd_list, cmd_dict
    try:
        import json
        with open(os.path.join(current_dir, 'cmd.json'), 'r') as f:
            cmd_dict = json.load(f)
        cmd_list = list(cmd_dict.keys())
    except Exception as e:
        print(f"加载命令文件失败: {e}")
        cmd_dict = {}
        cmd_list = []

# 更新便携命令页显示
def update_command_display():
    global start_cmd_index  # 关键修复
    image = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))  # 黑色背景
    draw = ImageDraw.Draw(image)

    # 绘制深粉色边框
    draw.rectangle([(0, 0), (WIDTH-1, HEIGHT-1)], outline=(255, 105, 180), width=1)

    # 绘制水平网格线（深粉色）
    for i in range(1, ROWS):
        y = i * ROW_HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=(255, 105, 180), width=1)

    # 第一行 - 页面标题
    draw.text((WIDTH // 2 - font.getlength("便携命令") // 2, ROW_HEIGHT // 2 - font.size // 2), "便携命令", font=font, fill=(255, 255, 255))

    # 如果还没有加载命令，显示提示信息
    if not cmd_list:
        for i in range(1, 8):
            y_center = (i + 1) * ROW_HEIGHT - ROW_HEIGHT // 2
            if i == 1:
                text = "未加载命令文件"
                draw.text((WIDTH // 2 - font.getlength(text) // 2, y_center - font.size // 2), text, font=font, fill=(255, 255, 255))
        return image

    # 计算当前显示的命令范围
    max_displayed_cmds = 7
    if len(cmd_list) > max_displayed_cmds:
        if selected_cmd_index < start_cmd_index:
            start_cmd_index = selected_cmd_index
        elif selected_cmd_index >= start_cmd_index + max_displayed_cmds:
            start_cmd_index = selected_cmd_index - max_displayed_cmds + 1

    end_cmd_index = start_cmd_index + max_displayed_cmds
    if end_cmd_index > len(cmd_list):
        end_cmd_index = len(cmd_list)
        start_cmd_index = max(0, end_cmd_index - max_displayed_cmds)

    # 显示周围的命令列表
    for i, cmd in enumerate(cmd_list[start_cmd_index:end_cmd_index]):
        if i == selected_cmd_index - start_cmd_index:
            # 选中的命令，背景为白色，文字为黑色
            draw.rectangle([(0, (i+2)*ROW_HEIGHT - ROW_HEIGHT), (WIDTH, (i+2)*ROW_HEIGHT)], fill=(255, 255, 255))
            draw.text((WIDTH // 2 - font.getlength(cmd) // 2, (i+2)*ROW_HEIGHT - ROW_HEIGHT // 2 - font.size // 2), cmd, font=font, fill=(0, 0, 0))
        else:
            # 未选中的命令，背景为黑色，文字为白色
            draw.text((WIDTH // 2 - font.getlength(cmd) // 2, (i+2)*ROW_HEIGHT - ROW_HEIGHT // 2 - font.size // 2), cmd, font=font, fill=(255, 255, 255))

    return image

# 显示启动图片
def show_splash_image():
    try:
        # 加载并显示图片
        splash_path = os.path.join(current_dir, 'meimo.png')
        splash_image = Image.open(splash_path)
        
        # 确保图片大小与屏幕匹配
        splash_image = splash_image.resize((WIDTH, HEIGHT), Image.LANCZOS)
        
        # 将图片转换为RGB565格式
        byte_data = rgb_to_rgb565(splash_image)
        
        # 写入帧缓冲设备
        with open('/dev/fb0', 'wb') as fb:
            fb.write(byte_data)
        
        # 显示图片5秒
        time.sleep(5)
    except Exception as e:
        print(f"无法显示启动图片：{e}")

# 获取CPU温度
def get_cpu_temp():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = f.read()
            return f"{float(temp)/1000:.1f}°C"
    except:
        return "N/A"

# 按键处理函数
def handle_button_press():
    global current_page, selected_wifi_index, start_wifi_index, wifi_list, current_wifi_name, wifi_list_scanned, current_wifi_password, selected_key_row, selected_key_col, start_key_row, connection_status
    
    current_values = {}
    
    for name, (chip_name, pin) in buttons.items():
        if chip_name not in chips:
            chips[chip_name] = gpiod.Chip(chip_name)
        line = chips[chip_name].get_line(pin)
        if name not in lines:
            line.request(consumer='button_test', type=gpiod.LINE_REQ_DIR_IN)
            lines[name] = line
        current_values[name] = line.get_value()
    
    # 检测左右按键按下事件
    if current_values.get("Left", 1) == 0 and prev_values.get("Left", 1) == 1:
        if current_page > 0 and current_page != 102:
            current_page -= 1
            print("左键按下，切换到页面", current_page)
    elif current_values.get("Right", 1) == 0 and prev_values.get("Right", 1) == 1:
        if current_page < 3 and current_page != 102:
            current_page += 1
            print("右键按下，切换到页面", current_page)
    
    # 检测上/下按键按下事件（在Wi-Fi列表页有效）
    if current_page == 2:  # Wi-Fi列表页
        if current_values.get("Down", 1) == 0 and prev_values.get("Down", 1) == 1:
            if len(wifi_list) > 0:
                selected_wifi_index = min(selected_wifi_index + 1, len(wifi_list) - 1)
                print("下键按下，选中的Wi-Fi索引:", selected_wifi_index)
        elif current_values.get("Up", 1) == 0 and prev_values.get("Up", 1) == 1:
            if len(wifi_list) > 0:
                selected_wifi_index = max(selected_wifi_index - 1, 0)
                print("上键按下，选中的Wi-Fi索引:", selected_wifi_index)
    
    # 检测KEY3按下事件（刷新Wi-Fi列表或连接Wi-Fi）
    if current_values.get("KEY3", 1) == 0 and prev_values.get("KEY3", 1) == 1:
        if current_page == 2:  # 刷新Wi-Fi列表
            print("KEY3按下，开始刷新Wi-Fi列表")  # 调试信息
            temp_wifi_list = scan_wifi()  # 使用临时变量存储扫描结果
            if temp_wifi_list:  # 检查是否成功扫描到Wi-Fi
                current_wireless_info = get_wireless_info()
                current_wifi_name = current_wireless_info['essid']
                wifi_list = temp_wifi_list
                wifi_list_scanned = True
                # 重置Wi-Fi列表页状态
                start_wifi_index = 0
                selected_wifi_index = 0
                print("Wi-Fi列表已更新:", wifi_list)  # 调试信息
            else:
                print("未扫描到Wi-Fi列表")  # 调试信息
        elif current_page == 102:  # 连接Wi-Fi
            print("KEY3按下，开始连接Wi-Fi")
            connection_result = connect_wifi(wifi_list[selected_wifi_index], current_wifi_password)
            if connection_result:
                connection_status = "连接成功"
            else:
                connection_status = "连接失败"
            # 2秒后自动跳转
            time.sleep(2)
            if connection_status == "连接成功":
                current_page = 1  # 跳转到网络信息页
            else:
                current_page = 2  # 跳转到Wi-Fi列表页
            # 清空密码和连接状态
            current_wifi_password = ""
            selected_key_row = 0
            selected_key_col = 0
            start_key_row = 0
            connection_status = ""
    
    # 检测KEY1按下事件（进入密码输入页或输入密码字符）
    if current_values.get("KEY1", 1) == 0 and prev_values.get("KEY1", 1) == 1:
        if current_page == 2:  # 从Wi-Fi列表页进入密码输入页
            current_page = 102
            current_wifi_password = ""
            selected_key_row = 0
            selected_key_col = 0
            start_key_row = 0
            connection_status = ""  # 重置连接状态
            print("KEY1按下，进入密码输入页")
        elif current_page == 102:  # 在密码输入页输入字符
            selected_char = keyboard_layout[selected_key_row][selected_key_col]
            current_wifi_password += selected_char
            print(f"KEY1按下，输入字符: {selected_char}, 当前密码: {current_wifi_password}")
    
    # 检测KEY2按下事件（退出密码输入页）
    if current_values.get("KEY2", 1) == 0 and prev_values.get("KEY2", 1) == 1 and current_page == 102:
        current_page = 2
        current_wifi_password = ""
        selected_key_row = 0
        selected_key_col = 0
        start_key_row = 0
        connection_status = ""  # 重置连接状态
        print("KEY2按下，退出密码输入页")
    
    # 检测上/下/左/右按键按下事件（在密码输入页有效）
    if current_page == 102:  # 密码输入页
        if current_values.get("Down", 1) == 0 and prev_values.get("Down", 1) == 1:
            selected_key_row = min(selected_key_row + 1, len(keyboard_layout) - 1)
            print("下键按下，选中的键盘行:", selected_key_row)
        elif current_values.get("Up", 1) == 0 and prev_values.get("Up", 1) == 1:
            selected_key_row = max(selected_key_row - 1, 0)
            print("上键按下，选中的键盘行:", selected_key_row)
        elif current_values.get("Right", 1) == 0 and prev_values.get("Right", 1) == 1:
            selected_key_col = min(selected_key_col + 1, len(keyboard_layout[selected_key_row]) - 1)
            print("右键按下，选中的键盘列:", selected_key_col)
        elif current_values.get("Left", 1) == 0 and prev_values.get("Left", 1) == 1:
            selected_key_col = max(selected_key_col - 1, 0)
            print("左键按下，选中的键盘列:", selected_key_col)
    
    # 检测上/下按键按下事件（在便携命令页有效）
    if current_page == 3:  # 便携命令页
        global selected_cmd_index, start_cmd_index  # 添加声明全局变量
        if current_values.get("Down", 1) == 0 and prev_values.get("Down", 1) == 1:
            selected_cmd_index = min(selected_cmd_index + 1, len(cmd_list) - 1)
            print("下键按下，选中的命令索引:", selected_cmd_index)
        elif current_values.get("Up", 1) == 0 and prev_values.get("Up", 1) == 1:
            selected_cmd_index = max(selected_cmd_index - 1, 0)
            print("上键按下，选中的命令索引:", selected_cmd_index)
    # 检测KEY1按下事件（在便携命令页执行命令）
    if current_values.get("KEY1", 1) == 0 and prev_values.get("KEY1", 1) == 1 and current_page == 3:
        if selected_cmd_index < len(cmd_list):
            cmd_name = list(cmd_dict.keys())[selected_cmd_index]
            cmd = cmd_dict[cmd_name]
            try:
                result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print(f"执行命令: {cmd}")
                print(f"输出: {result.stdout.decode()}")
                print(f"错误: {result.stderr.decode()}")
            except Exception as e:
                print(f"执行命令时发生错误: {e}")
    
    prev_values.update(current_values)

# 注册信号处理函数
def signal_handler(sig, frame):
    print("脚本已停止")
    for chip in chips.values():
        chip.close()
    sys.exit(0)

# 注册信号处理函数
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGTSTP, signal_handler)

# 主循环
try:
    # 先显示启动图片
    show_splash_image()

    # 加载便携命令
    load_commands()

    while True:
        # 处理按键
        handle_button_press()
        
        # 根据当前页面索引更新显示
        if current_page == 0:
            image = update_system_display()
        elif current_page == 1:
            image = update_network_display()
        elif current_page == 2:
            image = update_wifi_list_display()
        elif current_page == 3:
            image = update_command_display()
        elif current_page == 102:
            image = update_password_input_display()
        
        # 将图像转换为RGB565格式
        byte_data = rgb_to_rgb565(image)
        
        # 写入帧缓冲设备
        with open('/dev/fb0', 'wb') as fb:
            fb.write(byte_data)
        
        time.sleep(0.5)

except KeyboardInterrupt:
    print("退出程序")
except Exception as e:
    print(f"发生错误：{e}")
