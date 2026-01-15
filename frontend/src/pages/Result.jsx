import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { fetchFortuneAnalysis } from '../utils/api';
import ResultStream from '../components/ResultStream';
import ReportContainer from '../components/ReportContainer';
import { extractPersonalityTraits, extractEssenceText } from '../utils/baziUtils';

export default function Result() {
  const navigate = useNavigate();
  const { id } = useParams(); // 从URL获取ID
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [text, setText] = useState('');
  const [chartData, setChartData] = useState(null);
  const [calculation, setCalculation] = useState(null);
  const [isStreaming, setIsStreaming] = useState(true);
  const [formData, setFormData] = useState(null);

  useEffect(() => {
    // 如果URL中有ID，从API加载命书数据
    if (id) {
      loadFortuneBookById(id);
      return;
    }

    // 否则从 localStorage 获取表单数据（兼容旧逻辑）
    const savedFormData = localStorage.getItem('fortuneFormData');
    if (!savedFormData) {
      navigate('/create');
      return;
    }

    const data = JSON.parse(savedFormData);
    setFormData(data);

    // 开始调用 API
    setLoading(true);
    setIsStreaming(true);
    setText('');
    setChartData(null);
    setCalculation(null);
    setError(null);

    fetchFortuneAnalysis(data, {
      onText: (content) => {
        setText((prev) => prev + content);
      },
      onChartData: (data) => {
        setChartData(data);
      },
      onCalculation: (data) => {
        setCalculation(data);
      },
      onError: (errorMsg) => {
        setError(errorMsg);
        setLoading(false);
        setIsStreaming(false);
      },
      onComplete: () => {
        setLoading(false);
        setIsStreaming(false);
      },
    });
  }, [navigate, id]);

  // 根据ID加载命书数据
  const loadFortuneBookById = async (bookId) => {
    try {
      setLoading(true);
      setError(null);

      // 调用API获取命书详情
      const response = await fetch(`http://localhost:8000/api/fortune-books/${bookId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('命书不存在：未找到该ID对应的命书数据');
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `获取命书失败: ${response.status}`);
      }

      const result = await response.json();
      
      if (!result.success) {
        throw new Error(result.error || '获取命书失败');
      }

      const bookData = result.data;
      
      // 解析summary数据
      let summaryData = {};
      if (bookData.summary) {
        try {
          summaryData = typeof bookData.summary === 'string' 
            ? JSON.parse(bookData.summary) 
            : bookData.summary;
        } catch (e) {
          console.error('解析summary失败:', e);
        }
      }

      // 设置表单数据
      setFormData({
        name: bookData.person_name || bookData.name || '未命名',
        city: bookData.city || '',
        year: bookData.birth_date ? bookData.birth_date.split('-')[0] : '',
        month: bookData.birth_date ? bookData.birth_date.split('-')[1] : '',
        day: bookData.birth_date ? bookData.birth_date.split('-')[2] : '',
        hour: bookData.birth_time ? bookData.birth_time.split(':')[0] : '',
        minute: bookData.birth_time ? bookData.birth_time.split(':')[1] : '',
        gender: bookData.gender || 'male',
        lat: bookData.lat || '',
        lng: bookData.lng || '',
      });

      // 设置排盘数据
      if (summaryData.bazi_report) {
        setCalculation(summaryData.bazi_report);
      }

      // 设置AI分析文本
      if (summaryData.llm_data) {
        if (summaryData.llm_data.analysis_text) {
          setText(summaryData.llm_data.analysis_text);
        }
        setIsStreaming(false);
      }

      setLoading(false);
    } catch (err) {
      console.error('加载命书失败:', err);
      setError(err.message || '加载命书失败，请稍后重试');
      setLoading(false);
    }
  };

  if (error) {
    return (
      <div className="flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h2 className="text-xl font-bold text-red-800 mb-2">错误</h2>
            <p className="text-red-600">{error}</p>
            <button
              onClick={() => navigate('/create')}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              返回表单
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1">
      {/* 加载状态 */}
      {loading && !calculation && (
        <div className="flex items-center justify-center min-h-screen bg-gray-50">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mb-4"></div>
            <p className="text-gray-600 text-lg">正在排盘中...</p>
          </div>
        </div>
      )}

      {/* 命理报告概览 */}
      {calculation && formData && (
        <ReportContainer
          calculation={calculation}
          name={formData.name}
          city={formData.city}
          trueSolarTime={calculation.true_solar_time}
          personalityTraits={useMemo(() => extractPersonalityTraits(text), [text])}
          essenceText={useMemo(() => {
            const dayGan = calculation?.chart?.day_gan || calculation?.gods?.day_gan || '';
            const dayWuxing = calculation?.gods?.day_wuxing || '';
            return extractEssenceText(text, dayGan, dayWuxing);
          }, [text, calculation])}
        />
      )}

      {/* 流式文本分析（在报告下方） */}
      {calculation && (
        <div className="max-w-6xl mx-auto px-4 py-8">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-2xl font-bold mb-4 text-gray-900">命理精华</h2>
            {(text || isStreaming) && (
              <ResultStream text={text} isStreaming={isStreaming} />
            )}
          </div>
        </div>
      )}

      {/* 图表数据（可选） */}
      {chartData && (
        <div className="max-w-6xl mx-auto px-4 pb-8">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-xl font-bold mb-4 text-gray-900">运势评分图表</h2>
            <p className="text-gray-600 text-sm mb-4">
              图表数据已接收（可在此处添加图表组件显示）
            </p>
            <pre className="text-xs bg-gray-50 p-4 rounded overflow-auto">
              {JSON.stringify(chartData, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* 完成后的操作按钮 */}
      {!loading && !isStreaming && calculation && (
        <div className="max-w-6xl mx-auto px-4 pb-8">
          <div className="flex gap-4">
            <button
              onClick={() => navigate('/create')}
              className="px-6 py-3 bg-black text-white rounded-lg hover:bg-gray-800 transition-colors"
            >
              创建新的命理
            </button>
            <button
              onClick={() => navigate('/')}
              className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              返回首页
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
