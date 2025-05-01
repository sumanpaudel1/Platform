import os
import cv2
import torch
import shutil
import numpy as np
from PIL import Image
from flask import Flask, request, render_template, send_file
from rembg import remove
import subprocess

app = Flask(__name__)

# Configuration
BASE_DIR = "/content/drive/MyDrive/VITON_App"
os.makedirs(f"{BASE_DIR}/static/inputs", exist_ok=True)
os.makedirs(f"{BASE_DIR}/static/outputs", exist_ok=True)

# --------------------------
# Preprocessing Functions
# --------------------------

def generate_cloth_mask(cloth_path, output_path):
    """Convert cloth image to transparent background mask"""
    with open(cloth_path, "rb") as f_in:
        with open(output_path, "wb") as f_out:
            f_out.write(remove(f_in.read()))
    print(f"Generated cloth mask: {output_path}")

def run_human_parsing(person_path, output_path):
    """Generate human segmentation map using SCHP"""
    !python /content/Self-Correction-Human-Parsing/simple_extractor.py \
        --dataset "lip" \
        --model-restore "/content/Self-Correction-Human-Parsing/checkpoints/final.pth" \
        --input-dir {os.path.dirname(person_path)} \
        --output-dir {os.path.dirname(output_path)}
    print(f"Generated parsing map: {output_path}")

def run_openpose(person_path, json_output_dir, img_output_dir):
    """Generate pose keypoints and visualization"""
    !cd /content/openpose && \
    ./build/examples/openpose/openpose.bin \
        --image_dir {os.path.dirname(person_path)} \
        --write_json {json_output_dir} \
        --write_images {img_output_dir} \
        --display 0 \
        --render_pose 1
    print(f"Generated OpenPose data in {json_output_dir}")

def create_pairs_txt(image_name, cloth_name):
    """Create test_pairs.txt for VITON-HD"""
    with open(f"{BASE_DIR}/datasets/test_pairs.txt", "w") as f:
        f.write(f"{image_name} {cloth_name}\n")

# --------------------------
# Flask Routes
# --------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Clear previous files
        shutil.rmtree(f"{BASE_DIR}/static/inputs")
        os.makedirs(f"{BASE_DIR}/static/inputs")
        
        # Save uploaded files
        person_img = request.files["person"]
        cloth_img = request.files["cloth"]
        
        person_path = f"{BASE_DIR}/static/inputs/person.jpg"
        cloth_path = f"{BASE_DIR}/static/inputs/cloth.jpg"
        
        person_img.save(person_path)
        cloth_img.save(cloth_path)
        
        # Start preprocessing pipeline
        process_images(person_path, cloth_path)
        
        return render_template("result.html")
    
    return render_template("index.html")

def process_images(person_path, cloth_path):
    """Full preprocessing pipeline"""
    # 1. Prepare dataset structure
    os.makedirs(f"{BASE_DIR}/datasets/image", exist_ok=True)
    os.makedirs(f"{BASE_DIR}/datasets/cloth", exist_ok=True)
    
    # 2. Resize images (1024x768 for VITON-HD)
    img = Image.open(person_path).resize((768, 1024))
    img.save(f"{BASE_DIR}/datasets/image/person_01.jpg")
    
    cloth = Image.open(cloth_path).resize((768, 1024))
    cloth.save(f"{BASE_DIR}/datasets/cloth/cloth_01.jpg")
    
    # 3. Generate cloth mask
    generate_cloth_mask(
        f"{BASE_DIR}/datasets/cloth/cloth_01.jpg",
        f"{BASE_DIR}/datasets/cloth_mask/cloth_01.png"
    )
    
    # 4. Human parsing
    run_human_parsing(
        f"{BASE_DIR}/datasets/image/person_01.jpg",
        f"{BASE_DIR}/datasets/image-parse/person_01.png"
    )
    
    # 5. OpenPose estimation
    run_openpose(
        f"{BASE_DIR}/datasets/image/person_01.jpg",
        f"{BASE_DIR}/datasets/openpose_json",
        f"{BASE_DIR}/datasets/openpose_img"
    )
    
    # 6. Create pairs.txt
    create_pairs_txt("person_01.jpg", "cloth_01.jpg")
    
    # 7. Run VITON-HD
    !cd /content/drive/MyDrive/VITON_App && \
    python test.py \
        --name output \
        --dataset_dir ./datasets \
        --checkpoint_dir ./checkpoints \
        --save_dir ./static/outputs

@app.route("/result")
def get_result():
    return send_file(f"{BASE_DIR}/static/outputs/output/person_01_cloth_01.jpg")

# --------------------------
# Setup & Run
# --------------------------

def setup_environment():
    """Install all dependencies"""
    !pip install -q flask rembg opencv-python torch torchvision
    !git clone https://github.com/CMU-Perceptual-Computing-Lab/openpose
    !git clone https://github.com/PeikeLi/Self-Correction-Human-Parsing
    
    # Build OpenPose
    %cd /content/openpose
    !bash scripts/ubuntu/install_deps.sh
    !mkdir build
    %cd build
    !cmake ..
    !make -j`nproc`
    
    # Download SCHP weights
    %cd /content/Self-Correction-Human-Parsing
    !gdown https://drive.google.com/uc?id=1kUxGSvF8Wr7zvDV7VU0HEtBEUQ_0BZvP
    !unzip checkpoint.zip

if __name__ == "__main__":
    setup_environment()
    app.run(host="0.0.0.0", port=5000)