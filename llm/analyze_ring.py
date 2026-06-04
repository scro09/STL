import ollama
import json

def analyze_ring(image_path):

    prompt = """
You are an objective and precise jewelry vision system.
Analyze the ring in the image. 
Return ONLY valid JSON. DO NOT output any other text or markdown.

CRITICAL INSTRUCTION:
Look very carefully. Is there a gemstone attached to the ring? 
If it is just a plain metal band with no stone, you MUST set "has_stone" to false and "stone_size_mm" to 0.0.

JSON Schema to follow:
{
  "has_stone": boolean (true if stone exists, false if plain band),
  "stone_type": string ("round", "oval", "square", or "none"),
  "setting_style": string ("prongs", "bezel", or "none"),
  "stone_size_mm": float (estimate in mm, use 0.0 if no stone),
  "band_profile": string ("flat", "d-shape", or "round"),
  "band_width_class": string ("very_narrow", "narrow", "medium", "wide", or "very_wide"),
  "thickness_class": string ("thin", "medium", or "thick")
}
"""

    response = ollama.chat(
        model="llava",
        messages=[{
            "role": "user",
            "content": prompt,
            "images": [image_path]
        }]
    )

    text = response["message"]["content"]

    start = text.find("{")
    end = text.rfind("}") + 1

    return json.loads(text[start:end])