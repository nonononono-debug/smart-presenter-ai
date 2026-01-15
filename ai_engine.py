import google.generativeai as genai
import time
import random
import json
import io
from PIL import Image

# --- 1. 连接与模型获取 ---
def configure_genai(api_key):
    """配置 API Key 并返回可用模型列表"""
    try:
        genai.configure(api_key=api_key)
        models = genai.list_models()
        available_models = []
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        return True, available_models
    except Exception as e:
        return False, str(e)

# --- 2. 核心：带指数退避的重试请求 ---
def generate_with_retry(model, inputs, slide_index, status_callback=None):
    """
    死磕模式的核心函数。
    status_callback: 一个函数，用来向 UI 发送状态更新（比如“正在冷却...”）
    """
    max_retries = 10
    base_wait_time = 10
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(inputs)
            return response
            
        except Exception as e:
            error_str = str(e)
            
            # 识别限流 (429) 或 服务过载 (503)
            if "429" in error_str or "quota" in error_str.lower() or "503" in error_str:
                wait_time = base_wait_time * (attempt + 1) + random.randint(1, 5)
                
                # 如果 UI 传了回调函数，就通知 UI 更新状态
                if status_callback:
                    status_callback(slide_index, wait_time, attempt + 1, max_retries)
                
                time.sleep(wait_time)
            else:
                # 其他错误（如图片格式错误）直接抛出，不重试
                raise e
                
    raise Exception("重试次数耗尽，Google API 暂时不可用。")

# --- 3. 单页分析逻辑 ---
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
    Analyze this slide. Output valid JSON only (no markdown formatting).
    JSON Structure:
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
    
    # (D) 调用重试逻辑
    response = generate_with_retry(model, inputs, index, status_callback)
    
    # (E) 清洗数据
    txt = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(txt)
