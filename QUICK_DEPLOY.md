# 🚀 快速部署指南

## 第一步：推送代码到 GitHub

### 1. 在 GitHub 上创建新仓库

1. 访问 https://github.com/new
2. 填写仓库名称（例如：`fortune-app`）
3. 选择 Public 或 Private
4. **不要**勾选 "Initialize this repository with a README"
5. 点击 "Create repository"

### 2. 在本地推送代码

在终端执行以下命令（替换 `YOUR_USERNAME` 为你的 GitHub 用户名）：

```bash
cd /Users/zijun.yan/fortune_app

# 提交代码
git commit -m "Initial commit: Fortune App"

# 添加远程仓库（替换 YOUR_USERNAME 和仓库名）
git remote add origin https://github.com/YOUR_USERNAME/fortune-app.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

如果提示需要登录，GitHub 现在使用 Personal Access Token 而不是密码：
- 访问 https://github.com/settings/tokens
- 生成新的 token（选择 `repo` 权限）
- 使用 token 作为密码

---

## 第二步：在 Vercel 上部署

### 1. 登录 Vercel

1. 访问 https://vercel.com
2. 点击 "Sign Up" 或 "Log In"
3. 选择 "Continue with GitHub"
4. 授权 Vercel 访问你的 GitHub 账号

### 2. 导入项目

1. 登录后，点击 **"Add New..."** 或 **"New Project"**
2. 在项目列表中找到你刚才推送的 `fortune-app` 仓库
3. 点击 **"Import"**

### 3. 配置项目设置

Vercel 会自动检测到这是一个 Vite 项目，但需要手动配置：

- **Framework Preset**: `Vite` 或 `Other`
- **Root Directory**: 点击 "Edit" 并设置为 `frontend`
- **Build Command**: `npm run build`（应该自动填充）
- **Output Directory**: `dist`（应该自动填充）
- **Install Command**: `npm install`（应该自动填充）

### 4. 配置环境变量

在 "Environment Variables" 部分，添加：

- **Key**: `VITE_API_BASE_URL`
- **Value**: 
  - 如果后端已部署：填写后端地址（如 `https://your-backend.railway.app`）
  - 如果后端还在本地：暂时填写 `http://localhost:8000`（仅用于测试）

点击 "Add" 添加变量。

### 5. 部署

1. 点击 **"Deploy"** 按钮
2. 等待 1-2 分钟，Vercel 会自动：
   - 安装依赖
   - 构建项目
   - 部署到 CDN

### 6. 获取访问链接

部署完成后，你会看到：
- ✅ 部署成功提示
- 🌐 访问链接：`https://your-app-name.vercel.app`

**这个链接就是你的公网访问地址，可以分享给任何人！**

---

## 第三步：更新代码后重新部署

以后每次更新代码，只需要：

```bash
git add .
git commit -m "描述你的更改"
git push origin main
```

Vercel 会自动检测到 GitHub 的更新并重新部署（通常 1-2 分钟）。

---

## ⚠️ 重要提示

### 关于后端

Vercel **只部署前端**，你的 Python 后端需要单独部署：

**推荐方案：**
1. **Railway** (https://railway.app) - 最简单，支持自动部署
2. **Render** (https://render.com) - 免费套餐可用
3. **Fly.io** (https://fly.io) - 性能好

**后端部署后，记得：**
1. 在 Vercel 环境变量中更新 `VITE_API_BASE_URL` 为后端地址
2. 在后端设置 `ALLOWED_ORIGINS` 环境变量，包含你的 Vercel 域名

### 后端 CORS 配置示例

如果后端部署在 Railway，在 Railway 的环境变量中添加：
```
ALLOWED_ORIGINS=https://your-app.vercel.app,https://your-app-git-main.vercel.app
```

---

## 🎉 完成！

部署成功后，你的应用就可以通过公网访问了！

如有问题，查看 `DEPLOYMENT.md` 获取更详细的说明。
