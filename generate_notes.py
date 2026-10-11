import os
from PIL import Image, ImageDraw

def generate_musical_notes():
    # Ensure the assets directory exists
    os.makedirs("assets", exist_ok=True)
    
    print("Generating high-resolution note assets...")

    # --- 1. Generate note_up.png ---
    # Create a massive 400x1200 transparent canvas
    img_up = Image.new("RGBA", (400, 1200), (255, 255, 255, 0))
    draw_up = ImageDraw.Draw(img_up)
    
    # Draw the notehead (an oval at the bottom)
    draw_up.ellipse([50, 900, 350, 1100], fill=(0, 0, 0, 255))
    # Draw the stem (a rectangle on the right side pointing up)
    draw_up.rectangle([300, 100, 350, 1000], fill=(0, 0, 0, 255))
    
    # Supersample: mathematically shrink the image to anti-alias the edges
    img_up_smooth = img_up.resize((20, 60), Image.Resampling.LANCZOS)
    img_up_smooth.save("assets/note_up.png")
    print("Saved: assets/note_up.png")

    # --- 2. Generate note_down.png ---
    img_down = Image.new("RGBA", (400, 1200), (255, 255, 255, 0))
    draw_down = ImageDraw.Draw(img_down)
    
    # Draw the notehead (an oval at the top)
    draw_down.ellipse([50, 100, 350, 300], fill=(0, 0, 0, 255))
    # Draw the stem (a rectangle on the left side pointing down)
    draw_down.rectangle([50, 200, 100, 1100], fill=(0, 0, 0, 255))
    
    img_down_smooth = img_down.resize((20, 60), Image.Resampling.LANCZOS)
    img_down_smooth.save("assets/note_down.png")
    print("Saved: assets/note_down.png")

if __name__ == "__main__":
    generate_musical_notes()