# 🔒 用户隔离功能说明

## 📋 功能概述

已实现完整的用户隔离功能，确保：
- ✅ **用户只能看到自己创建的命书**
- ✅ **用户不能访问或删除别人的命书**
- ✅ **内网环境下自动生成用户唯一ID**

## 🔧 实现方式

### 前端：自动生成用户ID

**文件：** `frontend/src/utils/userAuth.js`

**工作原理：**
1. 首次访问时，基于浏览器指纹生成唯一用户ID
2. 将用户ID保存到 `localStorage`
3. 后续访问时，自动使用已保存的用户ID
4. 在所有命书相关的 API 请求中自动添加用户身份信息

**生成规则：**
- 基于：User-Agent + 屏幕分辨率 + 时区 + 语言 + 时间戳
- 格式：`user_{hash}_{timestamp}`
- 存储：`localStorage.fortune_user_id`

### 后端：权限验证

**所有命书相关接口都有权限检查：**

1. **获取命书列表** (`GET /api/user/fortune-books`)
   - ✅ 只返回当前用户的命书
   - ✅ 按 `user_id` 过滤查询

2. **获取命书详情** (`GET /api/fortune-books/{book_id}`)
   - ✅ 检查命书是否属于当前用户
   - ✅ 如果不是，返回 403 错误

3. **删除命书** (`DELETE /api/fortune-books/{book_id}`)
   - ✅ 检查命书是否属于当前用户
   - ✅ 如果不是，返回 403 错误

4. **保存命书** (`POST /api/fortune-books`)
   - ✅ 自动关联当前用户的 `user_id`

## 🔐 用户身份识别

### 方式 1: JWT Token（推荐用于生产环境）

前端发送：
```javascript
headers: {
  'Authorization': 'Bearer {base64_encoded_token}'
}
```

后端解析：
- 从 `Authorization` header 中解析 token
- 提取 `user_id` 字段

### 方式 2: Query 参数（备用方案）

前端发送：
```
GET /api/user/fortune-books?user_id=user_123456
```

后端解析：
- 从 query 参数中获取 `user_id`

### 方式 3: 环境变量（仅开发环境）

如果都没有提供，开发环境会使用 `default_user`（不安全）

## 🛡️ 安全说明

### 内网环境

**当前实现：**
- ✅ 基于浏览器指纹生成用户ID
- ✅ 同一设备/浏览器使用相同的ID
- ✅ 不同设备/浏览器使用不同的ID
- ⚠️ **不是真正的身份验证**，仅用于用户隔离

**适用场景：**
- ✅ 内网环境
- ✅ 不需要登录的场景
- ✅ 基于设备的用户隔离

### 生产环境（如果需要真正的身份验证）

**建议改进：**
1. 实现真正的登录系统
2. 使用 JWT token 进行身份验证
3. 在后端验证 token 的有效性
4. 使用 session 或 cookie 管理用户状态

## 📝 使用示例

### 前端自动处理

前端代码**无需修改**，所有 API 调用会自动添加用户身份：

```javascript
// 这些调用会自动添加用户身份信息
await getMyFortuneBooks();        // ✅ 自动添加 user_id
await saveFortuneBook(bookData);  // ✅ 自动添加 user_id
await deleteFortuneBook(bookId);  // ✅ 自动添加 user_id
```

### 手动获取用户ID

如果需要手动获取用户ID：

```javascript
import { getUserId } from './utils/userAuth';

const userId = getUserId();
console.log('当前用户ID:', userId);
```

### 清除用户ID（测试用）

```javascript
import { clearUserId } from './utils/userAuth';

clearUserId(); // 清除后，下次访问会生成新的用户ID
```

## ✅ 验证方法

### 1. 测试用户隔离

1. **在浏览器 A 中：**
   - 创建几个命书
   - 查看命书列表，应该能看到所有创建的命书

2. **在浏览器 B 中（或清除 localStorage）：**
   - 查看命书列表，应该看不到浏览器 A 创建的命书
   - 尝试访问浏览器 A 创建的命书ID，应该返回 403 错误

### 2. 检查后端日志

后端会输出详细的权限检查日志：

```
✅ 从 JWT token 解析用户ID: user_123456
✅ 权限验证通过：用户 user_123456 访问自己的命书
❌ 权限拒绝：用户 user_789012 尝试访问用户 user_123456 的命书
```

## 🎯 总结

**已实现的功能：**
- ✅ 用户只能看到自己创建的命书
- ✅ 用户不能访问别人的命书
- ✅ 用户不能删除别人的命书
- ✅ 自动生成和管理用户ID
- ✅ 内网环境下无需登录即可使用

**安全级别：**
- 🟡 **内网环境**：基于浏览器指纹，适合内网使用
- 🔴 **公网环境**：建议实现真正的身份验证系统

## 📋 部署注意事项

**内网部署时：**
- ✅ 无需额外配置
- ✅ 用户隔离功能自动生效
- ✅ 每个设备/浏览器自动获得独立的用户空间

**如果需要更强的安全性：**
- 实现登录系统
- 使用真正的 JWT token
- 在后端验证 token 签名和过期时间
