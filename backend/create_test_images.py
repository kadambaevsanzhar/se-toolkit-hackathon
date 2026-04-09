#!/usr/bin/env python3
"""Create test images with and without student names."""
from PIL import Image, ImageDraw

def make_test_image(filename, lines):
    img = Image.new("RGB", (400, 300), color="white")
    draw = ImageDraw.Draw(img)
    y = 20
    for line in lines:
        draw.text((20, y), line, fill="black")
        y += 25
    img.save(filename)
    print(f"Created {filename}")

# Test A: Name: Ivan Ivanov
make_test_image("/tmp/test_name_a.png", [
    "Name: Ivan Ivanov",
    "",
    "Problem 1. Solve the equation:",
    "2x + 5 = 17",
    "",
    "Student solution:",
    "2x = 17 - 5",
    "2x = 12",
    "x = 6"
])

# Test B: Student: Maria Petrova
make_test_image("/tmp/test_name_b.png", [
    "Student: Maria Petrova",
    "",
    "Solve:",
    "3x - 4 = 11",
    "",
    "Solution:",
    "3x = 15",
    "x = 5"
])

# Test C: No name
make_test_image("/tmp/test_name_c.png", [
    "Solve the equation:",
    "x + 3 = 7",
    "",
    "Solution:",
    "x = 4"
])
