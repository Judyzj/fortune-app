/**
 * API 工具函数
 */

import { getAuthHeader, addUserIdToUrl } from './userAuth';

// 支持环境变量，生产环境使用 Vercel 环境变量，开发环境使用 localhost
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const FORTUNE_API = `${API_BASE_URL}/api/fortune`;
const CALCULATE_API = `${API_BASE_URL}/api/calculate`;
const MY_FORTUNE_BOOKS_API = `${API_BASE_URL}/api/user/fortune-books`;
const GENERATE_KLINE_API = `${API_BASE_URL}/api/generate-kline`;
const LIFE_LINE_API = `${API_BASE_URL}/api/divination/life-line`;
const CHAT_DIVINATION_API = `${API_BASE_URL}/api/chat/divination`;
const SAVE_FORTUNE_BOOK_API = `${API_BASE_URL}/api/fortune-books`;

// 导出 API 常量供组件使用
export { CHAT_DIVINATION_API };
const DELETE_FORTUNE_BOOK_API = `${API_BASE_URL}/api/fortune-books`;

/**
 * 格式化出生时间，分钟允许为空（自动转换为 00）
 * @param {number|string} hour - 小时
 * @param {number|string|null|undefined} minute - 分钟（允许为空）
 * @returns {string} 格式化的时间字符串 HH:MM
 */
function formatBirthTime(hour, minute) {
  const hourStr = String(hour).padStart(2, '0');
  // 分钟允许为空，为空时自动转换为 00
  const minuteStr = (minute !== '' && minute !== null && minute !== undefined) 
    ? String(minute).padStart(2, '0') 
    : '00';
  return `${hourStr}:${minuteStr}`;
}

/**
 * 处理 SSE 流式响应
 * @param {Response} response - Fetch API 响应对象
 * @param {Object} callbacks - 回调函数对象
 */
export async function handleSSEStream(response, callbacks = {}) {
  const {
    onText,
    onChartData,
    onCalculation,
    onProgress,
    onError,
    onComplete
  } = callbacks;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        if (onComplete) onComplete();
        break;
      }

      // 解码数据并添加到缓冲区
      buffer += decoder.decode(value, { stream: true });
      
      // 按行分割处理
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 保留最后一个可能不完整的行

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          
          // 检查结束标记
          if (data === '[DONE]') {
            if (onComplete) onComplete();
            return;
          }

          // 解析 JSON
          try {
            const json = JSON.parse(data);
            
            // 根据类型分发处理
            switch (json.type) {
              case 'text':
                if (onText) onText(json.content);
                break;
              
              case 'progress':
                if (onProgress) onProgress(json.progress || 0);
                break;
              
              case 'chart_data':
                if (onChartData) onChartData(json.data);
                break;
              
              case 'complete':
                // complete 类型：只有在 generateKLineChart 等需要数据的场景才使用
                // 起卦接口不应该返回此类型，但如果误返回了，只调用 onComplete 表示完成，不传递数据
                if (onComplete) {
                  // 检查 onComplete 是否接受参数（通过检查参数数量）
                  // 如果 json.data 存在且 onComplete 接受参数，传递 data
                  // 否则只调用 onComplete() 表示完成
                  if (json.data !== undefined && json.data !== null) {
                    // 尝试传递 data，但如果 onComplete 不接受参数，会抛出错误，需要捕获
                    try {
                      onComplete(json.data);
                    } catch (e) {
                      // 如果 onComplete 不接受参数，只调用 onComplete()
                      onComplete();
                    }
                  } else {
                    // 如果没有 data，只表示完成（用于起卦等不需要数据的场景）
                    onComplete();
                  }
                }
                break;
              
              case 'calculation':
              case 'bazi_report':
                // 支持两种类型：calculation 和 bazi_report
                if (onCalculation) onCalculation(json.data);
                break;
              
              default:
                if (json.error) {
                  if (onError) onError(json.error);
                }
                break;
            }
          } catch (e) {
            console.error('Parse JSON error:', e, 'Data:', data);
          }
        }
      }
    }
  } catch (error) {
    if (onError) onError(error.message || 'Stream read error');
  }
}

/**
 * 调用命理分析 API
 * @param {Object} formData - 表单数据
 * @param {Object} callbacks - 回调函数对象
 */
export async function fetchFortuneAnalysis(formData, callbacks = {}) {
  try {
    // 转换表单数据为 API 格式
    const requestData = {
      name: formData.name,
      gender: formData.gender === '男(乾造)' || formData.gender === 'male' ? 'male' : 'female',
      birth_date: `${formData.year}-${String(formData.month).padStart(2, '0')}-${String(formData.day).padStart(2, '0')}`,
      birth_time: formatBirthTime(formData.hour, formData.minute),
      lat: parseFloat(formData.lat),
      lng: parseFloat(formData.lng),
      city: formData.city,
    };

    const response = await fetch(FORTUNE_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestData),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    // 处理流式响应
    await handleSSEStream(response, callbacks);
  } catch (error) {
    if (callbacks.onError) {
      callbacks.onError(error.message || '请求失败');
    }
  }
}

