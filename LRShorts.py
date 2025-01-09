import streamlit as st
from openai import OpenAI
from elevenlabs import ElevenLabs
from moviepy.editor import concatenate_videoclips, ImageClip, AudioFileClip
from PIL import Image, ImageDraw, ImageFont
import requests
import os
import textwrap
import PyPDF2
from docx import Document

st.markdown("""
<style>
.stAppHeader { display: none !important; }
.st-emotion-cache-12fmjuu.e10jh26i0 { display: none !important; }
</style>
""", unsafe_allow_html=True)

os.environ["OPENAI_API_KEY"] = st.secrets["openai_api_key"]
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
elevenlabs_client = ElevenLabs(api_key=st.secrets["elevenlabs_api_key"])

def compress_image(image_path, output_path, quality=50):
    with Image.open(image_path) as img:
        img.save(output_path, "JPEG", quality=quality)

def add_text_overlay(image_path, text, output_path, font_path):
    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, size=30)
    max_text_width = img.width - 40
    wrapped_text = textwrap.fill(text, width=40)
    text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    total_text_height = text_height + 20
    x_start = 20
    y_start = img.height - total_text_height - 20
    background = Image.new("RGBA", img.size, (255, 255, 255, 0))
    background_draw = ImageDraw.Draw(background)
    background_draw.rectangle(
        [(x_start - 10, y_start - 10), (x_start + text_width + 10, y_start + total_text_height + 10)],
        fill=(0, 0, 0, 128)
    )
    img = Image.alpha_composite(img, background)
    draw.text((x_start, y_start), wrapped_text, font=font, fill="white")
    img.convert("RGB").save(output_path, "JPEG")

def download_font(font_url, local_path):
    if not os.path.exists(local_path):
        response = requests.get(font_url)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)

font_url = "https://github.com/scooter7/vidshorts/blob/main/Arial.ttf"
local_font_path = "Arial.ttf"
download_font(font_url, local_font_path)

def extract_text_from_document(file):
    if file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(file)
        text = "".join(page.extract_text() for page in reader.pages)
    elif file.name.endswith(".docx"):
        doc = Document(file)
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    elif file.name.endswith(".txt"):
        text = file.read().decode("utf-8")
    else:
        st.error("Unsupported file type.")
        text = ""
    return text

st.title("Storytelling Video Creator with Document Upload")
st.write("Generate videos with captions and select your desired image style.")

uploaded_file = st.file_uploader("Upload a document (PDF, Word, or text file):", type=["pdf", "docx", "txt"])

if uploaded_file:
    full_text = extract_text_from_document(uploaded_file)
    if full_text:
        summary_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": f"Summarize the following text:\n\n{full_text[:4000]}"},
            ]
        )
        summarized_topic = summary_response.choices[0].message.content.strip()
        st.session_state.summarized_topic = summarized_topic
        st.text_area("Summarized Topic", summarized_topic, height=150)

if "summarized_topic" in st.session_state and st.session_state.summarized_topic:
    duration_choice = st.radio("Select the desired video length:", ["15 seconds", "30 seconds"])
    style_choice = st.selectbox(
        "Choose an image style for the video:",
        ["Realistic", "Oil Painting", "Watercolor", "Sketch", "Fantasy Art", "3D Render"]
    )

    if duration_choice and style_choice and st.button("Generate Script"):
        word_limit = 30 if duration_choice == "15 seconds" else 60
        prompt = (f"Write a short story about the topic '{st.session_state.summarized_topic}' in no more than {word_limit} words. "
                  f"Make it engaging, concise, and suitable for a video narration of {duration_choice}.")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        story_script = response.choices[0].message.content
        st.session_state.script = story_script

if "script" in st.session_state and st.session_state.script:
    st.text_area("Story Script", st.session_state.script, height=200, key="story_script")
