# 🔒 命书权限控制说明

## ✅ 已实现的权限控制

### 1. 获取命书列表（GET /api/user/fortune-books）
- ✅ **已实现**：只返回当前用户创建的命书
- **实现方式**：按 `user_id` 过滤查询
- **代码位置**：`main.py:1378-1380`

```python
books = db.query(FortuneBook).filter(
    FortuneBook.user_id == current_user_id
).order_by(FortuneBook.created_at.desc()).all()
```

### 2. 获取命书详情（GET /api/fortune-books/{book_id}）
- ✅ **已实现**：只能访问自己创建的命书
- **实现方式**：查询后验证 `user_id` 是否匹配
- **代码位置**：`main.py:1421-1429`

```python
current_user_id = get_current_user_id(authorization=authorization, user_id=user_id)
if fortune_book.user_id != current_user_id:
    raise HTTPException(status_code=403, detail="无权访问：该命书不属于当前用户")
```

### 3. 删除命书（DELETE /api/fortune-books/{book_id}）
- ✅ **已实现**：只能删除自己创建的命书
- **实现方式**：查询后验证 `user_id` 是否匹配
- **代码位置**：`main.py:1512-1519`

```python
current_user_id = get_current_user_id(authorization=authorization, user_id=user_id)
if fortune_book.user_id != current_user_id:
    raise HTTPException(status_code=403, detail="无权删除：该命书不属于当前用户")
```

### 4. 生成K线（POST /api/generate-kline）
- ✅ **已实现**：使用 `book_id` 时，只能使用自己创建的命书
- **实现方式**：当传入 `book_id` 时，验证 `user_id` 是否匹配
- **代码位置**：`main.py:1637-1645`
- **注意**：如果直接传入 `birth_data`（不传 `book_id`），则无需权限验证

```python
if request.book_id:
    book = db.query(FortuneBook).filter(FortuneBook.id == request.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="命书不存在")
    
    # 用户权限检查：确保用户只能使用自己的命书
    current_user_id = get_current_user_id(authorization=authorization, user_id=user_id)
    if book.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权访问：该命书不属于当前用户")
```

### 5. 保存命书（POST /api/fortune-books）
- ✅ **已实现**：保存时自动关联当前用户ID
- **实现方式**：从 JWT token 或 query 参数获取 `user_id`，保存到数据库
- **代码位置**：`main.py:1569-1573`

```python
current_user_id = get_current_user_id(authorization=authorization, user_id=user_id)
fortune_book = FortuneBook(
    user_id=current_user_id,
    ...
)
```

## 🚫 不受影响的接口

### 人生K线接口（POST /api/divination/life-line）
- ✅ **不受影响**：该接口不涉及命书权限，直接使用传入的出生信息生成K线
- **原因**：该接口不查询数据库中的命书，而是直接使用请求参数

## 🔐 用户身份识别

### 获取用户ID的优先级：
1. **JWT Token**（从 `Authorization` header 解析）
2. **Query 参数** `user_id`（开发/测试用）
3. **环境变量** `DEFAULT_USER_ID`（仅开发环境）
4. **默认值** `"default_user"`（仅开发环境，不安全）

### 生产环境要求：
- 生产环境必须提供有效的 JWT token
- 如果没有提供 token，会返回 401 错误

## 📝 使用示例

### 前端调用示例：

```javascript
// 1. 获取命书列表（自动过滤，只返回当前用户的）
const response = await fetch('/api/user/fortune-books', {
  headers: {
    'Authorization': `Bearer ${token}` // 或从 localStorage 获取
  }
});

// 2. 获取命书详情（需要权限验证）
const response = await fetch(`/api/fortune-books/${bookId}`, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

// 3. 删除命书（需要权限验证）
const response = await fetch(`/api/fortune-books/${bookId}`, {
  method: 'DELETE',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

// 4. 使用命书生成K线（需要权限验证）
const response = await fetch('/api/generate-kline', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    book_id: 123 // 必须是当前用户的命书
  })
});
```

## ⚠️ 注意事项

1. **内网环境**：如果在内网环境使用，可能需要调整 `get_current_user_id` 函数，支持基于 IP 或其他方式生成临时用户ID
2. **开发环境**：开发环境可以使用 `user_id` query 参数或默认值，但生产环境必须使用 JWT token
3. **前端集成**：前端需要确保在请求时携带正确的 `Authorization` header

## ✅ 验证清单

- [x] 获取命书列表：只返回当前用户的命书
- [x] 获取命书详情：只能访问自己的命书
- [x] 删除命书：只能删除自己的命书
- [x] 生成K线（使用 book_id）：只能使用自己的命书
- [x] 保存命书：自动关联当前用户ID
- [x] 人生K线接口：不受影响，正常工作

## 🎯 总结

所有命书相关的接口都已实现权限控制，确保：
- ✅ 用户只能看到自己创建的命书
- ✅ 用户只能访问自己创建的命书
- ✅ 用户只能删除自己创建的命书
- ✅ 用户只能使用自己的命书生成K线
- ✅ 人生K线功能不受影响，正常工作
