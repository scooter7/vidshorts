import streamlit as st
from openai import OpenAI
from elevenlabs import ElevenLabs
from moviepy.editor import concatenate_videoclips, ImageClip, AudioFileClip, CompositeVideoClip
import requests
import os
import captacity

# Set up OpenAI client with API key
client = OpenAI(api_key=st.secrets["openai_api_key"])

# Set ElevenLabs API key from Streamlit secrets
elevenlabs_client = ElevenLabs(api_key=st.secrets["elevenlabs_api_key"])

# App title and description
st.title("Storytelling Video Creator")
st.write("Generate videos with images, narration, and captions from your topic.")

# Initialize session state for the script
if "script" not in st.session_state:
    st.session_state.script = ""

# Input: Topic
topic = st.text_input("Enter the topic for your video:")
if topic and st.button("Generate Script"):
    st.write("Generating story script...")
    prompt = f"Write a short story about the topic: {topic}. Make it engaging, concise, and suitable for a video."

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

        # Step 1: Split script into sentences
        sentences = story_script.split(". ")
        video_clips = []
        os.makedirs("images", exist_ok=True)
        os.makedirs("audio", exist_ok=True)

        @st.cache
        def generate_image_cached(prompt):
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="512x512",  # Reduced size to lower final video resolution
                quality="standard",
                n=1
            )
            return response.data[0].url

        for idx, sentence in enumerate(sentences):
            # Generate image using DALL-E 3
            st.write(f"Generating image for sentence {idx + 1}...")
            image_prompt = f"A visually engaging representation of: {sentence}"

            try:
                image_url = generate_image_cached(image_prompt)
                
                # Download the image from the URL
                image_filename = f"images/image_{idx}.jpg"
                image_data = requests.get(image_url).content
                with open(image_filename, "wb") as f:
                    f.write(image_data)

            except Exception as e:
                st.warning(f"Image generation failed for sentence {idx + 1}. Error: {e}")
                image_filename = "placeholder.jpg"  # Path to a local placeholder image

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

        # Step 2: Combine video clips
        if video_clips:
            st.write("Combining all video clips...")
            try:
                final_video = concatenate_videoclips(video_clips, method="compose")

                # Split video into chunks if size exceeds limits
                chunk_duration = 120  # Split into 2-minute chunks
                video_chunks = [
                    final_video.subclip(i, min(i + chunk_duration, final_video.duration))
                    for i in range(0, int(final_video.duration), chunk_duration)
                ]

                for idx, chunk in enumerate(video_chunks):
                    chunk_path = f"chunk_{idx}.mp4"
                    chunk.write_videofile(
                        chunk_path, 
                        codec="libx264", 
                        audio_codec="aac", 
                        fps=24,  # Lower fps to reduce file size
                        bitrate="500k"  # Adjust bitrate for compression
                    )

                    # Step 3: Add captions with Captacity
                    st.write(f"Adding captions to chunk {idx + 1}...")
                    captioned_chunk_path = f"output_with_captions_chunk_{idx}.mp4"
                    captacity.add_captions(
                        video_file=chunk_path,
                        output_file=captioned_chunk_path,
                    )

                    # Step 4: Download the video chunk with captions
                    with open(captioned_chunk_path, "rb") as video_file:
                        video_bytes = video_file.read()
                        st.download_button(
                            f"Download Chunk {idx + 1}", 
                            video_bytes, 
                            file_name=f"video_chunk_{idx + 1}.mp4", 
                            mime="video/mp4"
                        )

            except Exception as e:
                st.error(f"Failed to create the final video: {e}")
        else:
            st.error("No video clips were created. Check for errors in the input or generation process.")