/**
 * 调用八字排盘计算 API
 * @param {Object} formData - 表单数据
 * @returns {Promise<Object>} 返回计算结果
 */
export async function fetchBaziCalculation(formData) {
  try {
    // 转换表单数据为 API 格式
    const requestData = {
      name: formData.name,
      gender: formData.gender === '男(乾造)' || formData.gender === 'male' ? 'male' : 'female',
      birth_date: `${formData.year}-${String(formData.month).padStart(2, '0')}-${String(formData.day).padStart(2, '0')}`,
      birth_time: formatBirthTime(formData.hour, formData.minute),
      lat: parseFloat(formData.lat),
      lng: parseFloat(formData.lng),
      city: formData.city,
    };
    
    // 如果提供了自动保存参数，添加到请求中
    if (formData.auto_save !== undefined) {
      requestData.auto_save = formData.auto_save;
    }
    if (formData.book_name) {
      requestData.book_name = formData.book_name;
    }

    const response = await fetch(CALCULATE_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestData),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.error || '计算失败');
    }

    // 返回数据，包含 saved_book_id（如果自动保存成功）
    return {
      ...result.data,
      saved_book_id: result.saved_book_id  // 保存的命书ID（如果自动保存成功）
    };
  } catch (error) {
    throw new Error(error.message || '请求失败');
  }
}

/**
 * 获取用户的命书列表
 * @returns {Promise<Array>} 返回命书列表
 */
export async function getMyFortuneBooks() {
  try {
    // 添加用户身份信息
    const authHeader = getAuthHeader();
    const url = addUserIdToUrl(MY_FORTUNE_BOOKS_API);
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...authHeader,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.error || '获取命书列表失败');
    }

    return result.data || [];
  } catch (error) {
    throw new Error(error.message || '请求失败');
  }
}

/**
 * 生成K线图
 * @param {Object} payload - 请求数据（book_id 或完整的出生信息）
 * @returns {Promise<Object>} 返回K线图数据
 */
/**
 * 生成K线图数据（支持进度回调）
 * @param {Object} payload - 请求数据
 * @param {Function} onProgress - 进度回调 (progress) => void
 * @returns {Promise<Object>} 返回K线图数据
 */
export async function generateKLineChart(payload, onProgress = null) {
  // 重试机制：最多重试2次
  const maxRetries = 2;
  let lastError = null;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      if (attempt > 0) {
        console.log(`🔄 重试第 ${attempt} 次...`);
        if (onProgress) {
          onProgress(10); // 重试时显示10%进度
        }
        // 等待一段时间再重试（指数退避）
        await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
      }
      
      // 添加60秒超时（增加超时时间）
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000);
    
    try {
      const response = await fetch(GENERATE_KLINE_API, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        signal: controller.signal, // 添加超时控制
      });
      
      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const error = new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        error.status = response.status;
        throw error;
      }

    // 检查是否是流式响应
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('text/event-stream')) {
      // 流式响应处理
      let chartData = null;
      let analysisText = '';
      
      await handleSSEStream(response, {
        onProgress: (progress) => {
          if (onProgress) {
            onProgress(progress);
          }
        },
        onChartData: (data) => {
          chartData = data;
        },
        onComplete: (data) => {
          if (data && data.chart_data) {
            chartData = data.chart_data;
            analysisText = data.analysis_text || '';
          }
        },
        onError: (error) => {
          throw new Error(error);
        }
      });
      
      if (!chartData) {
        throw new Error('未收到K线图数据');
      }
      
      return {
        chart_data: chartData,
        analysis_text: analysisText
      };
    } else {
      // 普通JSON响应（兼容旧版本）
      const result = await response.json();
      
      if (!result.success) {
        throw new Error(result.error || '生成K线图失败');
      }

      return result.data;
    }
  } catch (error) {
    throw new Error(error.message || '请求失败');
  }
}

/**
 * 保存八字命书
 * @param {Object} bookData - 命书数据
 * @param {string} bookData.name - 命书名（用户自定义）
 * @param {string} bookData.person_name - 姓名
 * @param {string} bookData.gender - 性别
 * @param {string} bookData.birth_date - 出生日期 YYYY-MM-DD
 * @param {string} bookData.birth_time - 出生时间 HH:MM
 * @param {number} bookData.lat - 纬度
 * @param {number} bookData.lng - 经度
 * @param {string} bookData.city - 城市
 * @returns {Promise<Object>} 返回保存的命书信息（包含 id）
 */
