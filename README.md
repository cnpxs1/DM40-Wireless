# DM40 Wireless

<p align="center" width="100%">
    <img width="50%" src="images/alientek.png">
</p>

一款 Windows 桌面应用程序，通过**低功耗蓝牙（BLE）**连接无线**正点原子（Alientek）DM40**万用表（支持 DM40A / DM40B / DM40C）。界面完整复现设备显示屏内容，包括测量模式、量程、HOLD 保持状态及已保存的数值。

**仓库地址：** [github.com/Urobotos/DM40-Wireless](https://github.com/Urobotos/DM40-Wireless)

| 分支 | 用途 |
|------|------|
| `main` | 稳定发布版，与 GitHub Releases 同步 |
| `develop` | 活跃开发分支，新功能与问题修复 |

<br>

---

## 环境要求：

- **Windows 10/11** 操作系统，蓝牙（BLE）功能正常
- **正点原子 DM40** 万用表（A / B / C 型），需在有效范围内
- 从源码运行需安装 **Python 3.11+**（[python.org](https://www.python.org/)）—— 安装时请勾选 *将 Python 添加到 PATH*

<br>

---

## 在 Windows 上运行（面向最终用户）：

**1.** 打开 GitHub 上的 [Releases](https://github.com/Urobotos/DM40-Wireless/releases) 页面，下载 **`DM40-Wireless-win64.zip`**

**2.** 将压缩包解压到任意文件夹（如 `C:\Apps\DM40 Wireless\`）

**3.** 运行 **`DM40 Wireless.exe`**

**4.** 首次启动时，将显示**连接**界面 —— 搜索附近的万用表，在列表中选择设备，点击**连接**。MAC 地址将保存至可执行文件所在目录的 `settings.json` 中；下次启动时应用会自动连接。

> 发布包为完整的 `dist\DM40 Wireless` 构建文件夹（exe + 依赖库）。请勿单独移动 `.exe` 文件 —— 它必须与 `_internal` 文件夹及 `images` 目录放在一起。

<br>

---

## 从源码运行（面向开发者）：

```bat
git clone -b develop https://github.com/Urobotos/DM40-Wireless.git
cd DM40-Wireless
install.bat
```

首次运行时，请复制配置模板：

```bat
copy settings.example.json settings.json
```

然后通过以下任一方式启动应用：

| 方式 | 说明 |
|------|------|
| **`DM40 Wireless.bat`** | 推荐方式 —— 运行 `app.pyw`，无控制台窗口（如存在 venv 则自动使用） |
| **`app.pyw`** | 双击运行或执行 `pythonw app.pyw` —— 无控制台窗口 |
| **`app.py`** | 在 PowerShell 中执行 `python app.py` —— 带控制台窗口（用于调试、查看日志） |

<br>

---

## 应用截图：

<p align="left" width="100%">
    <img width="44%" src="images/screenshot_main.png">
    <img width="44%" src="images/screenshot_main2.png">
    <img width="44%" src="images/screenshot_raw_console.png">
    <img width="44%" src="images/screenshot_mini_app.png">
</p>

<br>

---

## 使用说明：

### 连接界面（首次启动 / MAC 地址为空时）：

<img width="39%" src="images/screenshot_connect.png">

- **搜索** —— 扫描附近的 DM40 BLE 设备
- 点击列表行 —— 选中设备
- **连接** —— 保存 MAC 地址与型号，建立连接并进入主界面

### 主界面：

<p align="left" width="100%">
    <img width="54%" src="images/manual.png">
</p>

| 区域 | 功能 |
|------|------|
| **1. AUTO+** | 打开当前模式的**量程界面**菜单 |
| **2. RUN / HOLD** | 切换测量保持状态 |
| **3. 模式按钮** | 循环切换子模式：直流电压/交流电压、直流电流/交流电流、电阻、电容、二极管/通断、频率/温度 |
| **4. 显示数字** | 主显示屏数字 |
| **5. 保存槽位** | 点击**显示数字**区域可将数值保存到槽位（最多 6 个），长按显示数字区域可清空槽位 |
| **6. 图表** | 实时测量曲线（迷你应用模式下隐藏），长按图表区域可清空图表 |
| **7. 设置** ⚙️ | 打开**设置界面** |
| **8. REL 按钮** | REL = **相对值模式**，点击启用，长按按钮取消 |

连接状态、万用表电量及单位信息通过实时 BLE 数据显示在顶部栏中。

### 量程界面：

<img width="39%" src="images/screenshot_range.png">

- 显示当前测量模式下的可用量程列表（取决于 DM40A/B/C 型号）
- **返回** —— 回到主界面

### 设置界面：

<img width="39%" src="images/screenshot_settings.png">

| 开关项 | 功能 |
|--------|------|
| **迷你应用** | 缩小窗口，隐藏图表和保存槽位 |
| **窗口置顶** | 将窗口保持在其它应用之上 |
| **RAW 数据控制台** | 在界面下方显示 BLE 收发数据包面板（用于协议调试） |

修改后的设置将保存至 `settings.json`。

<br>

---

## 配置文件（`settings.json`）：

该文件位于 exe 所在目录或项目根目录下。该文件不纳入 Git 版本管理 —— 请使用 `settings.example.json` 作为模板。

| 键名 | 含义 |
|------|------|
| `target_mac` | DM40 MAC 地址（`""` = 显示连接界面） |
| `model_name` | 型号：`DM40A`、`DM40B` 或 `DM40C` |
| `device_counts` | 量程计数比例（40k / 50k / 60k） |
| `window_scale` | 窗口缩放比例（`1.0` = 480×300 逻辑像素） |
| `mini_app` | 迷你模式 |
| `always_on_top` | 窗口置顶 |
| `raw_console` | RAW 数据控制台 |

<br>

---

## 构建 exe 及发布包（面向维护者）：

```bat
build_exe.bat
release_zip.bat
```

- **`build_exe.bat`** —— 使用 PyInstaller `--onedir` 模式打包，输出目录：`dist\DM40 Wireless\`
- **`release_zip.bat`** —— 生成 `release\DM40-Wireless-win64.zip`，用于 GitHub Releases 发布

在 GitHub 上发布版本的步骤：

1. 构建 exe 及 zip 包（见上文）。
2. 在 `main` 分支上创建新的 Release，标签格式如 `v1.0.0`。
3. 将 **`DM40-Wireless-win64.zip`** 作为发布资产上传。
4. 源代码保留在仓库中；用户下载 zip 包使用，开发者克隆仓库进行开发。

<br>

---

## 项目结构：

```
DM40-Wireless/
├── app.py / app.pyw      # 入口文件
├── ble/                  # BLE 工作线程、设备发现
├── core/                 # 协议解析、数据解析、模式定义
├── gui/                  # Tkinter 用户界面
├── images/               # UI 图片资源
├── settings.example.json
├── install.bat
├── build_exe.bat
└── release_zip.bat
```

<br>

---

## 注意事项：

- 本项目并非正点原子（Alientek）官方产品，属于社区 / 爱好者项目。
- Windows 系统须开启蓝牙功能；若蓝牙未开启，应用将显示警告提示。

<br>

---

## 许可证：

<p align="center">
     <strong>本项目基于 MIT 许可证开源 —— 版权所有 © 2026 Urobotos。</strong>
</p>

<p align="center">
    <img width="100" src="images/bin_urobotos.png" alt="Urobotos logo">
</p>

<br>

&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;  &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; [MIT 许可证](LICENSE)
<br>
<br>
