import streamlit as st
from openai import OpenAI
from elevenlabs import ElevenLabs
from moviepy.editor import concatenate_videoclips, ImageClip, AudioFileClip, CompositeVideoClip
from PIL import Image
import requests
import os
import captacity

# Initialize OpenAI client explicitly with the API key from Streamlit secrets
client = OpenAI(api_key=st.secrets["openai_api_key"])

# Set ElevenLabs API key from Streamlit secrets
elevenlabs_client = ElevenLabs(api_key=st.secrets["elevenlabs_api_key"])

# Compress images before adding to video
def compress_image(image_path, output_path, quality=50):
    with Image.open(image_path) as img:
        img.save(output_path, "JPEG", quality=quality)

# App title and description
st.title("Storytelling Video Creator")
st.write("Generate videos with a limit of 15 or 30 seconds.")

# Initialize session state for the script
if "script" not in st.session_state:
    st.session_state.script = ""

# Placeholder image setup
placeholder_url = "https://raw.githubusercontent.com/scooter7/vidshorts/main/placeholder.jpg"
placeholder_path = "placeholder.jpg"

# Ensure the placeholder image exists locally
if not os.path.exists(placeholder_path):
    try:
        placeholder_image_data = requests.get(placeholder_url).content
        with open(placeholder_path, "wb") as f:
            f.write(placeholder_image_data)
        st.info("Downloaded placeholder image successfully.")
    except Exception as e:
        st.error(f"Failed to download placeholder image: {e}")
        placeholder_path = None  # Disable fallback if download fails

# Step 1: User Input - Topic and Duration
topic = st.text_input("Enter the topic for your video:")
duration_choice = st.radio("Select the desired video length:", ["15 seconds", "30 seconds"])

if topic and duration_choice and st.button("Generate Script"):
    st.write("Generating story script...")
    
    # Set word limit based on duration choice
    if duration_choice == "15 seconds":
        word_limit = 30  # Approx. 2 words/sec * 15 seconds
    else:
        word_limit = 60  # Approx. 2 words/sec * 30 seconds

    # Modify the prompt for GPT-4
    prompt = (f"Write a short story about the topic '{topic}' in no more than {word_limit} words. "
              f"Make it engaging, concise, and suitable for a video narration of {duration_choice}.")

    # Generate story script using OpenAI GPT-4
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state.script = response.choices[0].message.content
    except Exception as e:
        st.error(f"Failed to generate script: {e}")

# Display the generated script if available
if st.session_state.script:
    st.write("Generated Script:")
    story_script = st.text_area(
        "Story Script",
        st.session_state.script,
        height=200,
        key="story_script"
    )

    # Allow editing of the generated script
    if st.button("Generate Video"):
        st.write("Processing...")

        # Step 2: Split script into sentences
        sentences = story_script.split(". ")
        video_clips = []
        os.makedirs("images", exist_ok=True)
        os.makedirs("audio", exist_ok=True)

        for idx, sentence in enumerate(sentences):
            # Generate image using DALL-E 3
            st.write(f"Generating image for sentence {idx + 1}...")
            image_prompt = f"A visually engaging representation of: {sentence}"

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

            except Exception as e:
                st.warning(f"Image generation failed for sentence {idx + 1}. Error: {e}")
                if placeholder_path:
                    image_filename = placeholder_path
                else:
                    st.error("No placeholder available. Skipping this frame.")
                    continue

            # Generate audio
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

            # Combine image and audio
            st.write(f"Combining image and audio for sentence {idx + 1}...")
            try:
                audio_clip = AudioFileClip(audio_filename)
                image_clip = ImageClip(image_filename, duration=audio_clip.duration).set_audio(audio_clip)
                video_clips.append(image_clip.set_fps(30))
            except Exception as e:
                st.error(f"Failed to combine image and audio: {e}")
                continue

        # Step 3: Combine video clips
        if video_clips:
            st.write("Combining all video clips...")
            try:
                final_video = concatenate_videoclips(video_clips, method="compose")

                # Save final video
                final_video_path = "final_video.mp4"
                final_video.write_videofile(
                    final_video_path,
                    codec="libx264",
                    audio_codec="aac",
                    fps=24,
                    bitrate="500k"  # Reduced bitrate
                )

                # Step 4: Add captions with Captacity
                st.write("Adding captions...")
                captioned_video_path = "output_with_captions.mp4"
                captacity.add_captions(
                    video_file=final_video_path,
                    output_file=captioned_video_path,
                )

                # Step 5: Download the video with captions
                st.write("Video generation complete!")
                with open(captioned_video_path, "rb") as video_file:
                    video_bytes = video_file.read()
                    st.download_button("Download Video", video_bytes, file_name="final_video_with_captions.mp4", mime="video/mp4")

            except Exception as e:
                st.error(f"Failed to create the final video: {e}")
        else:
            st.error("No video clips were created. Check for errors in the input or generation process.")
