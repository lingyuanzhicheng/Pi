### Pi Tool Python

一个基于Waveshare 1.3inch LCD HAT开发的设备小工具。

#### 交互页面

1、设备状态页（系统版本、运行时间、CPU占用、芯片温度、核心占用、内存占用、空闲内存、使用内存、缓存内存、交换内存、硬盘占用、空闲硬盘）
2、网络信息页（wlan0网口IP、wlan0网关IP、连接WiFi名称、比特率、链路质量、信号质量）
3、WiFi列表页&密码输入页（用于显示当前连接的WiFi与周围可以连接的WiFi，选择需要连接的WiFi进行连接）
4、便捷命令页（一键执行需要执行的命令）

#### 交互说明

摇杆的上下左右是控制上下左右选择的。
KEY1是确认、KEY2是取消。KEY3是特殊按键（如密码输入页里的确认密码，进行连接）。

### 环境配置

请根据情况自行修改相关内容。如`/etc/systemd/system/PiToolPython.service`文件里的`ExecStart`与`WorkingDirectory`部分。

```
sudo apt-get install python3-pip
pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
sudo pip3 install pillow
sudo apt-get install python3-libgpiod
sudo apt install net-tools
sudo apt install wireless-tools
sudo nano PiToolPython.service
mv PiToolPython.service /etc/systemd/system/
sudo chmod -R 777 /etc/systemd/system/PiToolPython.service
sudo systemctl daemon-reload
sudo systemctl enable PiToolPython.service
sudo systemctl start PiToolPython.service
```