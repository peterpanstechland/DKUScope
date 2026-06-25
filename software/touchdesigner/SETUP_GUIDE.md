# TouchDesigner 上手指南 — DKUScope 投影映射

> 适合零基础用户。读完这份指南你就能跑起整个投影可视化系统。

---

## 目录

1. [需要什么](#需要什么)
2. [系统架构一句话版](#系统架构一句话版)
3. [快速开始（推荐：自动建网）](#快速开始推荐自动建网)
4. [手动逐步搭建](#手动逐步搭建)
5. [投影校准](#投影校准)
6. [常见问题 / 报错排查](#常见问题--报错排查)
7. [网络结构说明](#网络结构说明)

---

## 需要什么

| 工具 | 版本要求 | 说明 |
|------|----------|------|
| **TouchDesigner** | 2022.28000 或更新 | 免费版（非商业）即可 |
| **Python 服务器** | 已在 `software/python/` | 摄像头识别 + WebSocket 服务端 |
| **numpy** | 已内置于 TD | 不需要单独安装 |

**下载 TouchDesigner：** https://derivative.ca/download

---

## 系统架构一句话版

```
摄像头 → Python识别 → WebSocket → TouchDesigner → 投影仪
         (port 8765)   (ws_receiver DAT)   (grid_render_top → 投影)
```

Python 服务器每秒推送 5-10 次 JSON 消息，TD 实时接收并渲染 16×16 彩色格子投影。

---

## 快速开始（推荐：自动建网）

这是最简单的方法，**一条命令** 自动在 TD 里创建好所有节点。

### 第一步：启动 Python 服务器

```bash
cd software/python
python main.py
```

等到 UI 窗口出现，确认摄像头已连接并开始识别。

### 第二步：打开 TouchDesigner

1. 打开 TD，新建一个空项目（File → New）
2. 进入默认的 `/project1` 组件

### 第三步：运行自动建网脚本（两步法）

**Step A — 在 Textport 里粘贴这一行**（直接输入，不用 exec）：

```python
t = op('/project1').create(textDAT, 'dku_builder'); t.text = open('C:/Users/Twink/OneDrive/Documents/Robomon/DKUScope/software/touchdesigner/bootstrap/create_network.py').read()
```

按 Enter 执行后，Node Graph 里会出现一个黄色的 **`dku_builder`** Text DAT。

**Step B — 右键 `dku_builder` → Run Script**

在 Node Graph 里右键点击刚创建的 `dku_builder` 节点，选择 **Run Script**。

> **为什么要两步？**  
> TD 的算子类型（`websocketDAT`、`tableDAT` 等）只在 DAT 脚本上下文里可用。  
> 直接在 Textport 用 `exec()` 执行文件时，这些类型不在作用域内，会报 `NameError`。  
> 把脚本放进 Text DAT 再运行，就解决了这个问题。

3. 看到以下输出说明成功：
   ```
   ============================================================
   DKUScope — Building TD network...
   ============================================================
     ✓ ws_receiver
     ✓ ws_callbacks
     ✓ grid_state_table
     ✓ grid_render_script
     ✓ grid_render_top
     ✓ level_top
     ✓ null_output
   Network created successfully!
   ```

### 第四步：查看效果

- 在 Node Graph 里找到 `grid_render_top`，双击打开，应该看到 960×960 的彩色格子图
- 如果 Python 服务器有数据推送，格子颜色会实时变化

### 第五步：全屏投影输出

1. 在 Node Graph 空白处右键 → Add Operator → Window COMP
2. 将 `null_output` 的输出连接到 Window COMP 的输入
3. 在 Window COMP 的 Parameters 里：
   - `Open in Perform Mode` → 勾选
   - 选择投影仪对应的显示器
4. 按 **F1** 进入 Perform 模式（全屏）

---

## 手动逐步搭建

如果你想了解每个节点的作用，可以手动创建：

### 节点 1：WebSocket DAT（接收数据）

1. Node Graph 空白处右键 → Add Operator → DAT → **WebSocket**
2. 命名为 `ws_receiver`
3. Parameters：
   - **Active** (`active`) → On
   - **Net Address** (`netaddress`) → `localhost`
   - **Port** (`port`) → `8765`

### 节点 2：ws_callbacks（Text DAT，解析 JSON）

1. 右键 → Add Operator → DAT → **Text**
2. 命名为 `ws_callbacks`
3. 把 `software/touchdesigner/scripts/ws_callbacks.py` 的全部内容粘贴进去
4. 回到 `ws_receiver` 的 Parameters → **Callbacks DAT** → 填写 `ws_callbacks`

### 节点 3：grid_state_table（Table DAT，存储格子状态）

1. 右键 → Add Operator → DAT → **Table**
2. 命名为 `grid_state_table`
3. 用代码初始化（在 Textport 输入）：
   ```python
   t = op('grid_state_table')
   t.clear()
   for _ in range(16):
       t.appendRow([8]*16)
   ```

### 节点 4：grid_render_script（Text DAT，渲染代码）

1. 右键 → Add Operator → DAT → **Text**
2. 命名为 `grid_render_script`
3. 把 `software/touchdesigner/scripts/grid_render_script_top.py` 的全部内容粘贴进去

### 节点 5：grid_render_top（Script TOP，生成图像）

1. 右键 → Add Operator → TOP → **Script**
2. 命名为 `grid_render_top`
3. Parameters：
   - **Callbacks** (`callbacks`) → `grid_render_script`

### 节点 6-7：Level TOP + Null TOP

1. 右键 → TOP → **Level**，命名 `level_top`，连接 `grid_render_top` 的输出
2. 右键 → TOP → **Null**，命名 `null_output`，连接 `level_top` 的输出

---

## 投影校准

当投影仪和桌子物理对齐后，需要做映射校准：

### 使用 Python UI 做校准

1. 在 Python UI（`main.py`）里点击 **投影校准** 按钮
2. 按界面提示对齐投影仪到棋盘格
3. 校准结果会保存到 `software/python/config/project_config.json` 的 `projection.warp_matrix` 字段

### 在 TD 里加载 warp matrix

在 `grid_render_top` 和 `null_output` 之间插入一个 **Warp TOP** 或 **GLSL TOP** 来应用校准矩阵：

```python
# 在 Textport 或 Script DAT 里加载 warp matrix
import json, os

config_path = 'C:/path/to/DKUScope/software/python/config/project_config.json'
with open(config_path) as f:
    config = json.load(f)

warp_matrix = config['projection']['warp_matrix']
print('Warp matrix:', warp_matrix)
# 将此 3×3 矩阵应用到 Warp TOP 的 Source Points 参数
```

> **注意：** 投影仪、桌子、摄像头三者位置固定后才做校准；移动了任何一个都需要重新校准。

---

## 常见问题 / 报错排查

### Q: grid_render_top 全黑/无输出

- 检查 `grid_state_table` DAT 是否存在，且有 16 行 16 列
- 在 Textport 输入 `op('grid_state_table').numRows` 确认返回 `16`
- 检查 Script TOP 的 **Callbacks** 参数是否指向 `grid_render_script`

### Q: ws_receiver 一直显示 "Connecting"

- 确认 Python 服务器正在运行：`python software/python/main.py`
- 确认端口 8765 没有被防火墙拦截
- Textport 运行：`op('ws_receiver').par.active.pulse()` 重连

### Q: 格子颜色不变，一直是白色（全 Road）

- 白色是 Road（class_id=8）的颜色，是默认值
- 检查 `ws_callbacks` Text DAT 是否有语法错误（红色下划线）
- Textport 运行：`print(op('grid_state_table')[0, 0])` 查看值是否在变化

### Q: 报错 `copyNumpyArray not found`

- TD 版本低于 2022.28000，请升级

### Q: 报错 `numpy not found`

- 在 TD Textport 执行：`import sys; print(sys.version)`
- TD 内置的 Python 已包含 numpy，如果报错说明 Script TOP 的 Python 环境异常，重启 TD

---

## 网络结构说明

```
ws_receiver (WebSocket DAT)
    │  receives JSON from Python at ws://localhost:8765
    │  callbacks → ws_callbacks (Text DAT)
    │
    ▼
grid_state_table (Table DAT)  ── 16 rows × 16 cols ── class_id per cell
    │
    ▼
grid_render_script (Text DAT)  ─── Script TOP source code
    │
    ▼
grid_render_top (Script TOP)   ─── 960×960 px RGBA image
    │  each cell = colour of its building class
    │
    ▼
level_top (Level TOP)          ─── brightness / contrast for projection
    │
    ▼
null_output (Null TOP)         ◄── wire to Window COMP for fullscreen
```

### 各建筑类型颜色对照

| class_id | 类型 | 颜色 | 色值 |
|----------|------|------|------|
| 1 | 教学建筑 Academic | 红色 | `#D73A49` |
| 2 | 体育场地 Sports   | 咖啡色 | `#8B5A2B` |
| 3 | 餐厅建筑 Dining   | 黄色 | `#F2CC0C` |
| 4 | 行政建筑 Admin    | 黑色 | `#2F2F2F` |
| 5 | 生活服务 Residential | 粉色 | `#F7A1C4` |
| 6 | 绿地 Green Space  | 绿色 | `#2EA043` |
| 7 | 水体 Water        | 蓝色 | `#1F6FEB` |
| 8 | 默认道路 Road     | 白色 | `#F5F5F5` |
