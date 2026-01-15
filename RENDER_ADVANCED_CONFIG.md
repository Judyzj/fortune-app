# ⚙️ Render Advanced 配置填写指南

## 📋 配置项说明

### 1. Secret Files（密钥文件）

**说明：** 存储包含敏感数据的纯文本文件（如 .env 文件或私钥）

**填写：**
- ✅ **留空**（不需要）
- 你的环境变量已经通过 "Variables" 标签设置了
- 不需要上传 .env 文件

### 2. Health Check Path（健康检查路径）⭐ 重要

**说明：** Render 会定期访问这个路径来监控服务状态

**填写：**
```
/health
```

**原因：**
- 你的代码中有 `/health` 接口
- Render 会定期访问这个路径检查服务是否正常运行
- 如果服务异常，Render 会自动重启

**验证：**
部署后可以访问：`https://你的服务地址/health`
应该返回：`{"status": "ok"}`

### 3. Pre-Deploy Command（部署前命令）

**说明：** 在启动命令之前运行的命令，用于数据库迁移等

**填写：**
- ✅ **留空**（不需要）
- 你的应用不需要数据库迁移
- 数据库表会在首次启动时自动创建

**如果需要（可选）：**
如果将来需要数据库迁移，可以填写：
```bash
python -m alembic upgrade head
```
但当前不需要。

### 4. Auto-Deploy（自动部署）

**说明：** 是否在代码更新时自动部署

**填写：**
- ✅ **保持默认：`On Commit`**
- 这样每次你推送代码到 GitHub，Render 会自动重新部署
- 非常方便！

**选项说明：**
- `On Commit`: 每次代码更新自动部署（推荐）
- `Manual`: 手动部署（不推荐）

### 5. Build Filters（构建过滤器）

**说明：** 指定哪些文件变化会触发自动部署

**填写：**
- ✅ **留空**（使用默认）
- 默认情况下，任何文件变化都会触发部署
- 这对你的项目来说没问题

**如果需要优化（可选）：**

#### Included Paths（包含路径）：
如果只想在特定文件变化时部署，可以添加：
```
main.py
calculator.py
requirements.txt
services/
```

#### Ignored Paths（忽略路径）：
如果想忽略某些文件变化（如文档），可以添加：
```
*.md
README.md
DEPLOY.md
frontend/
```

**建议：** 保持默认，让所有变化都触发部署。

## ✅ 推荐配置

### 必须填写：

1. **Health Check Path**: `/health`

### 可以留空：

2. **Secret Files**: 留空
3. **Pre-Deploy Command**: 留空
4. **Build Filters**: 留空（使用默认）

### 保持默认：

5. **Auto-Deploy**: `On Commit`（默认值）

## 📝 完整配置示例

```
Secret Files: [留空]
Health Check Path: /health
Pre-Deploy Command: [留空]
Auto-Deploy: On Commit
Build Filters: [留空]
```

## 🎯 下一步

配置完成后：
1. 点击 **"Save Changes"** 保存
2. Render 会自动开始部署
3. 等待部署完成（5-10 分钟）
4. 访问健康检查：`https://你的服务地址/health`

## ⚠️ 注意事项

1. **Health Check Path 很重要**：
   - 如果填写错误，Render 无法监控服务状态
   - 可能导致服务异常时无法自动重启

2. **Auto-Deploy 保持开启**：
   - 这样每次推送代码都会自动部署
   - 非常方便，不需要手动操作

3. **其他配置可以留空**：
   - 你的应用不需要这些高级配置
   - 保持简单即可
