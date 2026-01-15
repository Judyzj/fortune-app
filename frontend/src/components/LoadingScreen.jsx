import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';

/**
 * 玄学风格的加载界面
 * 带有环形进度条（不显示数字）
 */
export default function LoadingScreen({ progress: externalProgress = null }) {
  const [progress, setProgress] = useState(0);

  // 如果外部传入进度，使用外部进度；否则使用模拟进度
  useEffect(() => {
    if (externalProgress !== null) {
      setProgress(externalProgress);
      return;
    }

    // 模拟进度：0-95%
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 95) {
          return 95; // 保持在95%，等待真实数据
        }
        // 前30%快速，中间40%中等，最后25%慢速
        let increment = 0;
        if (prev < 30) {
          increment = 2 + Math.random() * 2; // 2-4%
        } else if (prev < 70) {
          increment = 1 + Math.random() * 1.5; // 1-2.5%
        } else {
          increment = 0.5 + Math.random() * 0.8; // 0.5-1.3%
        }
        return Math.min(prev + increment, 95);
      });
    }, 200);

    return () => clearInterval(progressInterval);
  }, [externalProgress]);

  // 旋转的阴阳八卦动画
  const yinYangVariants = {
    rotate: {
      rotate: 360,
      transition: {
        duration: 3,
        repeat: Infinity,
        ease: "linear"
      }
    }
  };

  // 文字淡入淡出动画
  const textVariants = {
    animate: {
      opacity: [0.5, 1, 0.5],
      transition: {
        duration: 2,
        repeat: Infinity,
        ease: "easeInOut"
      }
    }
  };

  // 计算环形进度条的参数
  const size = 160; // SVG 大小
  const strokeWidth = 6; // 进度条宽度
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <motion.div
      className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-gray-50 to-gray-100"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      {/* 阴阳八卦图标 + 环形进度条 */}
      <div className="relative mb-8">
        {/* 环形进度条 SVG */}
        <svg
          width={size}
          height={size}
          className="absolute top-0 left-0"
          style={{ transform: 'rotate(-90deg)' }}
        >
          {/* 背景圆环 */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={strokeWidth}
          />
          {/* 进度圆环 */}
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="url(#progressGradient)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          />
          {/* 渐变定义 */}
          <defs>
            <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#3b82f6" />
              <stop offset="50%" stopColor="#8b5cf6" />
              <stop offset="100%" stopColor="#ec4899" />
            </linearGradient>
          </defs>
        </svg>

        {/* 阴阳八卦图标（居中） */}
        <motion.div
          className="relative w-32 h-32"
          style={{ margin: `${(size - 128) / 2}px` }}
          variants={yinYangVariants}
          animate="rotate"
        >
          <svg
            viewBox="0 0 100 100"
            className="w-full h-full"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* 外圆 */}
            <circle cx="50" cy="50" r="50" fill="#1a1a1a" />
            {/* 白色半圆 */}
            <path
              d="M 50 0 A 50 50 0 0 1 50 100 Z"
              fill="#ffffff"
            />
            {/* 黑色小圆（上） */}
            <circle cx="50" cy="25" r="12" fill="#1a1a1a" />
            {/* 白色小圆（下） */}
            <circle cx="50" cy="75" r="12" fill="#ffffff" />
          </svg>
        </motion.div>
      </div>

      {/* 加载文字 */}
      <motion.div
        className="text-center space-y-4"
        variants={textVariants}
        animate="animate"
      >
        <h2 className="text-2xl font-bold text-gray-900">
          正在批命...
        </h2>
        <p className="text-gray-600 text-lg">
          为您排盘计算中，请稍候
        </p>
      </motion.div>

      {/* 加载点动画 */}
      <div className="flex gap-2 mt-8">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="w-3 h-3 bg-gray-900 rounded-full"
            animate={{
              y: [0, -10, 0],
              opacity: [0.5, 1, 0.5],
            }}
            transition={{
              duration: 1,
              repeat: Infinity,
              delay: i * 0.2,
              ease: "easeInOut"
            }}
          />
        ))}
      </div>
    </motion.div>
  );
}
