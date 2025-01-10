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

# Styling for Streamlit app
st.markdown("""
<style>
.stAppHeader { display: none !important; }
.st-emotion-cache-12fmjuu.e10jh26i0 { display: none !important; }
</style>
""", unsafe_allow_html=True)

# Environment variables for API keys
os.environ["OPENAI_API_KEY"] = st.secrets["openai_api_key"]
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
elevenlabs_client = ElevenLabs(api_key=st.secrets["elevenlabs_api_key"])

# Helper functions
def compress_image(image_path, output_path, quality=50):
    with Image.open(image_path) as img:
        img.save(output_path, "JPEG", quality=quality)


def add_text_overlay(image_path, text, output_path, font_path):
    """
    Add captions to an image using Pillow.
    """
    try:
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Load font
        font = ImageFont.truetype(font_path, size=30)

        # Calculate text wrapping
        max_text_width = img.width - 40  # Leave 20px padding on each side
        wrapped_text = textwrap.fill(text, width=40)

        # Measure text dimensions
        text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Calculate positions
        x_start = 20  # Padding
        y_start = img.height - text_height - 40  # Place at bottom with padding

        # Create semi-transparent rectangle for background
        background = Image.new("RGBA", img.size, (255, 255, 255, 0))
        background_draw = ImageDraw.Draw(background)
        background_draw.rectangle(
            [(x_start - 10, y_start - 10), (x_start + text_width + 20, y_start + text_height + 10)],
            fill=(0, 0, 0, 128)  # Semi-transparent black
        )

        # Combine the image and the background
        img = Image.alpha_composite(img, background)

        # Draw text on the image
        draw = ImageDraw.Draw(img)
        draw.text((x_start, y_start), wrapped_text, font=font, fill="white")

        # Save the output
        img.convert("RGB").save(output_path, "JPEG")

    except Exception as e:
        raise RuntimeError(f"Error adding text overlay: {e}")


def download_font(font_url, local_path):
    if not os.path.exists(local_path):
        response = requests.get(font_url)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)


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


# Font setup
font_url = "https://github.com/scooter7/vidshorts/blob/main/Arial.ttf"
local_font_path = "Arial.ttf"
download_font(font_url, local_font_path)  # Use local_font_path instead of local_path

# Placeholder image setup
placeholder_url = "https://raw.githubusercontent.com/scooter7/vidshorts/main/placeholder.jpg"
placeholder_path = "placeholder.jpg"
if not os.path.exists(placeholder_path):
    try:
        placeholder_image_data = requests.get(placeholder_url).content
        with open(placeholder_path, "wb") as f:
            f.write(placeholder_image_data)
    except Exception as e:
        st.error(f"Failed to download placeholder image: {e}")
        placeholder_path = None

# Streamlit app
st.title("Storytelling Video Creator with Document Upload")
st.write("Generate videos with captions and select your desired image style.")

uploaded_file = st.file_uploader("Upload a document (PDF, Word, or text file):", type=["pdf", "docx", "txt"])

if uploaded_file:
    try:
        full_text = extract_text_from_document(uploaded_file)
        if full_text:
            st.write("📖 Summarizing the document...")
            summary_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": f"Summarize the following text:\n\n{full_text[:4000]}"},
                ]
            )
            summarized_topic = summary_response.choices[0].message.content.strip()
            st.session_state.summarized_topic = summarized_topic
            st.text_area("Summarized Topic", summarized_topic, height=150)
    except Exception as e:
        st.error(f"Error processing uploaded file: {e}")

