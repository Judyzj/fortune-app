# 命理分析应用后端

基于 Python FastAPI 构建的命理应用后端，提供八字排盘和命理分析功能。

## 功能特性

- 真太阳时转换（根据经纬度自动校正）
- 四柱八字排盘
- 十神计算
- 大运计算
- 集成 Gemini-2.5 进行智能分析
- 绘制人生k线图（0-100运势评分）

## 项目结构

```
fortune_app/
├── calculator.py      # 核心计算逻辑
├── main.py            # FastAPI 服务
├── requirements.txt   # 依赖包
├── .env              # 环境变量配置
├── faq.txt           # 知识库
└── README.md         # 说明文档
```

## 安装步骤

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **配置环境变量**
编辑 `.env` 文件，填入你的 DeepSeek API Key：
```
DEEPSEEK_API_KEY=your_actual_api_key_here
```

3. **运行服务**
```bash
python main.py
```

或者使用 uvicorn：
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API 接口

### POST /api/fortune

命理分析接口，接收用户信息，返回流式分析结果。

**请求体：**
```json
{
  "name": "张三",
  "gender": "male",
  "birth_date": "1990-01-01",
  "birth_time": "12:00",
  "lat": 39.9042,
  "lng": 116.4074,
  "city": "北京"
}
```

**响应格式（Server-Sent Events）：**
```
data: {"type": "text", "content": "分析文本..."}
data: {"type": "chart_data", "data": {"career": [...], "relationship": [...], "wealth": [...]}}
data: {"type": "calculation", "data": {...}}
data: [DONE]
```

### GET /health

健康检查接口，返回服务状态。

## 核心功能说明

### 真太阳时转换

系统会根据用户提供的经纬度，自动将标准时间转换为真太阳时。这是因为古法八字看的是太阳角度，不同经度的地方，太阳时是不同的。

例如：北京时间 12:00 在新疆可能才刚日出，所以需要根据经度进行校正。

### 四柱排盘

根据真太阳时，计算年、月、日、时四柱，每柱由一天干一地支组成。

### 十神计算

以日主（日柱天干）为基准，计算其他天干对应的十神关系。

### 大运计算

根据年柱天干的阴阳和性别，判断大运是顺排还是逆排，计算每10年的大运干支。

## 注意事项

1. 经纬度必须准确，否则真太阳时计算会有偏差
2. 需要有效的 API Key 才能使用分析功能
3. 知识库文件 `faq.txt` 可以根据需要自定义内容

## 开发说明

- `calculator.py`: 包含所有命理计算逻辑，可以独立测试
- `main.py`: FastAPI 服务，处理 HTTP 请求和流式响应
- 系统会自动从 `faq.txt` 加载知识库内容到 AI 提示词中
