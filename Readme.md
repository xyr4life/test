# 彩票号码推荐 Demo（Python 本地可运行）

这个仓库现在提供了一个可以直接本地运行的最小示例：
- 后端：FastAPI
- 前端：HTML + JS + CSS
- 功能：点击按钮生成 5 组双色球候选号码（带评分）

> 说明：彩票结果属于随机事件，以下结果仅供学习/演示，不保证中奖。

## 1) 本地运行

### 方式 A：Anaconda / Miniconda（推荐给你）

```bash
conda create -n lottery-demo python=3.10 -y
conda activate lottery-demo
pip install -r requirements.txt
# 先准备真实历史数据 CSV（见下方“2) 真实数据准备”）
uvicorn app:app --reload
```


启动后打开：
- http://127.0.0.1:8000

## 2) 真实数据准备

程序已改为**只读取真实历史开奖数据**，不再使用随机模拟历史。

默认读取路径：`data/ssq_history.csv`（可通过环境变量 `SSQ_HISTORY_CSV` 覆盖）。

### CSV 格式（任选一种）

格式 A（推荐）：

```csv
issue,date,red1,red2,red3,red4,red5,red6,blue
2024001,2024-01-02,3,8,12,19,24,31,9
```

格式 B：

```csv
issue,date,red,blue
2024001,2024-01-02,"03 08 12 19 24 31",9
```

> 说明：上面只展示格式示例，实际请替换为你收集的真实历史开奖数据。

### 启动前检查

- 确保文件存在：`data/ssq_history.csv`
- 红球范围 `1-33` 且不重复，共 6 个
- 蓝球范围 `1-16`

## 3) API 示例

### `POST /api/predict`

请求：

```json
{
  "lotteryType": "ssq",
  "count": 5
}
```

返回示例：

```json
{
  "modelVersion": "demo-rule-v2-real-data",
  "generatedAt": "2026-03-12T10:00:00",
  "numbers": [
    {"red": [3, 8, 12, 19, 24, 31], "blue": 9, "score": 1.934}
  ],
  "disclaimer": "仅供娱乐，不保证中奖。彩票具有随机性，请理性看待。"
}
```

## 4) 代码结构

- `app.py`：FastAPI 服务、评分器、接口
- `templates/index.html`：前端页面和按钮逻辑
- `static/style.css`：页面样式
- `requirements.txt`：依赖

## 5) 当前评分逻辑（baseline）

后端会随机采样大量合法号码组合，并按规则打分后取 Top 5：
- 历史频率得分（红球/蓝球）
- 和值靠近中心区间加分
- 奇偶均衡加分
- 跨度在常见区间加分
- 连号过多扣分

你后续可以把这部分替换成 LightGBM/XGBoost 排序模型。

## 6) 如何把这 5 个文件下载到你本地

如果你只想拿到这次生成的 5 个核心文件（`app.py`、`requirements.txt`、`Readme.md`、`templates/index.html`、`static/style.css`），推荐下面三种方式。

### 方式 A：直接 `git clone`（最推荐）

```bash
git clone <你的仓库地址>
cd <仓库目录>
```

这样会把完整项目都拉到本地，后续更新也方便。

### 方式 B：打包 zip 再下载

```bash
cd /workspace/test
zip -r lottery_prediction.zip Readme.md app.py requirements.txt static/ templates/
```

执行后会得到 `lottery_prediction.zip`，下载并解压即可。

### 方式 C：只复制单个文件

如果你用的是 VS Code Remote、SSH 或文件管理器，也可以直接逐个下载这 5 个文件：

- `app.py`
- `requirements.txt`
- `Readme.md`
- `templates/index.html`
- `static/style.css`

> 小提示：如果你告诉我你现在是用 GitHub 网页、VS Code 还是服务器 SSH，我可以给你对应的一步一步截图式操作说明。
