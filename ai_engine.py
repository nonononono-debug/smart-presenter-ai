import google.generativeai as genai
import time
import random
import json
import io
from PIL import Image

# --- 1. 智能连接：获取真实模型列表 ---
def configure_genai(api_key):
    try:
        genai.configure(api_key=api_key)
        # 关键修改：不再写死，而是去问 Google "我现在能用什么？"
        all_models = genai.list_models()
        valid_models = []
        for m in all_models:
            # 只找支持生成内容的模型
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
        
        # 如果获取到了列表，就返回真实的列表
        if valid_models:
            return True, valid_models
        else:
            # 万一列表为空（极少见），才用兜底名字
            return True, ["models/gemini-1.5-flash"]
            
    except Exception as e:
        return False, str(e)

# --- 2. 核心：带重试的生成函数 ---
def generate_with_retry(model, inputs, slide_index, status_callback=None):
    max_retries = 3
    # 每次请求前强制休息 3 秒，防止 429
    time.sleep(3) 

    for attempt in range(max_retries):
        try:
            response = model.generate_content(inputs)
            return response
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                wait_time = 10 * (attempt + 1)
                if status_callback:
                    status_callback(slide_index, wait_time, attempt + 1, max_retries)
                time.sleep(wait_time)
            else:
                raise e
                
    raise Exception("Google 限流严重，请稍后再试")

# --- 3. 分析逻辑 ---
def analyze_slide_content(model, slide, index, status_callback=None):
    text_runs = []
    for shape in slide.shapes:
        if hasattr(shape, "text"):
            text_runs.append(shape.text)
    slide_text = "\n".join(text_runs)

    slide_image = None
    for shape in slide.shapes:
        if shape.shape_type == 13: 
            try:
                image_stream = io.BytesIO(shape.image.blob)
                slide_image = Image.open(image_stream)
                break 
            except:
                pass

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
    
    response = generate_with_retry(model, inputs, index, status_callback)
    txt = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(txt)
