# 🔄 后端部署替代方案

## ⚠️ Railway 限制问题

Railway 的免费计划可能有限制，只允许部署数据库，不允许部署应用服务。

## 🚀 替代方案

### 方案 1: Render（推荐，完全免费）⭐

**优点：**
- ✅ 完全免费（有免费套餐）
- ✅ 支持 Python/FastAPI
- ✅ 自动部署
- ✅ 支持环境变量

**缺点：**
- ⚠️ 免费套餐有休眠机制（15分钟无活动后休眠）
- ⚠️ 首次启动可能较慢

**部署步骤：**

1. **访问 Render**：https://render.com
2. **注册/登录**：使用 GitHub 账号登录
3. **创建新服务**：
   - 点击 "New" → "Web Service"
   - 选择你的 `fortune-app` GitHub 仓库
4. **配置服务**：
   - **Name**: `fortune-app-backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: 选择 "Free"
5. **添加环境变量**：
   - `COMPASS_API_KEY`: 你的 API key
   - `ALLOWED_ORIGINS`: `https://fortune-app.vercel.app`（部署前端后更新）
6. **点击 "Create Web Service"**
7. **等待部署完成**（可能需要 5-10 分钟）
8. **获取服务地址**：Render 会提供一个 URL，如 `https://fortune-app.onrender.com`

### 方案 2: Fly.io（性能好）

**优点：**
- ✅ 性能优秀
- ✅ 全球分布
- ✅ 有免费额度

**缺点：**
- ⚠️ 配置稍复杂
- ⚠️ 需要安装 Fly CLI

**部署步骤：**

1. **访问 Fly.io**：https://fly.io
2. **注册账号**
3. **安装 Fly CLI**：
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```
4. **登录**：
   ```bash
   fly auth login
   ```
5. **初始化项目**：
   ```bash
   cd /Users/zijun.yan/fortune_app
   fly launch
   ```
6. **配置环境变量**：
   ```bash
   fly secrets set COMPASS_API_KEY=你的key
   fly secrets set ALLOWED_ORIGINS=https://fortune-app.vercel.app
   ```
7. **部署**：
   ```bash
   fly deploy
   ```

### 方案 3: PythonAnywhere（简单但有限制）

**优点：**
- ✅ 简单易用
- ✅ 有免费套餐

**缺点：**
- ⚠️ 免费套餐限制较多
- ⚠️ 需要手动配置

### 方案 4: 升级 Railway 计划

如果你想继续使用 Railway：

1. **点击 "Upgrade your plan"**
2. **选择付费计划**（通常 $5/月起）
3. **然后可以部署应用服务**

## 🎯 推荐：使用 Render

**为什么推荐 Render：**
- ✅ 完全免费
- ✅ 配置简单
- ✅ 自动部署
- ✅ 适合小型项目

**部署后：**
- 获取 Render 提供的 URL（如 `https://fortune-app.onrender.com`）
- 在 Vercel 前端环境变量中设置：`VITE_API_BASE_URL` = Render URL
- 在 Render 环境变量中设置：`ALLOWED_ORIGINS` = Vercel 前端地址

## 📋 Render 详细部署步骤

### 1. 访问 Render

打开：https://render.com

### 2. 注册/登录

- 点击 "Get Started for Free"
- 选择 "Sign up with GitHub"
- 授权 Render 访问你的 GitHub

### 3. 创建 Web Service

1. 登录后，点击 "New" → "Web Service"
2. 选择你的 `fortune-app` 仓库
3. 点击 "Connect"

### 4. 配置服务

填写以下信息：

- **Name**: `fortune-app-backend`（或你喜欢的名字）
- **Region**: 选择离你最近的区域（如 `Singapore`）
- **Branch**: `main`
- **Root Directory**: 留空（根目录）
- **Environment**: `Python 3`
- **Build Command**: 
  ```
  pip install -r requirements.txt
  ```
- **Start Command**: 
  ```
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```
- **Plan**: 选择 **"Free"**

### 5. 添加环境变量

在 "Environment Variables" 部分，点击 "Add Environment Variable"：

1. **COMPASS_API_KEY**
   - Key: `COMPASS_API_KEY`
   - Value: 你的 Compass API key

2. **ALLOWED_ORIGINS**（暂时，部署前端后更新）
   - Key: `ALLOWED_ORIGINS`
   - Value: `https://fortune-app.vercel.app`

3. **可选：DEEPSEEK_API_KEY**
   - Key: `DEEPSEEK_API_KEY`
   - Value: 你的 DeepSeek API key（如果有）

### 6. 创建服务

点击 "Create Web Service"

### 7. 等待部署

- Render 会自动开始部署
- 可能需要 5-10 分钟
- 可以在 "Logs" 标签查看部署进度

### 8. 获取服务地址

部署完成后：
- Render 会提供一个 URL，如：`https://fortune-app.onrender.com`
- **这就是你的后端地址！** 📍

### 9. 测试后端

访问健康检查：
```
https://你的render地址/health
```

应该返回：
```json
{"status": "ok"}
```

## ⚠️ Render 免费套餐注意事项

1. **休眠机制**：
   - 15 分钟无活动后，服务会休眠
   - 首次访问休眠服务时，需要等待 30-60 秒唤醒

2. **性能**：
   - 免费套餐性能较低
   - 适合开发和小型项目

3. **升级选项**：
   - 如果需要更好的性能，可以升级到付费计划

## ✅ 部署后操作

1. **获取后端地址**（Render 提供的 URL）
2. **部署前端到 Vercel**
3. **在 Vercel 设置环境变量**：`VITE_API_BASE_URL` = Render 后端地址
4. **在 Render 更新环境变量**：`ALLOWED_ORIGINS` = Vercel 前端地址

## 🎯 总结

由于 Railway 免费计划限制，建议使用 **Render** 部署后端：
- ✅ 完全免费
- ✅ 配置简单
- ✅ 自动部署
- ✅ 适合你的项目

需要我帮你用 Render 部署吗？
