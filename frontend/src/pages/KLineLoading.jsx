import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import LoadingScreen from '../components/LoadingScreen';
import { generateKLineChart } from '../utils/api';

/**
 * K线图加载页面
 * 在生成K线图时显示加载动画
 */
export default function KLineLoading() {
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const generateKLine = async () => {
      const payload = location.state?.payload;
      
      if (!payload) {
        setError('缺少必要的参数');
        setTimeout(() => {
          navigate('/kline');
        }, 2000);
        return;
      }

      try {
        console.log('📤 调用 generateKLineChart API，payload:', payload);

        // 调用后端 API 生成 K 线数据，传入进度回调
        const result = await generateKLineChart(payload, (progressValue) => {
          console.log(`📊 进度更新: ${progressValue}%`);
          setProgress(progressValue);
        });
        
        console.log('✅ API 调用成功，返回数据:', result);

        // 跳转到结果页面，传递生成的数据
        navigate('/kline-result', {
          state: {
            klineData: result,
            timestamp: Date.now()
          },
          replace: false
        });

        console.log('✅ 已跳转到结果页面');
      } catch (err) {
        console.error('❌ 生成K线图失败:', err);
        setError(err.message || '生成K线图失败，请稍后重试');
        setTimeout(() => {
          navigate('/kline', { state: { error: err.message } });
        }, 3000);
      }
    };

    generateKLine();
  }, [location, navigate]);

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-screen">
        <div className="text-center max-w-md">
          <div className="text-red-600 mb-4 text-lg font-semibold">{error}</div>
          <p className="text-gray-600 mb-4">正在返回...</p>
          <button
            onClick={() => {
              // 重新尝试
              const payload = location.state?.payload;
              if (payload) {
                navigate('/kline-loading', { state: { payload }, replace: true });
              } else {
                navigate('/kline');
              }
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  return <LoadingScreen progress={progress} />;
}
