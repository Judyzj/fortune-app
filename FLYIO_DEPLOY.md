# 🚀 Fly.io 部署指南

## 📋 为什么选择 Fly.io？

**优点：**
- ✅ 不需要绑定银行卡
- ✅ 有免费额度
- ✅ 性能优秀
- ✅ 全球分布

**缺点：**
- ⚠️ 需要安装 CLI 工具
- ⚠️ 配置稍复杂

## 🔧 部署步骤

### 第一步：安装 Fly CLI

**macOS:**
```bash
curl -L https://fly.io/install.sh | sh
```

**或者使用 Homebrew:**
```bash
brew install flyctl
```

**验证安装:**
```bash
fly version
```

### 第二步：登录 Fly.io

```bash
fly auth login
```

这会打开浏览器，用 GitHub 账号登录。

### 第三步：初始化项目

```bash
cd /Users/zijun.yan/fortune_app
fly launch
```

**交互式配置：**
- **App Name**: 输入应用名称（如 `fortune-app-backend`）
- **Region**: 选择区域（推荐 `sin` - Singapore 或 `iad` - Virginia）
- **Postgres**: 选择 `n`（稍后单独创建）
- **Redis**: 选择 `n`（不需要）
- **Deploy now**: 选择 `n`（先配置环境变量）

### 第四步：配置环境变量

```bash
fly secrets set COMPASS_API_KEY=你的compass_api_key
fly secrets set ALLOWED_ORIGINS=https://fortune-app.vercel.app
```

**可选环境变量：**
```bash
fly secrets set DEEPSEEK_API_KEY=你的deepseek_api_key
fly secrets set COMPASS_BASE_URL=https://compass.llm.shopee.io/compass-api/v1
```

### 第五步：创建 PostgreSQL 数据库（可选）

如果需要数据库：

```bash
fly postgres create --name fortune-app-db
```

然后连接数据库到应用：

```bash
fly postgres attach --app fortune-app-backend fortune-app-db
```

这会自动设置 `DATABASE_URL` 环境变量。

### 第六步：部署

```bash
fly deploy
```

等待部署完成（可能需要 5-10 分钟）。

### 第七步：获取应用地址

```bash
fly status
```

或者查看：
```bash
fly open
```

你会得到一个类似这样的地址：
```
https://fortune-app-backend.fly.dev
```

## 📝 配置文件说明

Fly.io 会创建 `fly.toml` 配置文件，内容类似：

```toml
app = "fortune-app-backend"
primary_region = "sin"

[build]

[env]
  PORT = "8080"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
  processes = ["app"]

[[services]]
  http_checks = []
  internal_port = 8080
  processes = ["app"]
  protocol = "tcp"
  script_checks = []
```

**需要修改的部分：**

1. **internal_port**: 改为 `8000`（或使用环境变量 `$PORT`）
2. **添加启动命令**：

```toml
[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "8000"

[[services]]
  internal_port = 8000
  processes = ["app"]

[processes]
  app = "uvicorn main:app --host 0.0.0.0 --port $PORT"
```

## 🔍 常见问题

### 问题 1: 找不到 Python

**解决方案：**
创建 `runtime.txt`：
```
python-3.11
```

### 问题 2: 启动命令错误

**检查 `fly.toml`**：
确保有正确的启动命令：
```toml
[processes]
  app = "uvicorn main:app --host 0.0.0.0 --port $PORT"
```

### 问题 3: 端口错误

**确保端口一致：**
- `fly.toml` 中的 `internal_port`
- 启动命令中的 `--port $PORT`
- 环境变量 `PORT`

## ✅ 验证部署

部署完成后：

1. **检查状态**：
   ```bash
   fly status
   ```

2. **查看日志**：
   ```bash
   fly logs
   ```

3. **访问健康检查**：
   ```
   https://你的应用地址.fly.dev/health
   ```

应该返回：`{"status": "ok"}`

## 🎯 完整命令列表

```bash
# 1. 安装
curl -L https://fly.io/install.sh | sh

# 2. 登录
fly auth login

# 3. 初始化
cd /Users/zijun.yan/fortune_app
fly launch

# 4. 设置环境变量
fly secrets set COMPASS_API_KEY=你的key
fly secrets set ALLOWED_ORIGINS=https://fortune-app.vercel.app

# 5. 创建数据库（可选）
fly postgres create --name fortune-app-db
fly postgres attach --app fortune-app-backend fortune-app-db

# 6. 部署
fly deploy

# 7. 查看状态
fly status
fly logs
```

## 📋 下一步

部署成功后：
1. **获取应用地址**（如 `https://fortune-app-backend.fly.dev`）
2. **部署前端到 Vercel**
3. **在 Vercel 设置环境变量**：`VITE_API_BASE_URL` = Fly.io 地址
4. **在 Fly.io 更新环境变量**：`ALLOWED_ORIGINS` = Vercel 前端地址

## 💰 费用说明

Fly.io 免费额度：
- **3 个共享 CPU 虚拟机**
- **3GB 持久化存储**
- **160GB 出站流量/月**

对于小型应用，通常足够使用。

需要我帮你执行这些命令吗？
