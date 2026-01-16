# 📦 版本信息汇总

## 🐍 Python 版本

- **当前使用**: Python 3.9.6
- **Python 路径**: `/Library/Developer/CommandLineTools/usr/bin/python3`
- **runtime.txt 指定**: Python 3.11（用于生产环境部署）

## 🔧 后端依赖包版本

### 核心框架
- **FastAPI**: 0.104.1
- **Uvicorn**: 0.24.0 (with standard extras)

### 数据验证
- **Pydantic**: 2.12.5
- **pydantic-core**: 2.41.5 (自动安装的依赖)

### 八字计算
- **lunar-python**: 1.3.0

### HTTP 客户端
- **httpx**: 0.28.1

### 环境变量管理
- **python-dotenv**: 1.0.0

### 数据库
- **SQLAlchemy**: 2.0.23
- **psycopg2-binary**: 2.9.9 (仅在使用 PostgreSQL 时需要，当前使用 SQLite 未安装)

### AI 客户端
- **google-genai**: 1.47.0

## 🎨 前端依赖版本

### 核心框架
- **React**: ^18.2.0
- **React DOM**: ^18.2.0
- **React Router DOM**: ^6.20.0

### UI 组件
- **lucide-react**: ^0.294.0 (图标库)
- **framer-motion**: ^12.25.0 (动画库)
- **clsx**: ^2.1.1 (类名工具)
- **tailwind-merge**: ^3.4.0 (Tailwind CSS 合并工具)

### 图表库
- **echarts**: ^6.0.0
- **recharts**: ^3.6.0

### Markdown 渲染
- **react-markdown**: ^10.1.0
- **remark-gfm**: ^4.0.1 (GitHub Flavored Markdown)

### 开发工具
- **Vite**: ^5.0.8 (构建工具)
- **@vitejs/plugin-react**: ^4.2.1
- **Tailwind CSS**: ^3.3.6
- **PostCSS**: ^8.4.32
- **Autoprefixer**: ^10.4.16
- **@types/react**: ^18.2.43
- **@types/react-dom**: ^18.2.17

## 🛠️ 其他工具版本

- **Node.js**: v24.12.0
- **npm**: 11.6.2
- **Git**: 2.50.1 (Apple Git-155)
- **pip**: 21.2.4 (建议升级到 25.3)

## 📋 requirements.txt 完整内容

```
# FastAPI 框架
fastapi==0.104.1
uvicorn[standard]==0.24.0

# 数据验证
pydantic==2.12.5

# 八字计算（lunar-java 的 Python 版本）
lunar-python==1.3.0

# HTTP 客户端（用于调用 DeepSeek API）
httpx==0.28.1

# 环境变量管理
python-dotenv==1.0.0

# 数据库 ORM
sqlalchemy==2.0.23

# PostgreSQL 驱动（用于生产环境）
psycopg2-binary==2.9.9

# Google GenAI 客户端（用于 Compass API）
google-genai==1.47.0
```

## ⚠️ 版本差异说明

### 已安装 vs requirements.txt
- ✅ **匹配**: fastapi, uvicorn, lunar-python, python-dotenv, sqlalchemy, google-genai
- ✅ **已更新**: pydantic (2.12.5), httpx (0.28.1) - 已更新到实际工作版本
- ⚠️ **未安装**: psycopg2-binary (仅在使用 PostgreSQL 时需要)

### Python 版本
- **开发环境**: Python 3.9.6
- **生产环境**: Python 3.11 (runtime.txt 指定)

## 🔄 版本更新历史

- **2025-01-15**: 更新 google-genai 从 0.2.2 → 1.47.0
- **2025-01-15**: 更新 pydantic 从 2.5.0 → 2.12.5
- **2025-01-15**: 更新 httpx 从 0.25.2 → 0.28.1

---

**最后更新**: 2025-01-15
