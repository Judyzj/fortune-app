# 🚂 Railway 后端部署指南

## 📋 部署步骤

### 第一步：准备 Railway 账号

1. 访问：https://railway.app
2. 点击 "Start a New Project"
3. 选择 "Login with GitHub"
4. 授权 Railway 访问你的 GitHub 账号

### 第二步：创建新项目

1. 登录后，点击 **"New Project"**
2. 选择 **"Deploy from GitHub repo"**
3. 在仓库列表中找到 `fortune-app`
4. 点击 **"Deploy Now"**

### 第三步：配置项目

Railway 会自动检测到 Python 项目，但需要确认配置：

1. **等待初始部署完成**（可能需要 2-3 分钟）
2. 点击项目进入详情页

### 第四步：配置环境变量

1. 在项目页面，点击 **"Variables"** 标签
2. 添加以下环境变量：

#### 必需的环境变量：

| Key | Value | 说明 |
|-----|-------|------|
| `COMPASS_API_KEY` | 你的 Compass API key | 必需，用于 AI 对话 |
| `ALLOWED_ORIGINS` | `https://fortune-app.vercel.app` | 前端地址（部署前端后更新） |

#### 可选的环境变量：

| Key | Value | 说明 |
|-----|-------|------|
| `DEEPSEEK_API_KEY` | 你的 DeepSeek API key | 可选，作为备用 |
| `DEEPSEEK_API_BASE_URL` | `https://api.deepseek.com/v1` | 可选 |
| `COMPASS_BASE_URL` | `https://compass.llm.shopee.io/compass-api/v1` | 可选，默认值 |
| `DATABASE_URL` | 留空（使用 SQLite） | 可选，Railway 会自动提供 PostgreSQL |

**添加方法：**
1. 点击 **"New Variable"**
2. 输入 Key 和 Value
3. 点击 **"Add"**
4. Railway 会自动重新部署

### 第五步：获取后端地址

1. 部署完成后，Railway 会显示一个 URL
2. 点击 **"Settings"** → **"Domains"**
3. 你会看到一个类似这样的地址：
   ```
   https://fortune-app-production.up.railway.app
   ```
4. **复制这个地址**，这就是你的后端 API 地址！📍

### 第六步：测试后端

1. 访问健康检查接口：
   ```
   https://你的后端地址/health
   ```
2. 应该返回：
   ```json
   {"status": "ok"}
   ```
3. 如果成功，说明后端部署成功！✅

## 🔧 配置说明

### 自动检测

Railway 会自动：
- ✅ 检测到 `requirements.txt`（Python 依赖）
- ✅ 检测到 `Procfile`（启动命令）
- ✅ 安装所有依赖
- ✅ 运行应用

### 启动命令

Railway 使用 `Procfile` 中的命令：
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

- `$PORT` 是 Railway 自动提供的端口
- Railway 会自动将流量路由到这个端口

### 数据库

- **开发环境**：使用 SQLite（`fortune_app.db`）
- **生产环境**：Railway 可以自动提供 PostgreSQL（可选）
  - 如果使用 PostgreSQL，Railway 会自动设置 `DATABASE_URL` 环境变量

## 🚨 常见问题

### 问题 1: 部署失败

**检查：**
1. 查看 Railway 的构建日志
2. 确认 `requirements.txt` 中的所有依赖都正确
3. 确认 `main.py` 文件存在

### 问题 2: 应用无法启动

**检查：**
1. 查看 Railway 的运行日志
2. 确认环境变量已正确设置
3. 确认 `COMPASS_API_KEY` 已设置

### 问题 3: CORS 错误

**解决方案：**
1. 在 Railway 环境变量中设置 `ALLOWED_ORIGINS`
2. 确保包含完整的前端 URL（包括 `https://`）
3. 如果有多个前端域名，用逗号分隔

### 问题 4: 数据库连接失败

**解决方案：**
1. 如果使用 SQLite，确保有写入权限
2. 如果使用 PostgreSQL，Railway 会自动配置 `DATABASE_URL`

## 📝 部署后操作

### 1. 更新前端环境变量

在 Vercel 中：
- 设置 `VITE_API_BASE_URL` = 你的 Railway 后端地址

### 2. 更新后端 CORS

在 Railway 环境变量中：
- 更新 `ALLOWED_ORIGINS` = 你的 Vercel 前端地址

### 3. 测试完整流程

1. 访问前端地址
2. 填写表单
3. 提交请求
4. 检查是否能正常调用后端 API

## ✅ 验证清单

部署完成后，确认：

- [ ] Railway 部署状态显示 "Active"
- [ ] 可以访问 `/health` 接口
- [ ] 环境变量已正确设置
- [ ] 后端地址已获取
- [ ] 前端环境变量已更新
- [ ] CORS 配置正确
- [ ] 可以正常调用 API

## 🎯 下一步

后端部署成功后：
1. **获取后端地址**（Railway 提供的 URL）
2. **部署前端**（Vercel）
3. **配置前端环境变量**（指向后端地址）
4. **更新后端 CORS**（允许前端域名）

## 💰 费用说明

Railway 提供：
- **免费额度**：$5/月
- **超出后**：按使用量付费
- **对于小型应用**：通常免费额度足够使用

## 📞 需要帮助？

如果遇到问题：
1. 查看 Railway 的构建日志和运行日志
2. 检查环境变量配置
3. 确认所有依赖都已安装
