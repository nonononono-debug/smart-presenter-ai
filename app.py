import streamlit as st
import google.generativeai as genai
from pptx import Presentation
import time
# 引入我们自己写的库！
import ai_engine 

# --- 页面配置 ---
st.set_page_config(page_title="智讲 SmartPresenter Pro", layout="wide", page_icon="🧠")

# --- 侧边栏 ---
with st.sidebar:
    st.title("🧠 智讲 Pro")
    st.caption("架构师版：前后端分离架构")
    
    api_key = st.text_input("🔑 Google API Key", type="password")
    
    # 调用 AI 引擎配置
    available_models = []
    if api_key:
        success, result = ai_engine.configure_genai(api_key)
        if success:
            available_models = result
            st.success(f"✅ 引擎连接成功 ({len(available_models)} 模型)")
        else:
            st.error(f"❌ 连接失败: {result}")

    # 模型选择
    if available_models:
        default_idx = 0
        for i, n in enumerate(available_models):
            if "flash" in n and "1.5" in n:
                default_idx = i
                break
        selected_model = st.selectbox("选择模型:", available_models, index=default_idx)
    else:
        selected_model = "models/gemini-1.5-flash"

    st.info("🛡️ 已加载 ai_engine.py 核心库，启用死磕重试机制。")

# --- 回调函数：让 AI 引擎能通知 UI ---
def update_status_ui(slide_index, wait_seconds, attempt, max_retries):
    """这个函数会被传给 ai_engine，当限流发生时，ai_engine 会调用它"""
    with st.empty():
        for t in range(wait_seconds, 0, -1):
            st.warning(
                f"🛑 第 {slide_index} 页触发限流 (429)。\n"
                f"⚡ 引擎正在冷却: {t} 秒后进行第 {attempt}/{max_retries} 次重试..."
            )
            time.sleep(1)

# --- 主界面 ---
st.title("🎙️ 智讲 SmartPresenter")
st.markdown("### 您的 AI 演示架构师：模块化流水线")

uploaded_file = st.file_uploader("上传 PPTX", type=['pptx'])

if 'results_cache' not in st.session_state:
    st.session_state['results_cache'] = []

if uploaded_file and api_key and available_models:
    if st.button("🚀 启动分析 (调用核心库)"):
        st.session_state['results_cache'] = [] 
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(selected_model)
        prs = Presentation(uploaded_file)
        
        progress_bar = st.progress(0)
        status_box = st.empty()
        result_container = st.container()
        total = len(prs.slides)
        
        for i, slide in enumerate(prs.slides):
            idx = i + 1
            status_box.info(f"🚀 正在调用 AI 引擎分析第 {idx}/{total} 页...")
            progress_bar.progress(i / total)
            
            try:
                # === 关键点：调用 ai_engine 库里的函数 ===
                # 我们把 update_status_ui 这个函数传进去，这样后端就能控制前端的显示了
                data = ai_engine.analyze_slide_content(model, slide, idx, status_callback=update_status_ui)
                
                data['index'] = idx
                st.session_state['results_cache'].append(data)
                
                with result_container:
                    with st.expander(f"✅ 第 {idx} 页 | {data.get('visual_summary')}", expanded=True):
                        c1, c2 = st.columns([2, 1])
                        c1.info(data['scripts']['standard'])
                        c2.success(data['knowledge_extension']['trivia'])
                
                # 成功后主动避让，减少触发限流的几率
                time.sleep(2)

            except Exception as e:
                st.error(f"第 {idx} 页最终失败: {e}")
        
        status_box.success("🎉 全部分析结束！")
        progress_bar.progress(1.0)

elif st.session_state['results_cache']:
    st.divider()
    for data in st.session_state['results_cache']:
        with st.expander(f"第 {data['index']} 页 | {data.get('visual_summary')}"):
            st.write(data['scripts']['standard'])
