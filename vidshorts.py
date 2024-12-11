import streamlit as st
import openai
from elevenlabs import ElevenLabs
from moviepy.editor import concatenate_videoclips, ImageClip, AudioFileClip, CompositeVideoClip, vfx
import base64
import os
from captacity import add_captions  # Captacity integration

# Set API keys from Streamlit secrets
openai.api_key = st.secrets["openai_api_key"]
elevenlabs_client = ElevenLabs(api_key=st.secrets["elevenlabs_api_key"])

# App title and description
st.title("Storytelling Video Creator")
st.write("Generate videos with images, narration, and captions from your topic.")

# Input: Topic
topic = st.text_input("Enter the topic for your video:")
if topic and st.button("Generate Script"):
    st.write("Generating story script...")
    prompt = f"Write a short story about the topic: {topic}. Make it engaging, concise, and suitable for a video."

    # Correct syntax for GPT-4o
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
)

    # Correct way to access the content
    story_script = response.choices[0].message.content
    st.write("Generated Script:")
    st.text_area("Story Script", story_script, height=200)


    # Allow editing the generated script
    story_script = st.text_area("Edit the generated story script (if needed):", value=story_script, height=200)

    if st.button("Generate Video"):
        st.write("Processing...")

        # Step 1: Split script into sentences
        sentences = story_script.split(". ")
        video_clips = []
        os.makedirs("images", exist_ok=True)
        os.makedirs("audio", exist_ok=True)

        for idx, sentence in enumerate(sentences):
            # Generate image
            st.write(f"Generating image for sentence {idx + 1}...")
            context = f"A video about {topic}"
            prompt = f"Generate an image without any text that describes: {sentence}. Context: {context}"
            response = openai.Image.create(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1792",
                response_format="b64_json"
            )
            image_filename = f"images/image_{idx}.jpg"
            with open(image_filename, "wb") as f:
                f.write(base64.b64decode(response["data"][0]["b64_json"]))

            # Generate audio
            st.write(f"Generating audio for sentence {idx + 1}...")
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

            # Combine image and audio
            st.write(f"Combining image and audio for sentence {idx + 1}...")
            audio_clip = AudioFileClip(audio_filename)
            image_clip = ImageClip(image_filename, duration=audio_clip.duration).set_audio(audio_clip)
            video_clips.append(image_clip.set_fps(30))

        # Step 2: Combine video clips
        st.write("Combining all video clips...")
        final_video = concatenate_videoclips(video_clips, method="compose")

        # Step 3: Add captions with Captacity
        st.write("Adding captions...")
        captioned_video_path = "output_with_captions.mp4"
        add_captions(final_video, story_script, output_path=captioned_video_path)

        # Save final video
        output_video_path = "final_video.mp4"
        final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", fps=30)

        # Step 4: Download the video
        st.write("Video generation complete!")
        with open(output_video_path, "rb") as video_file:
            video_bytes = video_file.read()
            st.download_button("Download Video", video_bytes, file_name="final_video.mp4", mime="video/mp4")
