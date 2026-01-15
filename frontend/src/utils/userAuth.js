/**
 * 用户身份管理工具
 * 用于内网环境下的用户识别和隔离
 */

/**
 * 生成或获取用户唯一ID
 * 基于浏览器指纹和设备信息生成，确保同一设备/浏览器使用相同的ID
 */
export function getOrCreateUserId() {
  // 1. 尝试从 localStorage 获取已存在的 user_id
  let userId = localStorage.getItem('fortune_user_id');
  
  if (userId) {
    return userId;
  }
  
  // 2. 生成新的用户ID（基于浏览器指纹）
  // 组合多个因素生成唯一ID：
  // - User-Agent
  // - 屏幕分辨率
  // - 时区
  // - 语言
  // - 时间戳（作为随机因子）
  
  const fingerprint = [
    navigator.userAgent,
    screen.width + 'x' + screen.height,
    new Date().getTimezoneOffset(),
    navigator.language,
    Date.now()
  ].join('|');
  
  // 简单的哈希函数（用于生成固定长度的ID）
  let hash = 0;
  for (let i = 0; i < fingerprint.length; i++) {
    const char = fingerprint.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // 转换为32位整数
  }
  
  // 生成用户ID：user_ + 哈希值（转为正数）+ 时间戳后6位
  userId = `user_${Math.abs(hash)}_${Date.now().toString().slice(-6)}`;
  
  // 3. 保存到 localStorage
  localStorage.setItem('fortune_user_id', userId);
  
  console.log('✅ 生成用户ID:', userId);
  
  return userId;
}

/**
 * 获取当前用户ID（如果不存在则创建）
 */
export function getUserId() {
  return getOrCreateUserId();
}

/**
 * 清除用户ID（用于测试或切换用户）
 */
export function clearUserId() {
  localStorage.removeItem('fortune_user_id');
  console.log('🗑️ 已清除用户ID');
}

/**
 * 生成 Authorization header
 * 用于向后端发送用户身份信息
 */
export function getAuthHeader() {
  const userId = getUserId();
  
  // 方案1: 使用简单的 base64 编码（内网环境）
  // 生产环境应使用真正的 JWT token
  const token = btoa(JSON.stringify({ user_id: userId }));
  
  return {
    'Authorization': `Bearer ${token}`
  };
}

/**
 * 在 URL 中添加 user_id 参数（备用方案）
 */
export function addUserIdToUrl(url) {
  const userId = getUserId();
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}user_id=${encodeURIComponent(userId)}`;
}
