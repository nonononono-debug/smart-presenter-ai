import google.generativeai as genai
import time
import json
import io
from PIL import Image

# --- 1. 获取模型列表 ---
def configure_genai(api_key):
    try:
        genai.configure(api_key=api_key)
        # 问 Google：我现在能用啥模型？
        all_models = genai.list_models()
        valid_models = []
        for m in all_models:
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
        
        if valid_models:
            return True, valid_models
        else:
            return True, ["models/gemini-1.5-flash"]
    except Exception as e:
        return False, str(e)

# --- 2. 带重试的生成函数 ---
def generate_with_retry(model, inputs, slide_index, status_callback=None):
    max_retries = 3
    time.sleep(2) # 基础冷却

    for attempt in range(max_retries):
        try:
            response = model.generate_content(inputs)
            return response
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                wait_time = 5 * (attempt + 1)
                if status_callback:
                    status_callback(slide_index, wait_time, attempt + 1, max_retries)
                time.sleep(wait_time)
            else:
                raise e
    raise Exception("API 限流，请稍后再试")

# --- 3. 分析单页 ---
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
# ... (保留上面的 import 和之前的函数，不要删)

# --- 4. 新增：全局逻辑复盘 ---
def analyze_presentation_logic(model, all_slides_data):
    """
    将所有页面的分析结果汇总，让 AI 进行全篇逻辑诊断。
    """
    # 1. 把分散的页面信息拼接成一个长文本
    context_text = "Presentation Structure:\n"
    for slide in all_slides_data:
        context_text += f"- Slide {slide['index']}: {slide['visual_summary']}\n"
        context_text += f"  Key Point: {slide['knowledge_extension']['entity']}\n"
    
    # 2. 构造“总架构师” Prompt
    prompt = """
    You are a Senior Presentation Consultant. 
    Review the structure of this presentation based on the summaries of each slide below.
    
    Output valid JSON only:
    {
        "executive_summary": "A powerful 2-sentence summary of the entire deck",
        "logic_diagnosis": "Analyze the narrative flow. Is it coherent? Any gaps?",
        "strengths": "What is done well?",
        "weaknesses": "What needs improvement?",
        "closing_remark": "A strong closing sentence for the speaker to end the presentation"
    }
    """
    
    # 3. 调用 AI (复用重试机制)
    # 这里的 slide_index 传 0 或 -1 表示这是全局任务
    response = generate_with_retry(model, [prompt, context_text], slide_index=0)
    
    txt = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(txt)
