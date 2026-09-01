import sys
sys.path.insert(0, "backend")

from dotenv import load_dotenv
load_dotenv()

from src.services.segmentation import build_segments

text = """The Lord of the Rings

Chapter 1: A Long-expected Party
When Mr. Bilbo Baggins of Bag End announced that he would shortly be celebrating his eleventy-first birthday with a party of special magnificence, there was much talk and excitement in Hobbiton.

Chapter 2: The Shadow of the Past
The talk did not die down in nine or even ninety-nine days. The second wonder of the Shire was that Bilbo wealth was mysteriously unabated, and it seemed that he was actually growing younger."""

segments = build_segments(text)
print(f"Found {len(segments)} segments:")
for s in segments:
    print(f"- {s['title']}")
