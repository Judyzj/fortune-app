"""
人生 K 线核心服务
结合 lunar_python (精准历法) 和 DeepSeek (大模型推理)
"""
import os
import json
import re
import asyncio
import httpx
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from calculator import FortuneCalculator
from schemas import LifeCurveResponse, ChartDataPoint, PeakValley


class LifeLineService:
    """人生 K 线服务"""
    
    def __init__(self):
        self.calculator = FortuneCalculator()
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url = os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com/v1")
    
    def _calculate_timeline(
        self, 
        birth_date: str, 
        birth_time: str,
        lng: float,
        lat: float,
        gender: str
    ) -> List[Dict]:
        """
        Step A: 硬计算 - 生成 0-100 岁的时间轴
        
        使用 lunar_python 计算：
        1. 八字原局
        2. 大运列表
        3. 每年对应的流年干支
        
        Returns:
            时间轴列表，每个元素包含 age, year, gan_zhi, da_yun
        """
        # 1. 计算真太阳时
        true_solar_time = self.calculator.calculate_true_solar_time(
            birth_date, birth_time, lng, lat
        )
        
        # 2. 计算四柱（八字原局）
        si_zhu = self.calculator.get_si_zhu(true_solar_time)
        bazi = [
            si_zhu['year_gan'] + si_zhu['year_zhi'],  # 年柱
            si_zhu['month_gan'] + si_zhu['month_zhi'],  # 月柱
            si_zhu['day_gan'] + si_zhu['day_zhi'],  # 日柱
            si_zhu['hour_gan'] + si_zhu['hour_zhi']  # 时柱
        ]
        
        # 3. 计算大运
        da_yun_list = self.calculator.calculate_da_yun(si_zhu, gender, birth_date)
        
        # 4. 生成 0-100 岁的时间轴（每年一个数据点）
        timeline = []
        birth_year = true_solar_time.year
        birth_month = true_solar_time.month
        birth_day = true_solar_time.day
        
        for age in range(101):  # 0-100 岁
            year = birth_year + age
            
            # 计算该年龄对应的流年干支
            # 流年干支就是该年的农历年干支
            from lunar_python import Solar
            solar = Solar.fromYmd(year, 1, 1)  # 使用该年的1月1日计算年干支
            lunar = solar.getLunar()
            year_gan = lunar.getYearGan()
            year_zhi = lunar.getYearZhi()
            liu_nian_gan_zhi = year_gan + year_zhi
            
            # 判断当前年龄属于哪个大运
            # 大运通常每10年一换
            current_dayun = ''
            if da_yun_list:
                # 找到当前年龄对应的大运
                for i, dayun_info in enumerate(da_yun_list):
                    age_start = dayun_info.get('age_start', i * 10)
                    age_end = dayun_info.get('age_end', (i + 1) * 10)
                    
                    if age_start <= age < age_end:
                        current_dayun = dayun_info.get('gan_zhi', '')
                        break
                
                # 如果年龄超过最后一个大运，使用最后一个大运
                if not current_dayun and da_yun_list:
                    last_dayun = da_yun_list[-1]
                    if age >= last_dayun.get('age_end', 80):
                        current_dayun = last_dayun.get('gan_zhi', '')
            
            timeline.append({
                'age': age,
                'year': year,
                'gan_zhi': liu_nian_gan_zhi,
                'da_yun': current_dayun,
                'bazi': bazi
            })
        
        return timeline, bazi, da_yun_list
    
    def _clean_ai_response(self, text: str) -> Dict:
        """
        清洗 AI 返回的响应文本，提取 JSON 数据
        
        Args:
            text: AI 返回的原始文本
        
        Returns:
            解析后的 JSON 字典
        
        Raises:
            ValueError: 如果无法解析 JSON
        """
        if not text:
            raise ValueError("AI 返回内容为空")
        
        print(f"🔍 开始清洗 AI 响应，原始内容长度: {len(text)}", flush=True)
        
        # 尝试提取 markdown 代码块中的 JSON
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
            print(f"✅ 从 markdown 代码块中提取到 JSON，长度: {len(json_str)}", flush=True)
        else:
            # 尝试提取大括号内的内容
            brace_match = re.search(r"\{.*\}", text, re.DOTALL)
            if brace_match:
                json_str = brace_match.group(0).strip()
                print(f"✅ 从大括号中提取到 JSON，长度: {len(json_str)}", flush=True)
            else:
                # 如果没有 markdown 标记，尝试直接使用整个文本
                json_str = text.strip()
                print(f"⚠️  未找到 markdown 标记，尝试直接解析整个文本", flush=True)
        
        # 尝试解析 JSON
        try:
            result = json.loads(json_str)
            print(f"✅ JSON 解析成功", flush=True)
            return result
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {str(e)}", flush=True)
            print(f"❌ 原始 AI 响应内容（前 500 字符）:", flush=True)
            print(text[:500], flush=True)
            print(f"❌ 原始 AI 响应内容（完整）:", flush=True)
            print(text, flush=True)
            print(f"❌ 尝试解析的 JSON 字符串（前 500 字符）:", flush=True)
            print(json_str[:500], flush=True)
            raise ValueError(f"无法解析 AI 返回的 JSON: {str(e)}")
    
    def _build_prompt(self, bazi: List[str], da_yun_list: List[Dict]) -> str:
        """
        Step B: 构造 Prompt
        
        将八字原局和大运列表放入 System Prompt
        """
        # 格式化大运列表
        dayun_text = ""
        for i, dy in enumerate(da_yun_list):
            age_start = dy.get('age_start', 0)
            age_end = dy.get('age_end', 10)
            gan_zhi = dy.get('gan_zhi', '')
            dayun_text += f"{age_start}-{age_end}岁: {gan_zhi}\n"
        
        prompt = f"""你是一位精通八字命理的大师。请根据用户的八字原局和大运，推演其 0-100 岁的运势曲线。

用户八字原局：
年柱：{bazi[0]}
月柱：{bazi[1]}
日柱：{bazi[2]}
时柱：{bazi[3]}

大运列表：
{dayun_text}

请严格返回 JSON 格式，包含以下字段：
{{
  "scores": [60, 62, 55, ...],  // 101个整数，对应0-100岁的运势分数（0-100分）
  "peaks": [
    {{"age": 26, "reason": "官印相生，事业高峰"}},
    {{"age": 45, "reason": "财星当令，财运亨通"}}
  ],  // 3-5个高峰年份
  "valleys": [
    {{"age": 30, "reason": "岁运并临，需谨慎"}},
    {{"age": 55, "reason": "冲克日主，注意健康"}}
  ],  // 3-5个低谷年份
  "advice": "整体运势呈上升趋势。建议在高峰年份把握机会，低谷年份谨慎行事，注意健康和安全。"
}}

要求：
1. scores 数组必须包含 101 个整数（0-100岁，共101个数据点）
2. 分数范围：0-100，其中 60-70 为平稳，70-85 为良好，85-100 为优秀，40-60 为一般，0-40 为较差
3. peaks 和 valleys 各包含 3-5 个关键年份
4. 根据八字和大运的五行生克关系，合理推演运势变化
5. 必须返回有效的 JSON 格式，不要包含任何其他文字"""
        
        return prompt
    
    async def _call_deepseek_api(self, prompt: str) -> Dict:
        """
        Step C: 调用 DeepSeek API
        
        使用 httpx 异步调用 DeepSeek API
        """
        if not self.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置，请在 .env 文件中设置")
        
        url = f"{self.deepseek_base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位精通八字命理的大师，擅长根据八字和大运推演人生运势。请严格按照 JSON 格式返回结果。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        # 重试机制：最多重试2次
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # 增加超时时间到60秒
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    result = response.json()
                    
                    # 提取回复内容
                    content = result["choices"][0]["message"]["content"]
                    print(f"📥 AI 返回原始内容长度: {len(content)}", flush=True)
                    
                    # 使用清洗函数解析 JSON
                    return self._clean_ai_response(content)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    print(f"⚠️  DeepSeek API 调用失败（尝试 {attempt + 1}/{max_retries + 1}），1秒后重试...", flush=True)
                    await asyncio.sleep(1)
                else:
                    print(f"❌ DeepSeek API 调用失败（已重试 {max_retries} 次）: {e}", flush=True)
                    raise
    
    def _merge_data(
        self,
        timeline: List[Dict],
        ai_response: Dict,
        birth_year: int
    ) -> List[ChartDataPoint]:
        """
        Step D: 数据融合
        
        将 AI 返回的 scores、peaks、valleys 与时间轴合并
        """
        scores = ai_response.get("scores", [])
        peaks = ai_response.get("peaks", [])
        valleys = ai_response.get("valleys", [])
        
        # 创建 peaks 和 valleys 的快速查找字典
        peaks_dict = {p["age"]: p for p in peaks}
        valleys_dict = {v["age"]: v for v in valleys}
        
        chart_data = []
        for i, point in enumerate(timeline):
            age = point["age"]
            year = point["year"]
            gan_zhi = point["gan_zhi"]
            da_yun = point.get("da_yun", "")
            
            # 获取分数（确保有 101 个数据点）
            score = scores[i] if i < len(scores) else 60
            
            # 判断是否为高峰或低谷
            is_peak = age in peaks_dict
            is_valley = age in valleys_dict
            
            # 生成详细说明
            if is_peak:
                details = peaks_dict[age].get("reason", "运势高峰")
                label = "吉"
            elif is_valley:
                details = valleys_dict[age].get("reason", "运势低谷")
                label = "凶"
            elif score >= 85:
                details = "运势极佳，把握机会"
                label = "大吉"
            elif score >= 70:
                details = "运势良好，稳步发展"
                label = "吉"
            elif score >= 60:
                details = "运势平稳，按部就班"
                label = "平"
            elif score >= 40:
                details = "运势一般，需谨慎"
                label = "小凶"
            else:
                details = "运势较差，注意防范"
                label = "凶"
            
            chart_data.append(ChartDataPoint(
                age=age,
                year=year,
                score=score,
                is_peak=is_peak,
                is_valley=is_valley,
                gan_zhi=gan_zhi,
                da_yun=da_yun,
                details=details,
                label=label
            ))
        
        return chart_data
    
    async def generate_life_curve(
        self,
        birth_date: str,
        birth_time: str,
        lng: float,
        lat: float,
        gender: str,
        name: str = "用户"
    ) -> LifeCurveResponse:
        """
        生成人生 K 线数据
        
        Args:
            birth_date: 出生日期 (YYYY-MM-DD)
            birth_time: 出生时间 (HH:MM)
            lng: 经度
            lat: 纬度
            gender: 性别 (male/female)
            name: 姓名
        
        Returns:
            LifeCurveResponse 对象
        """
        # Step A: 硬计算 - 生成时间轴
        timeline, bazi, da_yun_list = self._calculate_timeline(
            birth_date, birth_time, lng, lat, gender
        )
        
        # Step B: 构造 Prompt
        prompt = self._build_prompt(bazi, da_yun_list)
        
        # Step C: 调用 DeepSeek API
        ai_response = None
        try:
            print(f"🤖 开始调用 DeepSeek API...", flush=True)
            ai_response = await self._call_deepseek_api(prompt)
            print(f"✅ DeepSeek API 调用成功", flush=True)
        except Exception as e:
            print(f"⚠️  DeepSeek API 调用失败: {e}", flush=True)
            import traceback
            print(traceback.format_exc(), flush=True)
            # 如果 API 调用失败，使用默认数据
            ai_response = {
                "scores": [60] * 101,  # 默认 60 分
                "peaks": [],
                "valleys": [],
                "advice": "API 调用失败，使用默认数据"
            }
        
        # 验证 ai_response 格式
        if not ai_response:
            print(f"⚠️  AI 响应为空，使用默认数据", flush=True)
            ai_response = {
                "scores": [60] * 101,
                "peaks": [],
                "valleys": [],
                "advice": "AI 响应为空，使用默认数据"
            }
        
        # 确保 scores 数组有 101 个元素
        if "scores" not in ai_response or len(ai_response.get("scores", [])) != 101:
            print(f"⚠️  scores 数组长度不正确，当前: {len(ai_response.get('scores', []))}，期望: 101", flush=True)
            scores = ai_response.get("scores", [])
            if len(scores) < 101:
                # 用 60 分填充到 101 个
                scores.extend([60] * (101 - len(scores)))
            elif len(scores) > 101:
                # 截取前 101 个
                scores = scores[:101]
            ai_response["scores"] = scores
        
        # Step D: 数据融合
        birth_year = datetime.strptime(birth_date, "%Y-%m-%d").year
        chart_data = self._merge_data(timeline, ai_response, birth_year)
        
        # 计算当前分数（根据实际出生日期计算当前年龄）
        birth_year = datetime.strptime(birth_date, "%Y-%m-%d").year
        current_year = datetime.now().year
        current_age = min(current_year - birth_year, 100)  # 限制在0-100岁之间
        current_score = chart_data[current_age].score if current_age < len(chart_data) else 60
        
        # 计算趋势（简单判断：最近 5 年的平均分数趋势）
        if len(chart_data) >= 5:
            recent_scores = [d.score for d in chart_data[-5:]]
            avg_recent = sum(recent_scores) / len(recent_scores)
            earlier_scores = [d.score for d in chart_data[-10:-5]] if len(chart_data) >= 10 else recent_scores
            avg_earlier = sum(earlier_scores) / len(earlier_scores) if earlier_scores else avg_recent
            if avg_recent > avg_earlier + 5:
                trend = "上升"
            elif avg_recent < avg_earlier - 5:
                trend = "下降"
            else:
                trend = "平稳"
        else:
            trend = "平稳"
        
        # 格式化 peaks 和 valleys
        peaks = [
            PeakValley(
                age=p["age"],
                year=birth_year + p["age"],
                reason=p.get("reason", ""),
                score=chart_data[p["age"]].score if p["age"] < len(chart_data) else None
            )
            for p in ai_response.get("peaks", [])
        ]
        
        valleys = [
            PeakValley(
                age=v["age"],
                year=birth_year + v["age"],
                reason=v.get("reason", ""),
                score=chart_data[v["age"]].score if v["age"] < len(chart_data) else None
            )
            for v in ai_response.get("valleys", [])
        ]
        
        # 构建响应
        return LifeCurveResponse(
            user_profile={
                "name": name,
                "bazi": bazi
            },
            chart_data=chart_data,
            summary={
                "current_score": current_score,
                "trend": trend,
                "peaks": [p.dict() for p in peaks],
                "valleys": [v.dict() for v in valleys],
                "advice": ai_response.get("advice", "请根据个人实际情况调整人生规划")
            }
        )


# 创建全局服务实例
lifeline_service = LifeLineService()
