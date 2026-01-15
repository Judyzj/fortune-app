# 🗄️ Render PostgreSQL 数据库配置指南

## 📋 为什么需要 PostgreSQL？

Render 免费套餐**不支持持久化磁盘**，这意味着：
- ❌ SQLite 数据库文件会丢失
- ❌ 每次重启后数据会重置

**解决方案：** 使用 Render 提供的免费 PostgreSQL 数据库

## 🚀 创建 PostgreSQL 数据库

### 第一步：创建数据库

1. **在 Render Dashboard**，点击 **"New +"** 按钮
2. 选择 **"PostgreSQL"**
3. 填写配置：
   - **Name**: `fortune-app-db`（或你喜欢的名字）
   - **Database**: 留空（Render 会自动创建）
   - **User**: 留空（Render 会自动创建）
   - **Region**: 选择与你的 Web Service 相同的区域（如 `Virginia (US East)`）
   - **PostgreSQL Version**: 保持默认（最新版本）
   - **Plan**: 选择 **"Free"**
4. 点击 **"Create Database"**
5. 等待创建完成（1-2 分钟）

### 第二步：获取数据库连接信息

数据库创建完成后：

1. **进入数据库详情页**
2. **找到 "Connections" 部分**
3. **复制 "Internal Database URL"**（用于 Web Service 连接）
   - 格式类似：`postgresql://user:password@host:port/dbname`
   - 这个 URL 包含所有连接信息

### 第三步：配置 Web Service 环境变量

1. **进入你的 Web Service 详情页**
2. 点击 **"Environment"** 标签
3. 点击 **"Add Environment Variable"**
4. 添加：
   - **Key**: `DATABASE_URL`
   - **Value**: 粘贴刚才复制的 "Internal Database URL"
   - **注意**：使用 "Internal Database URL"，不是 "External Database URL"
5. 点击 **"Save Changes"**
6. Render 会自动重新部署你的服务

## ✅ 验证数据库连接

部署完成后，你的应用会自动：
1. 连接到 PostgreSQL 数据库
2. 自动创建数据库表（通过 SQLAlchemy）
3. 开始使用数据库存储数据

**验证方法：**
1. 访问你的应用
2. 保存一条命书数据
3. 刷新页面，数据应该还在（不会丢失）

## 📝 代码说明

你的代码已经支持 PostgreSQL！

```python
# main.py
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fortune_app.db")
```

**工作原理：**
- 如果设置了 `DATABASE_URL` 环境变量，使用 PostgreSQL
- 如果没有设置，使用 SQLite（本地开发）

**SQLAlchemy 会自动处理：**
- PostgreSQL 和 SQLite 的差异
- 数据库表的创建
- 数据类型的转换

## 🔧 可能需要添加的依赖

检查 `requirements.txt` 是否包含 PostgreSQL 驱动：

如果还没有，需要添加：
```
psycopg2-binary==2.9.9
```

**让我检查并更新 requirements.txt...**

## 🎯 完整步骤总结

1. ✅ 创建 PostgreSQL 数据库（Free 计划）
2. ✅ 复制 "Internal Database URL"
3. ✅ 在 Web Service 环境变量中添加 `DATABASE_URL`
4. ✅ 等待自动重新部署
5. ✅ 验证数据持久化

## ⚠️ 注意事项

1. **使用 Internal Database URL**：
   - 不要使用 "External Database URL"
   - Internal URL 在同一网络内，速度更快、更安全

2. **数据库区域**：
   - 选择与 Web Service 相同的区域
   - 这样可以减少延迟

3. **免费套餐限制**：
   - 数据库大小限制：1 GB
   - 对于小型应用足够使用

## 🚀 下一步

配置完数据库后：
1. 数据会持久化保存
2. 重启服务不会丢失数据
3. 可以正常使用所有数据库功能

需要我帮你检查并更新 requirements.txt 吗？
