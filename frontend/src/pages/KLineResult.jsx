import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, TrendingUp } from 'lucide-react';
import * as echarts from 'echarts';
import LoadingScreen from '../components/LoadingScreen';

/**
 * K 线图结果页面
 * 展示 AI 生成的 K 线图和解读（0-100岁完整数据）
 */
export default function KLineResult() {
  const navigate = useNavigate();
  const location = useLocation();
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [klineData, setKlineData] = useState(null);

  useEffect(() => {
    // 从 location.state 获取数据
    if (location.state?.klineData) {
      console.log('✅ 从 location.state 获取到 K 线数据:', location.state.klineData);
      // 注意：后端返回的是 { success: true, data: {...} }
      // 但 generateKLineChart 已经提取了 data，所以这里直接使用
      const data = location.state.klineData;
      setKlineData(data);
      setLoading(false);
    } else {
      console.error('❌ 未找到 K 线数据');
      setError('未找到 K 线数据，请重新生成');
      setLoading(false);
    }
  }, [location]);

  // 渲染 ECharts 图表
  useEffect(() => {
    if (!klineData || !klineData.chart_data || !chartRef.current) {
      return;
    }

    const chartData = klineData.chart_data;
    const points = chartData.points || [];  // 101个数据点（0-100岁）
    const peaks = chartData.peaks || [];
    const valleys = chartData.valleys || [];
    const currentAge = chartData.current_age || 0;

    console.log('📊 图表数据:', { points: points.length, peaks, valleys, currentAge });

    if (points.length === 0) {
      console.error('❌ 没有数据点');
      return;
    }

    // 提取数据
    const ages = points.map(p => p.age);
    const scores = points.map(p => p.score);
    
    // 初始化图表
    if (chartInstanceRef.current) {
      chartInstanceRef.current.dispose();
    }

    const myChart = echarts.init(chartRef.current);
    chartInstanceRef.current = myChart;

    // 准备高峰和低谷标记数据
    const peakMarkPoints = peaks.map(p => ({
      name: `${p.age}岁峰`,
      coord: [p.age, p.score || scores[p.age] || 0],
      value: p.score || scores[p.age] || 0,
      itemStyle: {
        color: '#10b981',  // 绿色
        borderColor: '#10b981',
        borderWidth: 2
      },
      label: {
        show: true,
        position: 'top',
        formatter: `${p.age}岁峰`,
        color: '#10b981',
        fontSize: 11,
        fontWeight: 'bold'
      }
    }));

    const valleyMarkPoints = valleys.map(v => ({
      name: `${v.age}岁谷`,
      coord: [v.age, v.score || scores[v.age] || 0],
      value: v.score || scores[v.age] || 0,
      itemStyle: {
        color: '#ef4444',  // 红色
        borderColor: '#ef4444',
        borderWidth: 2
      },
      label: {
        show: true,
        position: 'bottom',
        formatter: `${v.age}岁谷`,
        color: '#ef4444',
        fontSize: 11,
        fontWeight: 'bold'
      }
    }));

    // 大运分界点（每10年一个）
    const dayunMarkLines = [];
    const dayunAges = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    dayunAges.forEach(age => {
      if (age > 0 && age < 100) {
        dayunMarkLines.push({
          xAxis: age,
          lineStyle: {
            type: 'dashed',
            color: '#94a3b8',
            width: 1
          },
          label: {
            show: false
          }
        });
      }
    });

    // 当前年龄指示线
    const currentAgeMarkLine = currentAge > 0 && currentAge <= 100 ? [{
      xAxis: currentAge,
      lineStyle: {
        type: 'solid',
        color: '#3b82f6',
        width: 2
      },
      label: {
        show: true,
        position: 'insideEndTop',
        formatter: `今年${currentAge}岁`,
        color: '#3b82f6',
        fontSize: 12,
        fontWeight: 'bold',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        padding: [4, 8],
        borderRadius: 4
      }
    }] : [];

    const option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          label: {
            backgroundColor: '#6a7985'
          }
        },
        formatter: function(params) {
          const age = params[0].axisValue;
          const point = points[age];
          let result = `<div style="padding: 8px;">`;
          result += `<strong>${age}岁 (${point?.year || ''}年)</strong><br/>`;
          result += `流年: ${point?.gan_zhi || ''}<br/>`;
          result += `大运: ${point?.da_yun || ''}<br/>`;
          result += `运势: <strong>${params[0].value}分</strong><br/>`;
          result += '</div>';
          return result;
        }
      },
      legend: {
        data: ['运势曲线'],
        top: 10,
        right: 20,
        textStyle: {
          fontSize: 12
        }
      },
      grid: {
        left: '5%',
        right: '5%',
        bottom: '15%',
        top: '15%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: ages,
        name: '年龄',
        nameLocation: 'middle',
        nameGap: 30,
        nameTextStyle: {
          fontSize: 12,
          color: '#666'
        },
        axisLine: {
          show: true,
          lineStyle: {
            color: '#e0e0e0'
          }
        },
        axisTick: {
          show: false
        },
        axisLabel: {
          color: '#666',
          fontSize: 10,
          interval: 9,  // 每10年显示一个标签
          formatter: function(value) {
            if (value === 0 || value === 100 || value % 20 === 0) {
              return value + '岁';
            }
            return '';
          }
        },
        splitLine: {
          show: false
        }
      },
      yAxis: {
        type: 'value',
        name: '运势分数',
        min: 0,
        max: 100,
        nameLocation: 'middle',
        nameGap: 50,
        nameTextStyle: {
          fontSize: 12,
          color: '#666'
        },
        axisLine: {
          show: false
        },
        axisTick: {
          show: false
        },
        axisLabel: {
          color: '#666',
          fontSize: 11
        },
        splitLine: {
          show: true,
          lineStyle: {
            type: 'dashed',
            color: '#f0f0f0',
            width: 1
          }
        }
      },
      series: [
        {
          name: '运势曲线',
          type: 'line',
          data: scores,
          smooth: true,
          symbol: 'none',
          lineStyle: {
            color: '#3b82f6',
            width: 3
          },
          itemStyle: {
            color: '#3b82f6'
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
                { offset: 1, color: 'rgba(59, 130, 246, 0.05)' }
              ]
            }
          },
          markPoint: {
            data: [...peakMarkPoints, ...valleyMarkPoints],
            symbolSize: 50
          },
          markLine: {
            data: [...dayunMarkLines, ...currentAgeMarkLine],
            symbol: ['none', 'none']
          }
        }
      ]
    };

    myChart.setOption(option);

    // 响应式调整
    const handleResize = () => {
      myChart.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartInstanceRef.current) {
        chartInstanceRef.current.dispose();
        chartInstanceRef.current = null;
      }
    };
  }, [klineData]);

  // 显示加载进度
  if (loading) {
    return <LoadingScreen />;
  }

  // 错误处理
  if (error) {
    return (
      <div className="flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-red-800 mb-2">错误</h3>
            <p className="text-red-600 mb-4">{error}</p>
            <button
              onClick={() => navigate('/kline')}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              返回重新生成
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!klineData) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-gray-600 mb-4">未找到数据</p>
          <button
            onClick={() => navigate('/kline')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            返回重新生成
          </button>
        </div>
      </div>
    );
  }

  // 适配新的数据格式
  const analysisText = klineData.analysis_text || '';
  const chartData = klineData.chart_data || {};
  const points = chartData.points || [];
  const peaks = chartData.peaks || [];
  const valleys = chartData.valleys || [];
  const currentAge = chartData.current_age || 0;

  // 获取当前年龄的详细信息
  const currentPoint = points[currentAge] || null;

  return (
    <div className="flex-1 min-h-screen bg-gray-50">
      {/* 头部导航 */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <button
            onClick={() => navigate('/kline')}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>返回</span>
          </button>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-gray-700" />
            <h1 className="text-xl font-semibold text-gray-900">人生运势K线图</h1>
          </div>
          <div className="w-20"></div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto p-6 space-y-6">
        {/* 当前年龄详细信息卡片 */}
        {currentPoint && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">当前运势</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-gray-500 mb-1">年龄</div>
                <div className="text-lg font-medium text-gray-900">{currentAge}岁</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">年份</div>
                <div className="text-lg font-medium text-gray-900">{currentPoint.year}年</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">流年</div>
                <div className="text-lg font-medium text-gray-900">{currentPoint.gan_zhi}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">大运</div>
                <div className="text-lg font-medium text-gray-900">{currentPoint.da_yun}</div>
              </div>
            </div>
            <div className="mt-4">
              <div className="text-xs text-gray-500 mb-1">当前运势分数</div>
              <div className="text-3xl font-bold text-blue-600">{currentPoint.score}分</div>
            </div>
          </div>
        )}

        {/* K 线图表 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">人生运势K线图 (0-100岁)</h2>
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span className="text-gray-600">高峰</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <span className="text-gray-600">低谷</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                <span className="text-gray-600">当前年龄</span>
              </div>
            </div>
          </div>
          
          {/* 图表容器 */}
          <div 
            ref={chartRef}
            style={{ width: '100%', height: '500px' }}
          ></div>
          
          <div className="mt-4 text-xs text-gray-500 text-center">
            拖拽滑动查看，点击查看详情
          </div>
        </div>

        {/* 高峰和低谷列表 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* 人生高峰期 */}
          {peaks.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">人生高峰期</h3>
                <span className="text-xs text-gray-500">点击查看</span>
              </div>
              <div className="space-y-3">
                {peaks.map((peak, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                    <div>
                      <div className="font-medium text-gray-900">{peak.age}岁</div>
                      <div className="text-xs text-gray-600">{peak.reason || '运势高峰'}</div>
                    </div>
                    <div className="text-lg font-bold text-green-600">{peak.score || 0}分</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 需关注时期 */}
          {valleys.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">需关注时期</h3>
                <span className="text-xs text-gray-500">点击查看</span>
              </div>
              <div className="space-y-3">
                {valleys.map((valley, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                    <div>
                      <div className="font-medium text-gray-900">{valley.age}岁</div>
                      <div className="text-xs text-gray-600">{valley.reason || '需谨慎'}</div>
                    </div>
                    <div className="text-lg font-bold text-red-600">{valley.score || 0}分</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* AI 解读 */}
        {analysisText && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
                <span className="text-white text-sm font-bold">AI</span>
              </div>
              <h2 className="text-lg font-semibold text-gray-900">AI深度解读</h2>
            </div>
            <div className="prose max-w-none">
              <div className="whitespace-pre-wrap text-gray-700 leading-relaxed text-sm">
                {analysisText}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
