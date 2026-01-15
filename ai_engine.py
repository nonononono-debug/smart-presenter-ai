import google.generativeai as genai
import time
import random
import json
import io
from PIL import Image

# --- 1. 连接配置 ---
def configure_genai(api_key):
    try:
        genai.configure(api_key=api_key)
        return True, ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]
    except Exception as e:
        return False, str(e)

# --- 2. 核心：带强制冷却的请求 ---
def generate_with_retry(model, inputs, slide_index, status_callback=None):
    max_retries = 5
    # 免费版 Flash 限制每分钟 15 次 -> 每次间隔至少 4 秒
    # 免费版 Pro 限制每分钟 2 次 -> 每次间隔 30 秒
    
    # 强制冷却：在请求前先休息 2 秒，预防为主
    time.sleep(2) 

    for attempt in range(max_retries):
        try:
            response = model.generate_content(inputs)
            return response
            
        except Exception as e:
            error_str = str(e)
            
            # 遇到 429 限流
            if "429" in error_str or "quota" in error_str.lower():
                # 第一次等 10s，第二次 20s...
                wait_time = 10 * (attempt + 1)
                
                if status_callback:
                    status_callback(slide_index, wait_time, attempt + 1, max_retries)
                
                time.sleep(wait_time)
            else:
                raise e # 其他错误直接抛出
                
    raise Exception("Google API 限流严重，请稍后再试。")

# --- 3. 分析逻辑 ---
def analyze_slide_content(model, slide, index, status_callback=None):
    # (A) 提取文本
    text_runs = []
    for shape in slide.shapes:
        if hasattr(shape, "text"):
            text_runs.append(shape.text)
    slide_text = "\n".join(text_runs)

    # (B) 提取图片
    slide_image = None
    for shape in slide.shapes:
        if shape.shape_type == 13: 
            try:
                image_stream = io.BytesIO(shape.image.blob)
                slide_image = Image.open(image_stream)
                break 
            except:
                pass

    # (C) Prompt
    prompt = """
    Analyze this slide. Output valid JSON only:
    {
        "visual_summary": "1 sentence summary",
        "scripts": {
            "beginner": "Simple tone script",
            "standard": "Business tone script",
            "expert": "Technical tone script"
        },
        "knowledge_extension": {
            "entity": "Keyword",
            "trivia": "Did you know fact"
        }
    }
    """
    
    inputs = [prompt, f"Context: {slide_text}"]
    if slide_image: inputs.append(slide_image)
    
    # 调用重试逻辑
    response = generate_with_retry(model, inputs, index, status_callback)
    
    # 清洗数据
    txt = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(txt)
