import gpiod
import time
import signal
import sys
from PIL import Image, ImageDraw

# 按钮配置：格式为 (芯片名称, 引脚编号)
buttons = {
    "Left": ("gpiochip3", 11),     # GPIO3_B3
    "Up": ("gpiochip3", 12),       # GPIO3_B4
    "Press": ("gpiochip3", 19),   # GPIO3_C3
    "Down": ("gpiochip3", 4),    # GPIO3_A4
    "Right": ("gpiochip1", 4),    # GPIO1_A4
    "KEY3": ("gpiochip3", 7),     # GPIO3_A7
    "KEY2": ("gpiochip3", 6),     # GPIO3_A6
    "KEY1": ("gpiochip3", 5)      # GPIO3_A5
}

# 打开 GPIO 芯片并配置引脚为输入模式
chips = {}
lines = {}
prev_values = {}  # 用于存储每个按钮的前一个状态

# 设置屏幕大小
WIDTH, HEIGHT = 240, 240

# 创建一个图像和绘图对象
image = Image.new("RGB", (WIDTH, HEIGHT), "BLACK")  # 黑色背景
draw = ImageDraw.Draw(image)

# 绘制背景
def draw_background():
    # 绘制摇杆图（左侧）
    center_x, center_y = WIDTH // 4, HEIGHT // 2
    pad_size = 80
    # 方向指示三角形，填充黑色
    draw.polygon([(center_x - 10, center_y - pad_size//2), (center_x, center_y - pad_size//2 - 15), (center_x + 10, center_y - pad_size//2)], outline=(255,255,255), fill="BLACK")  # 上
    draw.polygon([(center_x - pad_size//2, center_y - 10), (center_x - pad_size//2 - 15, center_y), (center_x - pad_size//2, center_y + 10)], outline=(255,255,255), fill="BLACK")  # 左
    draw.polygon([(center_x + pad_size//2, center_y - 10), (center_x + pad_size//2 + 15, center_y), (center_x + pad_size//2, center_y + 10)], outline=(255,255,255), fill="BLACK")  # 右
    draw.polygon([(center_x - 10, center_y + pad_size//2), (center_x, center_y + pad_size//2 + 15), (center_x + 10, center_y + pad_size//2)], outline=(255,255,255), fill="BLACK")  # 下
    draw.chord((center_x - 15, center_y - 15, center_x + 15, center_y + 15), 0, 360, outline=(255,255,255), fill="BLACK")  # 中间按钮

    # 绘制KEY按钮（右侧），填充黑色
    key_x = WIDTH * 3 // 4
    key_width, key_height = 60, 30
    key_y = [HEIGHT // 4 - key_height//2, HEIGHT//2 - key_height//2, HEIGHT*3//4 - key_height//2]
    for i in range(3):
        draw.rectangle((key_x - key_width//2, key_y[i], key_x + key_width//2, key_y[i] + key_height), outline=(255,255,255), fill="BLACK")

# 绘制按钮状态
def draw_button_state(name, pressed):
    # 按钮颜色（绿色表示按下）
    color = (0, 255, 0)  # 绿色
    center_x, center_y = WIDTH // 4, HEIGHT // 2
    pad_size = 80
    key_x = WIDTH * 3 // 4
    key_width, key_height = 60, 30
    key_y = [HEIGHT // 4 - key_height // 2, HEIGHT // 2 - key_height // 2, HEIGHT * 3 // 4 - key_height // 2]

    # 如果按钮被按下，填充绿色
    if pressed:
        if name == "Up":
            draw.polygon([(center_x - 10, center_y - pad_size//2), (center_x, center_y - pad_size//2 - 15), (center_x + 10, center_y - pad_size//2)], outline=(255,255,255), fill=color)
        elif name == "Left":
            draw.polygon([(center_x - pad_size//2, center_y - 10), (center_x - pad_size//2 - 15, center_y), (center_x - pad_size//2, center_y + 10)], outline=(255,255,255), fill=color)
        elif name == "Right":
            draw.polygon([(center_x + pad_size//2, center_y - 10), (center_x + pad_size//2 + 15, center_y), (center_x + pad_size//2, center_y + 10)], outline=(255,255,255), fill=color)
        elif name == "Down":
            draw.polygon([(center_x - 10, center_y + pad_size//2), (center_x, center_y + pad_size//2 + 15), (center_x + 10, center_y + pad_size//2)], outline=(255,255,255), fill=color)
        elif name == "Press":
            draw.chord((center_x - 15, center_y - 15, center_x + 15, center_y + 15), 0, 360, outline=(255,255,255), fill=color)
        elif name == "KEY1":
            draw.rectangle((key_x - key_width // 2, key_y[0], key_x + key_width // 2, key_y[0] + key_height), outline=(255,255,255), fill=color)
        elif name == "KEY2":
            draw.rectangle((key_x - key_width // 2, key_y[1], key_x + key_width // 2, key_y[1] + key_height), outline=(255,255,255), fill=color)
        elif name == "KEY3":
            draw.rectangle((key_x - key_width // 2, key_y[2], key_x + key_width // 2, key_y[2] + key_height), outline=(255,255,255), fill=color)

# 将图像转换为 RGB565 格式，确保字节序正确
def rgb_to_rgb565(image):
    result = bytearray()
    for pixel in image.getdata():
        r, g, b = pixel[:3]
        red = (r >> 3) & 0x1F
        green = (g >> 2) & 0x3F
        blue = (b >> 3) & 0x1F
        rgb565 = (red << 11) | (green << 5) | blue
        result.append(rgb565 & 0xFF)
        result.append((rgb565 >> 8) & 0xFF)
    return result

def signal_handler(sig, frame):
    print("\n脚本已停止")
    draw_background()
    byte_data = rgb_to_rgb565(image)
    with open("/dev/fb0", "wb") as fb:
        fb.write(byte_data)
    for chip in chips.values():
        chip.close()
    sys.exit(0)

# 注册信号处理函数
signal.signal(signal.SIGTSTP, signal_handler)

def detect_button_press():
    try:
        # 初始绘制背景
        draw_background()
        # 获取GPIO芯片和引脚
        for name, (chip_name, pin) in buttons.items():
            if chip_name not in chips:
                chips[chip_name] = gpiod.Chip(chip_name)
            line = chips[chip_name].get_line(pin)
            line.request(consumer='button_test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
            lines[name] = line
            prev_values[name] = line.get_value()

        while True:
            # 先重绘背景，清除所有按钮状态
            draw_background()
            # 检测每个按钮的状态并绘制
            for name, line in lines.items():
                current_value = line.get_value()
                if current_value != prev_values[name]:
                    if current_value == 0:  # 按钮被按下
                        print(f"按钮 {name} 被按下")
                    else:  # 按钮被松开
                        print(f"按钮 {name} 被松开")
                    prev_values[name] = current_value
                # 根据按钮的当前状态绘制按钮
                draw_button_state(name, current_value == 0)
            # 将图像转换为 RGB565 格式并写入帧缓冲设备
            byte_data = rgb_to_rgb565(image)
            with open("/dev/fb0", "wb") as fb:
                fb.write(byte_data)
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n测试结束")
        draw_background()  # 恢复初始背景
        byte_data = rgb_to_rgb565(image)
        with open("/dev/fb0", "wb") as fb:
            fb.write(byte_data)
        for chip in chips.values():
            chip.close()

if __name__ == "__main__":
    detect_button_press()