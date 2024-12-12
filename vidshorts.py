import streamlit as st
from openai import OpenAI
from elevenlabs import ElevenLabs
from moviepy.editor import concatenate_videoclips, ImageClip, AudioFileClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
import requests
import os

# Set OpenAI API key and initialize the client
os.environ["OPENAI_API_KEY"] = st.secrets["openai_api_key"]
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize ElevenLabs client
elevenlabs_client = ElevenLabs(api_key=st.secrets["elevenlabs_api_key"])

# Compress images before adding to video
def compress_image(image_path, output_path, quality=50):
    with Image.open(image_path) as img:
        img.save(output_path, "JPEG", quality=quality)

# Add text overlay using Pillow
import textwrap

def add_text_overlay(image_path, text, output_path, font_path):
    """Add captions to an image using Pillow with text wrapping."""
    try:
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Load font
        font = ImageFont.truetype(font_path, size=30)

        # Calculate maximum text width (pixels) for wrapping
        max_text_width = img.width - 40  # Padding of 20px on each side
        lines = []
        line_height = 0

        # Wrap text into lines that fit within max_text_width
        for line in text.split("\n"):
            wrapped_lines = textwrap.wrap(line, width=40)  # Approx. 40 chars per line
            for wrapped_line in wrapped_lines:
                text_size = draw.textbbox((0, 0), wrapped_line, font=font)
                line_height = text_size[3] - text_size[1]
                lines.append(wrapped_line)

        # Calculate total text height
        total_text_height = len(lines) * line_height + (len(lines) - 1) * 5  # Add 5px spacing between lines

        # Starting position for text (centered vertically in bottom section)
        y_start = img.height - total_text_height - 20  # 20px padding from bottom
        x_start = 20  # 20px padding from left

        # Create semi-transparent rectangle for text background
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(
            [(x_start - 10, y_start - 10), (img.width - x_start + 10, img.height - 10)],
            fill=(0, 0, 0, 128)
        )

        # Combine overlay and image
        img = Image.alpha_composite(img, overlay)

        # Draw text line by line
        for line in lines:
            draw.text((x_start, y_start), line, font=font, fill="white")
            y_start += line_height + 5  # Move down for next line

        # Save the final image
        img.convert("RGB").save(output_path, "JPEG")
    except Exception as e:
        st.error(f"Failed to add text overlay: {e}")
        raise e

# Download font file
def download_font(font_url, local_path):
    if not os.path.exists(local_path):
        try:
            response = requests.get(font_url)
            response.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(response.content)
            st.info("Font file downloaded successfully.")
        except Exception as e:
            st.error(f"Failed to download font file: {e}")
            raise e

# Font file URL and local path
font_url = "https://github.com/scooter7/vidshorts/blob/main/Arial.ttf"
local_font_path = "Arial.ttf"
download_font(font_url, local_font_path)

# App title and description
st.title("Storytelling Video Creator with Styles")
st.write("Generate videos with captions and select your desired image style.")

# Placeholder image setup
placeholder_url = "https://raw.githubusercontent.com/scooter7/vidshorts/main/placeholder.jpg"
placeholder_path = "placeholder.jpg"
if not os.path.exists(placeholder_path):
    try:
        placeholder_image_data = requests.get(placeholder_url).content
        with open(placeholder_path, "wb") as f:
            f.write(placeholder_image_data)
        st.info("Downloaded placeholder image successfully.")
    except Exception as e:
        st.error(f"Failed to download placeholder image: {e}")
        placeholder_path = None

# Step 1: User Input - Topic, Duration, and Style
topic = st.text_input("Enter the topic for your video:")
duration_choice = st.radio("Select the desired video length:", ["15 seconds", "30 seconds"])
style_choice = st.selectbox(
    "Choose an image style for the video:",
    ["Realistic", "Oil Painting", "Watercolor", "Sketch", "Fantasy Art", "3D Render"]
)

if topic and duration_choice and style_choice and st.button("Generate Script"):
    st.write("Generating story script...")

    word_limit = 30 if duration_choice == "15 seconds" else 60
    prompt = (f"Write a short story about the topic '{topic}' in no more than {word_limit} words. "
              f"Make it engaging, concise, and suitable for a video narration of {duration_choice}.")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        story_script = response.choices[0].message.content
        st.session_state.script = story_script
    except Exception as e:
        st.error(f"Failed to generate script: {e}")

if "script" in st.session_state and st.session_state.script:
    st.write("Generated Script:")
    story_script = st.text_area("Story Script", st.session_state.script, height=200, key="story_script")

    if st.button("Generate Video"):
        st.write("Processing...")

        sentences = story_script.split(". ")
        video_clips = []
        os.makedirs("images", exist_ok=True)
        os.makedirs("audio", exist_ok=True)

        for idx, sentence in enumerate(sentences):
            st.write(f"Generating image for sentence {idx + 1}...")
            image_prompt = f"{sentence} in {style_choice.lower()} style"

            try:
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=image_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1
                )
                image_url = response.data[0].url
                image_filename = f"images/image_{idx}.jpg"
                image_data = requests.get(image_url).content
                with open(image_filename, "wb") as f:
                    f.write(image_data)
                compress_image(image_filename, image_filename, quality=50)
                captioned_image_path = f"images/captioned_image_{idx}.jpg"
                add_text_overlay(image_filename, sentence, captioned_image_path, local_font_path)
            except Exception as e:
                st.warning(f"Image generation failed for sentence {idx + 1}. Error: {e}")
                if placeholder_path:
                    captioned_image_path = placeholder_path
                else:
                    st.error("No placeholder available. Skipping this frame.")
                    continue

            st.write(f"Generating audio for sentence {idx + 1}...")
            try:
                audio = elevenlabs_client.text_to_speech.convert(
                    voice_id="pqHfZKP75CvOlQylNhV4",
                    model_id="eleven_multilingual_v2",
                    text=sentence,
                    voice_settings={"stability": 0.2, "similarity_boost": 0.8}
                )
                audio_filename = f"audio/audio_{idx}.mp3"
                with open(audio_filename, "wb") as f:
                    for chunk in audio:
                        f.write(chunk)
            except Exception as e:
                st.error(f"Audio generation failed for sentence {idx + 1}. Error: {e}")
                continue

            st.write(f"Combining image and audio for sentence {idx + 1}...")
            try:
                audio_clip = AudioFileClip(audio_filename)
                image_clip = ImageClip(captioned_image_path, duration=audio_clip.duration).set_audio(audio_clip)
                video_clips.append(image_clip.set_fps(30))
            except Exception as e:
                st.error(f"Failed to combine image and audio: {e}")
                continue

        if video_clips:
            st.write("Combining all video clips...")
            try:
                final_video = concatenate_videoclips(video_clips, method="compose")
                final_video_path = "final_video.mp4"
                final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac", fps=24)
                st.write("Video generation complete!")
                with open(final_video_path, "rb") as video_file:
                    video_bytes = video_file.read()
                    st.download_button("Download Video", video_bytes, file_name="final_video.mp4", mime="video/mp4")
            except Exception as e:
                st.error(f"Failed to create the final video: {e}")
        else:
            st.error("No video clips were created. Check for errors in the input or generation process.")