export async function saveFortuneBook(bookData) {
  try {
    console.log('调用保存API:', SAVE_FORTUNE_BOOK_API);
    console.log('发送的数据:', bookData);
    
    // 添加用户身份信息
    const authHeader = getAuthHeader();
    const url = addUserIdToUrl(SAVE_FORTUNE_BOOK_API);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeader,
      },
      body: JSON.stringify(bookData),
    });

    console.log('响应状态:', response.status, response.statusText);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error('保存失败，错误信息:', errorData);
      
      // 404错误处理：区分"数据库写入失败"和"接口地址错误"
      if (response.status === 404) {
        // 检查是否是接口地址错误（通常404表示路由不存在）
        if (errorData.detail && errorData.detail.includes('Not Found')) {
          throw new Error('接口地址错误：请检查API路径是否正确');
        } else {
          throw new Error('数据库写入失败：无法保存命书数据');
        }
      }
      
      // 其他错误
      throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    console.log('保存成功，返回结果:', result);
    
    if (!result.success) {
      throw new Error(result.error || '保存命书失败');
    }

    // 返回数据，优先返回 new_id 或 id（后端返回的ID在顶层）
    // 后端返回格式：{ "success": True, "id": saved_id, "data": {...} }
    const savedId = result.new_id || result.id || result.data?.id || result.data?.new_id;
    
    if (!savedId) {
      console.warn('警告：后端未返回ID，可能保存失败');
      console.warn('后端返回的完整结果:', result);
      throw new Error('保存失败：未获取到命书ID');
    }

    return {
      id: savedId,
      new_id: savedId, // 同时提供new_id字段以兼容不同命名
      ...result.data
    };
  } catch (error) {
    console.error('保存命书异常:', error);
    throw new Error(error.message || '请求失败');
  }
}

/**
 * 删除命书
 * @param {number} bookId - 命书ID
 * @returns {Promise<void>}
 */
export async function deleteFortuneBook(bookId) {
  try {
    // 添加用户身份信息
    const authHeader = getAuthHeader();
    const url = addUserIdToUrl(`${DELETE_FORTUNE_BOOK_API}/${bookId}`);
    
    const response = await fetch(url, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...authHeader,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || `删除失败: ${response.status}`);
    }

    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || '删除命书失败');
    }

    return result;
  } catch (error) {
    console.error('删除命书异常:', error);
    throw new Error(error.message || '请求失败');
  }
}

/**
 * 生成人生K线数据
 * @param {Object} payload - 请求数据（year, month, day, hour, minute, lng, lat, gender, name）
 * @returns {Promise<Object>} 返回人生K线数据
 */
export async function generateLifeLine(payload) {
  try {
    console.log('🌐 调用 generateLifeLine API');
    console.log('🌐 API URL:', LIFE_LINE_API);
    console.log('📦 请求参数类型:', typeof payload);
    console.log('📦 请求参数:', payload);
    console.log('📦 请求参数 JSON:', JSON.stringify(payload, null, 2));
    
    // 验证参数
    if (!payload) {
      throw new Error('请求参数为空');
    }
    
    const requiredFields = ['year', 'month', 'day', 'lng', 'lat'];
    const missingFields = requiredFields.filter(field => !payload[field] && payload[field] !== 0);
    if (missingFields.length > 0) {
      throw new Error(`缺少必要参数: ${missingFields.join(', ')}`);
    }
    
    const response = await fetch(LIFE_LINE_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    
    console.log('📥 API 响应状态:', response.status, response.statusText);
    console.log('📥 API 响应 headers:', Object.fromEntries(response.headers.entries()));

    if (!response.ok) {
      let errorMessage = `HTTP error! status: ${response.status}`;
      try {
        const errorData = await response.json();
        console.error('❌ API 错误响应:', errorData);
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch (e) {
        const errorText = await response.text();
        console.error('❌ API 错误响应（文本）:', errorText);
        errorMessage = errorText || errorMessage;
      }
      throw new Error(errorMessage);
    }

    const result = await response.json();
    console.log('📥 API 响应数据:', result);
    console.log('📥 API 响应数据类型:', typeof result);
    console.log('📥 API 响应 success 字段:', result.success);
    console.log('📥 API 响应 data 字段存在:', 'data' in result);
    
    if (!result) {
      throw new Error('API 返回数据为空');
    }
    
    if (result.success === false) {
      console.error('❌ API 返回 success: false');
      throw new Error(result.error || result.message || '生成人生K线失败');
    }

    if (!result.data) {
      console.error('❌ API 返回数据中没有 data 字段');
      console.error('❌ 完整响应:', JSON.stringify(result, null, 2));
      throw new Error('API 返回数据格式错误：缺少 data 字段');
    }

    console.log('✅ API 调用成功，返回数据:', result.data);
    console.log('✅ chart_data 长度:', result.data.chart_data?.length);
    return result.data;
  } catch (error) {
    console.error('❌ generateLifeLine 调用失败:', error);
    console.error('❌ 错误堆栈:', error.stack);
    throw new Error(error.message || '请求失败');
  }
}
