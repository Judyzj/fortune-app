# 🚀 Vercel 部署正确配置步骤

## ⚠️ 重要：必须在 Vercel 项目设置中配置

由于项目结构是 `frontend/` 子目录，**必须**在 Vercel 项目设置中手动配置 Root Directory。

## 📋 详细步骤

### 1. 进入项目设置
1. 登录 Vercel: https://vercel.com/dashboard
2. 找到你的 `fortune-app` 项目
3. 点击项目进入详情页
4. 点击顶部 **"Settings"** 标签

### 2. 设置 Root Directory（关键步骤）
1. 在左侧菜单找到 **"General"**
2. 滚动到 **"Root Directory"** 部分
3. 点击 **"Edit"** 按钮
4. 输入：`frontend`
5. 点击 **"Save"**

### 3. 配置环境变量
1. 在 Settings 页面，找到 **"Environment Variables"**
2. 点击 **"Add New"**
3. 添加：
   - **Key**: `VITE_API_BASE_URL`
   - **Value**: `http://localhost:8000`（暂时，后端部署后改）
   - **Environment**: 全选（Production, Preview, Development）
4. 点击 **"Save"**

### 4. 重新部署
1. 回到项目主页面
2. 点击 **"Deployments"** 标签
3. 找到最新的部署（或失败的部署）
4. 点击右侧 **"..."** 菜单
5. 选择 **"Redeploy"**
6. 确认并等待部署完成

## ✅ 验证配置

部署成功后，你应该看到：
- ✅ 构建日志显示 "Installing dependencies..."
- ✅ 构建日志显示 "Building..."
- ✅ 没有 "cd: frontend: No such file or directory" 错误
- ✅ 部署状态变为 "Ready"

## 🔍 如果还是失败

### 检查清单：
1. ✅ Root Directory 是否设置为 `frontend`？
2. ✅ 环境变量 `VITE_API_BASE_URL` 是否已添加？
3. ✅ 是否点击了 "Redeploy" 重新部署？
4. ✅ 查看构建日志，确认错误信息

### 备选方案：删除 vercel.json
如果设置 Root Directory 后还是有问题，可以：
1. 删除根目录的 `vercel.json` 文件
2. 只依赖 Vercel 项目设置中的 Root Directory
3. 重新部署

---

## 📝 当前配置说明

我已经简化了 `vercel.json`，只保留路由重写规则。所有构建配置都通过 Vercel 项目设置中的 Root Directory 来控制。

这样更可靠，因为：
- Root Directory 设置后，Vercel 会自动在 `frontend/` 目录下执行命令
- 不需要在命令中手动 `cd frontend`
- 更符合 Vercel 的最佳实践
