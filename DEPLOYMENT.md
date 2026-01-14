# 部署指南

## 前置说明

⚠️ **重要提示**：
- Vercel 主要用于部署前端（React/Vite 应用）
- 后端（Python FastAPI）需要单独部署到其他平台，如：
  - Railway (https://railway.app)
  - Render (https://render.com)
  - Fly.io (https://fly.io)
  - 或其他支持 Python 的云服务

## 部署步骤

### 1. 推送代码到 GitHub

```bash
# 1. 初始化 Git（已完成）
git init

# 2. 添加所有文件（已完成）
git add .

# 3. 提交代码
git commit -m "Initial commit: Fortune App"

# 4. 在 GitHub 上创建新仓库（通过网页或命令行）
#    访问 https://github.com/new 创建新仓库，例如命名为 "fortune-app"

# 5. 添加远程仓库并推送
git remote add origin https://github.com/YOUR_USERNAME/fortune-app.git
git branch -M main
git push -u origin main
```

### 2. 在 Vercel 上部署前端

1. **访问 Vercel**
   - 打开 https://vercel.com
   - 使用 GitHub 账号登录

2. **导入项目**
   - 点击 "Add New Project"
   - 选择你刚才创建的 GitHub 仓库
   - 点击 "Import"

3. **配置项目**
   - **Framework Preset**: 选择 "Vite" 或 "Other"
   - **Root Directory**: 设置为 `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`

4. **环境变量配置**
   - 在 "Environment Variables" 中添加：
     - `VITE_API_BASE_URL`: 你的后端 API 地址
       - 如果后端部署在 Railway: `https://your-app.railway.app`
       - 如果后端部署在 Render: `https://your-app.onrender.com`
       - 如果后端还在本地: `http://localhost:8000`（仅用于测试）

5. **部署**
   - 点击 "Deploy"
   - 等待部署完成（通常 1-2 分钟）

6. **获取访问链接**
   - 部署完成后，Vercel 会提供一个类似 `https://your-app.vercel.app` 的链接
   - 这个链接可以分享给其他人访问

### 3. 部署后端（可选，如果需要）

#### 使用 Railway 部署后端

1. 访问 https://railway.app
2. 使用 GitHub 登录
3. 点击 "New Project" -> "Deploy from GitHub repo"
4. 选择你的仓库
5. 配置环境变量：
   - `DEEPSEEK_API_KEY`: 你的 DeepSeek API Key
   - 其他必要的环境变量
6. Railway 会自动检测 Python 项目并部署

#### 使用 Render 部署后端

1. 访问 https://render.com
2. 使用 GitHub 登录
3. 点击 "New" -> "Web Service"
4. 选择你的仓库
5. 配置：
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. 添加环境变量
7. 点击 "Create Web Service"

## 注意事项

1. **CORS 配置**：确保后端允许来自 Vercel 域名的跨域请求
2. **API 地址**：前端部署后，记得在 Vercel 环境变量中设置正确的后端 API 地址
3. **数据库**：如果使用 SQLite，考虑迁移到 PostgreSQL 或其他云数据库
4. **HTTPS**：Vercel 自动提供 HTTPS，后端也需要支持 HTTPS

## 更新部署

每次代码更新后：

```bash
git add .
git commit -m "Update: 描述你的更改"
git push origin main
```

Vercel 会自动检测 GitHub 的更新并重新部署。
