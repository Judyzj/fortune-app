"""
优化后的K线生成接口 - 简化版本，提高速度和稳定性
"""
import asyncio
import json
import re
from datetime import datetime
from fastapi import HTTPException
from fastapi.responses import JSONResponse

async def generate_kline_optimized(request, calculator, compass_client, deepseek_api_key, deepseek_base_url):
    """
    优化后的K线生成函数
    - 移除多余的LLM调用
    - 使用非流式API（更快更稳定）
    - 添加30秒超时
    - 改进错误处理
    """
    try:
        # 1. 准备数据（复用现有逻辑）
        birth_date = request.birth_date
        birth_time = request.birth_time
        lat = request.lat
        lng = request.lng
        gender = request.gender
        name = request.name or "用户"
        
        # 2. 生成八字数据
        bazi_report = calculator.generate_bazi_report(
            birth_date=birth_date,
            birth_time=birth_time,
            lng=lng,
            lat=lat,
            gender=gender
        )
        
        # 3. 提取关键信息
        chart = bazi_report['chart']
        gods = bazi_report['gods']
        da_yun = bazi_report['da_yun']
        day_master = chart.get('day_gan', '')
        day_wuxing = gods.get('day_wuxing', '')
        yong_shen = gods.get('useful_gods', [])
        
        # 4. 计算时间轴
        birth_year = datetime.strptime(birth_date, "%Y-%m-%d").year
        current_year = datetime.now().year
        current_age = current_year - birth_year
        
        timeline_data = []
        for age in range(101):
            year = birth_year + age
            from lunar_python import Solar
            solar = Solar.fromYmd(year, 1, 1)
            lunar = solar.getLunar()
            liu_nian_gan_zhi = lunar.getYearGan() + lunar.getYearZhi()
            
            current_dayun = ''
            for dy in da_yun:
                if dy.get('age_start', 0) <= age < dy.get('age_end', 100):
                    current_dayun = dy.get('gan_zhi', '')
                    break
            
            timeline_data.append({
                'age': age,
                'year': year,
                'gan_zhi': liu_nian_gan_zhi,
                'da_yun': current_dayun
            })
        
        # 5. 构建精简Prompt
        kline_prompt = f"""根据八字生成0-100岁K线数据，只返回JSON：

日主: {day_master}（{day_wuxing}）
用神: {', '.join(yong_shen[:3]) if yong_shen else '无'}
大运: {'; '.join([f"{dy.get('age_start', 0)}-{dy.get('age_end', 100)}岁:{dy.get('gan_zhi', '')}" for dy in da_yun[:6]])}

返回格式（纯JSON，无Markdown）：
{{
  "scores": [101个整数，0-100，对应0-100岁],
  "peaks": [{{"age": 13, "score": 85, "reason": "简短原因"}}, ...],
  "valleys": [{{"age": 10, "score": 31, "reason": "简短原因"}}, ...],
  "summary": "100字总结"
}}

要求：scores必须101个，peaks/valleys各3-5个，只返回JSON。
"""
        
        # 6. 调用AI API（非流式，带超时）
        ai_response = None
        ai_call_success = False
        
        # 尝试Compass API
        if compass_client:
            try:
                print("🔄 调用 Compass API（非流式，30秒超时）...", flush=True)
                # 使用 asyncio.wait_for 添加超时
                async def call_compass():
                    response = compass_client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=kline_prompt,
                        config={
                            "response_mime_type": "application/json",
                            "temperature": 0.7,
                            "max_output_tokens": 2000
                        }
                    )
                    if hasattr(response, 'text'):
                        return response.text
                    elif hasattr(response, 'candidates') and response.candidates:
                        if hasattr(response.candidates[0], 'content'):
                            if hasattr(response.candidates[0].content, 'parts'):
                                return ''.join([part.text for part in response.candidates[0].content.parts if hasattr(part, 'text')])
                    return None
                
                try:
                    response_text = await asyncio.wait_for(call_compass(), timeout=30.0)
                    if response_text:
                        ai_response = response_text
                        ai_call_success = True
                        print("✅ Compass API 调用成功", flush=True)
                except asyncio.TimeoutError:
                    print("⏰ Compass API 调用超时（30秒）", flush=True)
                except Exception as e:
                    print(f"❌ Compass API 调用失败: {e}", flush=True)
            except Exception as e:
                print(f"❌ Compass API 异常: {e}", flush=True)
        
        # 如果Compass失败，尝试DeepSeek
        if not ai_call_success and deepseek_api_key:
            try:
                print("🔄 调用 DeepSeek API（非流式，30秒超时）...", flush=True)
                import httpx
                
                async def call_deepseek():
                    url = f"{deepseek_base_url}/chat/completions"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {deepseek_api_key}"
                    }
                    payload = {
                        "model": "deepseek-chat",
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是一位精通八字命理的大师，请严格按照 JSON 格式返回结果。"
                            },
                            {
                                "role": "user",
                                "content": kline_prompt
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2000,
                        "response_format": {"type": "json_object"}
                    }
                    
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(url, json=payload, headers=headers)
                        response.raise_for_status()
                        result = response.json()
                        return result["choices"][0]["message"]["content"]
                
                try:
                    response_text = await asyncio.wait_for(call_deepseek(), timeout=30.0)
                    if response_text:
                        ai_response = response_text
                        ai_call_success = True
                        print("✅ DeepSeek API 调用成功", flush=True)
                except asyncio.TimeoutError:
                    print("⏰ DeepSeek API 调用超时（30秒）", flush=True)
                except Exception as e:
                    print(f"❌ DeepSeek API 调用失败: {e}", flush=True)
            except Exception as e:
                print(f"❌ DeepSeek API 异常: {e}", flush=True)
        
        # 7. 解析JSON（带容错）
        scores = [60] * 101  # 默认值
        peaks = []
        valleys = []
        analysis_text = "基于八字和大运分析，整体运势平稳发展。"
        
        if ai_call_success and ai_response:
            try:
                # 清洗JSON
                clean_json = ai_response.replace("```json", "").replace("```", "").strip()
                
                # 尝试解析
                try:
                    data = json.loads(clean_json)
                except json.JSONDecodeError:
                    # 尝试提取JSON对象
                    json_match = re.search(r'\{.*\}', clean_json, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(0))
                    else:
                        raise ValueError("无法解析JSON")
                
                # 提取数据
                scores = data.get("scores", [])
                peaks = data.get("peaks", [])
                valleys = data.get("valleys", [])
                analysis_text = data.get("summary", analysis_text)
                
                # 验证和修复scores数组
                if len(scores) != 101:
                    if len(scores) < 101:
                        scores.extend([60] * (101 - len(scores)))
                    else:
                        scores = scores[:101]
                
                # 验证peaks和valleys
                peaks = [p for p in peaks if isinstance(p, dict) and 'age' in p and 0 <= p['age'] <= 100]
                valleys = [v for v in valleys if isinstance(v, dict) and 'age' in v and 0 <= v['age'] <= 100]
                
                print(f"✅ JSON解析成功: scores={len(scores)}, peaks={len(peaks)}, valleys={len(valleys)}", flush=True)
            except Exception as e:
                print(f"⚠️  JSON解析失败，使用默认数据: {e}", flush=True)
        
        # 8. 构建返回数据
        chart_points = []
        for i, timeline_point in enumerate(timeline_data):
            age = timeline_point['age']
            score = scores[i] if i < len(scores) else 60
            is_peak = any(p.get('age') == age for p in peaks)
            is_valley = any(v.get('age') == age for v in valleys)
            
            chart_points.append({
                "age": age,
                "year": timeline_point['year'],
                "gan_zhi": timeline_point['gan_zhi'],
                "da_yun": timeline_point['da_yun'],
                "score": score,
                "is_peak": is_peak,
                "is_valley": is_valley
            })
        
        # 9. 计算当前运势
        current_score = scores[current_age] if current_age < len(scores) else 60
        current_label = "吉" if current_score >= 70 else ("平" if current_score >= 50 else "凶")
        
        # 10. 构建完整响应
        chart_data = {
            "points": chart_points,
            "peaks": peaks,
            "valleys": valleys,
            "current_age": current_age,
            "current_fortune": {
                "score": current_score,
                "label": current_label
            },
            "analysis_text": analysis_text
        }
        
        return JSONResponse({
            "success": True,
            "data": {
                "chart_data": chart_data,
                "analysis_text": analysis_text
            }
        })
        
    except Exception as e:
        print(f"❌ K线生成失败: {e}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
        raise HTTPException(status_code=500, detail=f"生成K线数据失败: {str(e)}")