if "summarized_topic" in st.session_state and st.session_state.summarized_topic:
    duration_choice = st.slider("Select the desired video length (seconds):", 15, 300, step=15)
    style_choice = st.selectbox(
        "Choose an image style for the video:",
        ["Realistic", "Oil Painting", "Watercolor", "Sketch", "Fantasy Art", "3D Render"]
    )

    if st.button("Generate Script"):
        try:
            st.write("📝 Generating the script...")
            word_limit = duration_choice * 5  # Approx. 5 words per second
            prompt = (f"Write a short story about the topic '{st.session_state.summarized_topic}' "
                      f"in no more than {word_limit} words. "
                      f"Make it engaging, concise, and suitable for a video narration of {duration_choice} seconds, but don't be overly dramatic in your word choice.")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            story_script = response.choices[0].message.content.strip()
            st.session_state.script = story_script
            st.text_area("Story Script", story_script, height=200, key="story_script")
        except Exception as e:
            st.error(f"Failed to generate script: {e}")

if "script" in st.session_state and st.session_state.script:
    st.text_area("Generated Script", st.session_state.script, height=200)

    if st.button("Generate Video"):
        try:
            st.write("🎥 Starting video generation...")
            sentences = st.session_state.script.split(". ")
            video_clips = []
            audio_files = []
            os.makedirs("images", exist_ok=True)
            os.makedirs("audio", exist_ok=True)

            for idx, sentence in enumerate(sentences):
                st.write(f"🔄 Processing frame {idx + 1}/{len(sentences)}...")
                try:
                    # Generate image using DALL·E (latest version)
                    image_prompt = (
                        f"A visually stunning illustration of: {sentence}. "
                        f"Art style: {style_choice.lower()}. "
                        f"Add intricate details and vibrant colors for a 1024x1024 resolution."
                    )
                    response = client.images.generate(
                        prompt=image_prompt,
                        size="1024x1024",
                        quality="high",
                        n=1
                    )
                    image_url = response.data[0].url
                    image_filename = f"images/image_{idx}.jpg"
                    image_data = requests.get(image_url).content
                    with open(image_filename, "wb") as f:
                        f.write(image_data)

                    # Add text overlay
                    captioned_image_path = f"images/captioned_image_{idx}.jpg"
                    add_text_overlay(image_filename, sentence, captioned_image_path, local_font_path)

                    # Generate audio
                    audio = elevenlabs_client.text_to_speech.convert(
                        voice_id="NYy9s57OPECPcDJavL3T",
                        model_id="eleven_multilingual_v2",
                        text=sentence,
                        voice_settings={"stability": 0.2, "similarity_boost": 0.8}
                    )
                    audio_filename = f"audio/audio_{idx}.mp3"
                    with open(audio_filename, "wb") as f:
                        for chunk in audio:
                            f.write(chunk)
                    audio_clip = AudioFileClip(audio_filename)

                    # Create video clip with captioned image and audio
                    image_clip = ImageClip(captioned_image_path, duration=audio_clip.duration).set_audio(audio_clip)
                    video_clips.append(image_clip.set_fps(30))

                except Exception as e:
                    st.error(f"Failed to process frame {idx}: {e}")
                    continue

            # Combine video clips
            st.write("⏳ Combining video clips...")
            final_video = concatenate_videoclips(video_clips, method="compose")
            final_video_path = "final_video.mp4"
            final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac", fps=24)

            # Combine audio files
            st.write("🎵 Combining audio...")
            combined_audio_path = "combined_audio.mp3"
            audio_files_str = "|".join(audio_files)
            os.system(f"ffmpeg -y -i 'concat:{audio_files_str}' -acodec copy {combined_audio_path}")

            st.write("🎉 Video generation complete!")
            st.video(final_video_path)

            # Download video
            with open(final_video_path, "rb") as video_file:
                st.download_button("Download Video", video_file, file_name="final_video.mp4", mime="video/mp4")

            # Download audio
            with open(combined_audio_path, "rb") as audio_file:
                st.download_button("Download Audio", audio_file, file_name="final_audio.mp3", mime="audio/mpeg")

            # Download script
            script_path = "script.txt"
            with open(script_path, "w") as script_file:
                script_file.write(st.session_state.script)
            with open(script_path, "rb") as text_file:
                st.download_button("Download Script", text_file, file_name="script.txt", mime="text/plain")
        except Exception as e:
            st.error(f"Failed to generate the video: {e}")
