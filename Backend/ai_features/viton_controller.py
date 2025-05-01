import os
import sys
import uuid
import shutil
import subprocess
import logging
from pathlib import Path
import base64
import cv2
import numpy as np
import hashlib
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

# Define paths for VITON-HD
BASE_DIR = Path(settings.BASE_DIR)
VITON_DIR = BASE_DIR / 'ai' / 'viton_hd'
DATASET_DIR = VITON_DIR / 'datasets' / 'test'
CLOTH_DIR = DATASET_DIR / 'cloth'
CLOTH_MASK_DIR = DATASET_DIR / 'cloth-mask'
MODEL_DIR = DATASET_DIR / 'image'
TEST_PAIRS_FILE = VITON_DIR / 'datasets' / 'test_pairs.txt'
RESULT_DIR = VITON_DIR / 'results'

# Ensure directories exist
for directory in [CLOTH_DIR, CLOTH_MASK_DIR, MODEL_DIR, RESULT_DIR]:
    os.makedirs(directory, exist_ok=True)



# Generate high-quality cloth mask using OpenCV
def generate_cloth_mask(cloth_image_path):
    """Generate high-quality mask for a clothing item"""
    try:
        logger.info(f"Generating mask for: {cloth_image_path}")
        
        # Read the cloth image
        cloth_img = cv2.imread(cloth_image_path)
        if cloth_img is None:
            logger.error(f"Could not read image at: {cloth_image_path}")
            return None
            
        # Resize for consistent processing (if needed)
        max_dimension = 1024
        height, width = cloth_img.shape[:2]
        if max(height, width) > max_dimension:
            scale = max_dimension / max(height, width)
            cloth_img = cv2.resize(cloth_img, (int(width * scale), int(height * scale)))
            logger.info(f"Resized image to {cloth_img.shape[1]}x{cloth_img.shape[0]}")
            
        # Convert to grayscale
        gray = cv2.cvtColor(cloth_img, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply adaptive thresholding for better results on various clothing
        binary = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Alternative: standard thresholding if adaptive doesn't work well
        if np.sum(binary) < 1000:  # If mask is too small, try standard thresholding
            _, binary = cv2.threshold(blur, 250, 255, cv2.THRESH_BINARY_INV)
            
        # Find contours and fill them
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Create mask
        mask = np.zeros_like(gray)
        
        # If no contours found, try different approach
        if not contours or len(contours) == 0:
            logger.warning("No contours found, trying different thresholding approach")
            _, binary = cv2.threshold(blur, 240, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
        # Draw contours on mask
        if contours and len(contours) > 0:
            # Find the largest contour (likely to be the main clothing item)
            largest_contour = max(contours, key=cv2.contourArea)
            cv2.drawContours(mask, [largest_contour], -1, 255, -1)
            
            # Add any other significant contours
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 1000 and contour is not largest_contour:  # Adjust threshold as needed
                    cv2.drawContours(mask, [contour], -1, 255, -1)
        else:
            logger.error("Still no contours found after multiple attempts")
            return None
        
        # Clean up mask with morphological operations
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Additional clean up for smoother edges
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        _, mask = cv2.threshold(mask, 128, 255, cv2.THRESH_BINARY)
        
        # Create output path (use same filename but with jpg extension)
        mask_filename = os.path.splitext(os.path.basename(cloth_image_path))[0] + '.jpg'
        mask_path = os.path.join(CLOTH_MASK_DIR, mask_filename)
        
        # Save mask
        cv2.imwrite(mask_path, mask)
        logger.info(f"Saved mask to: {mask_path}")
        
        # Verify mask was created and has content
        if not os.path.exists(mask_path):
            logger.error(f"Mask file was not created at {mask_path}")
            return None
            
        mask_check = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask_check is None or np.sum(mask_check) < 1000:
            logger.error(f"Generated mask is empty or too small")
            return None
            
        return mask_path
    except Exception as e:
        logger.error(f"Error generating cloth mask: {str(e)}")
        return None

# Main try-on view
# @csrf_exempt
# @require_http_methods(["POST"])
# def try_on_direct(request):
#     """Handle initial try-on request"""
#     try:
#         # Get product image from POST data
#         product_image_data = request.POST.get('product_image')
#         product_name = request.POST.get('product_name', 'Unknown Product')
        
#         if not product_image_data:
#             return JsonResponse({"status": "error", "message": "No product image provided"})
        
#         # Convert base64 to image
#         if product_image_data.startswith('data:image'):
#             header, encoded = product_image_data.split(",", 1)
#             image_data = base64.b64decode(encoded)
#         else:
#             image_data = base64.b64decode(product_image_data)
        
#         # Save product image
#         os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
#         product_image_path = os.path.join(settings.MEDIA_ROOT, f"temp_product_{uuid.uuid4()}.jpg")
#         with open(product_image_path, "wb") as f:
#             f.write(image_data)
        
#         # Get available model images
#         models = []
#         if os.path.exists(MODEL_DIR):
#             for filename in os.listdir(MODEL_DIR):
#                 if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
#                     models.append({
#                         "id": filename,
#                         "path": f"/media/viton/models/{filename}"
#                     })
        
#         # Render the try-on page
#         return render(request, 'products/try_on.html', {
#             'product_image': product_image_path,
#             'product_name': product_name,
#             'models': models
#         })
        
#     except Exception as e:
#         logger.error(f"Try-on error: {str(e)}")
#         return JsonResponse({"status": "error", "message": str(e)})

# Process try-on request
import torch

@csrf_exempt
@require_http_methods(["POST"])
def process_try_on(request):
    """Process try-on request with correct path handling and CPU-only mode"""
    try:
        # Get form data
        product_image_path = request.POST.get('product_image_path')
        model_id = request.POST.get('model_id')
        force_new_cloth = request.POST.get('force_new_cloth') == 'true'
        
        if not product_image_path or not model_id:
            return JsonResponse({"status": "error", "message": "Missing required parameters"})
        
        # Log the inputs for debugging
        logger.info(f"Processing try-on with product_image_path: {product_image_path}, model_id: {model_id}")
        
        # Verify the product image exists at the specified path
        if not os.path.exists(product_image_path):
            logger.error(f"Product image not found at: {product_image_path}")
            return JsonResponse({"status": "error", "message": f"Product image not found at {product_image_path}"})
        
        # Convert URL to path if needed
        if product_image_path.startswith(settings.MEDIA_URL):
            product_image_path = os.path.join(settings.MEDIA_ROOT, product_image_path[len(settings.MEDIA_URL):])
        
        # Prepare input files
        if not os.path.exists(product_image_path):
            return JsonResponse({"status": "error", "message": f"Product image not found at {product_image_path}"})
            
        model_image_path = os.path.join(MODEL_DIR, model_id)
        if not os.path.exists(model_image_path):
            return JsonResponse({"status": "error", "message": f"Model image not found: {model_id}"})
        
        # Check if the cloth already exists in the cloth directory
        existing_cloth = find_existing_cloth(product_image_path, force_new=force_new_cloth)
        
        if existing_cloth:
            logger.info(f"Found existing cloth: {existing_cloth}")
            cloth_basename = os.path.splitext(existing_cloth)[0]
            cloth_path = os.path.join(CLOTH_DIR, existing_cloth)
        else:
            # Create new cloth files with appropriate extension
            run_id = str(uuid.uuid4())[:8]
            
            # Preserve original extension or default to jpg
            ext = os.path.splitext(product_image_path)[1].lower()
            if not ext or ext not in ['.jpg', '.jpeg', '.png']:
                ext = '.jpg'
                
            cloth_filename = f"cloth_{run_id}{ext}"
            cloth_path = os.path.join(CLOTH_DIR, cloth_filename)
            
            # Copy product image to cloth directory
            shutil.copy(product_image_path, cloth_path)
            logger.info(f"Copied product image to cloth directory: {cloth_path}")
            
            # Generate cloth mask
            mask_path = generate_cloth_mask(cloth_path)
            if not mask_path:
                return JsonResponse({"status": "error", "message": "Failed to generate cloth mask"})
            
            cloth_basename = f"cloth_{run_id}"
        
        # Get model basename without extension
        model_basename = os.path.splitext(os.path.basename(model_id))[0]
        
        # Update test_pairs.txt with correct info and extensions
        update_test_pairs_file(model_basename, cloth_basename)
        
        # Run VITON-HD using the virtual environment - CPU ONLY
        result_name = 't_t'  # Using standard name for consistent results
        
        # Use correct path to Python in virtual environment
        env_python = os.path.join(
            os.environ.get('VIRTUAL_ENV', ''), 
            'Scripts', 
            'python.exe'
        ) if os.environ.get('VIRTUAL_ENV') else sys.executable
        
        # Try multiple Python paths in case the environment variable isn't set correctly
        python_paths = [
            env_python,  # First try the environment variable
            r'C:\Users\Asus\Documents\Final_Year_Project\env\Scripts\python.exe',  # Fallback to hardcoded path
            sys.executable  # Last resort: use current Python
        ]
        
        # ONLY use CPU version
        script = 'test_cpu.py'
        success = False
        
        for python_path in python_paths:
            if not os.path.exists(python_path):
                logger.warning(f"Python path does not exist: {python_path}")
                continue
                
            script_path = os.path.join(VITON_DIR, script)
            if not os.path.exists(script_path):
                logger.warning(f"Script does not exist: {script_path}")
                continue
                
            cmd = [
                python_path,
                script_path,
                '--name', result_name
            ]
            
            logger.info(f"Running VITON-HD command: {' '.join(cmd)}")
            
            try:
                # Force CPU mode by setting environment variable
                env = os.environ.copy()
                env['CUDA_VISIBLE_DEVICES'] = ''  # Disable CUDA
                
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=VITON_DIR,
                    env=env,
                    timeout=300  # 5 minute timeout
                )
                
                # Check for result
                result_path = find_result_image(model_basename, cloth_basename, result_name)
                if result_path:
                    success = True
                    break  # Found a result, exit the loop
                    
                logger.warning(f"No result found after running {script}. Stderr: {process.stderr}")
            
            except subprocess.TimeoutExpired:
                logger.error(f"Command timed out: {' '.join(cmd)}")
            except Exception as e:
                logger.error(f"Error running command: {e}")
        
        if not success:
            return JsonResponse({
                "status": "error", 
                "message": "VITON-HD processing failed after multiple attempts"
            })
        
        # Make result accessible via media URL
        media_dir = os.path.join(settings.MEDIA_ROOT, "viton_results")
        os.makedirs(media_dir, exist_ok=True)
        
        result_filename = f"result_{model_basename}_{cloth_basename}.png"
        media_path = os.path.join(media_dir, result_filename)
        shutil.copy(result_path, media_path)
        
        # Return the result URL
        result_url = f"{settings.MEDIA_URL}viton_results/{result_filename}"
        
        return JsonResponse({
            "status": "success",
            "result_url": result_url,
            "product_image": os.path.basename(product_image_path),
            "model_image": model_id,
            "cloth_image": cloth_basename + os.path.splitext(cloth_path)[1]  # Return cloth image info
        })
        
    except Exception as e:
        logger.error(f"Process try-on error: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)})
    
    
    
# Ensure the media directory is set up correctly for VITON-HD
# In viton_controller.py - try_on_direct method
from django.http import JsonResponse, HttpResponse
@csrf_exempt
@require_http_methods(["POST"])
def try_on_direct(request):
    """Handle initial try-on request with proper base64 handling"""
    try:
        # Setup media directories
        setup_viton_media()
        
        # Get basic info from request
        product_name = request.POST.get('product_name', 'Unknown Product')
        product_image_input = request.POST.get('product_image', '')
        
        # DEBUG: Log the exact value (truncated for large base64)
        if len(product_image_input) > 100:
            logger.info(f"Product image from request: '{product_image_input[:100]}...' (truncated)")
        else:
            logger.info(f"Product image from request: '{product_image_input}'")
        
        # Check if product_image is a data URI (base64 encoded)
        if product_image_input.startswith('data:image'):
            # Handle base64 data
            logger.info("Detected base64 image data")
            try:
                # Extract the base64 part after the comma
                header, encoded = product_image_input.split(",", 1)
                img_data = base64.b64decode(encoded)
                
                # Save to a temp file
                product_filename = f"temp_product_{uuid.uuid4()}.jpg"
                product_image_path = os.path.join(settings.MEDIA_ROOT, product_filename)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(product_image_path), exist_ok=True)
                
                # Write image file
                with open(product_image_path, 'wb') as f:
                    f.write(img_data)
                
                # Create URL for template
                product_image_url = f"{settings.MEDIA_URL}{product_filename}"
                
                logger.info(f"Saved base64 image to: {product_image_path}")
            except Exception as e:
                logger.error(f"Error decoding base64 data: {str(e)}")
                return JsonResponse({
                    "status": "error", 
                    "message": f"Error decoding image data: {str(e)}"
                })
        elif product_image_input.startswith('/media/'):
            # Handle media URL path
            relative_path = product_image_input.replace('/media/', '', 1)
            
            # IMPORTANT: Use the correct project-relative media path
            potential_paths = [
                os.path.join(settings.MEDIA_ROOT, relative_path),
                os.path.join(settings.BASE_DIR, 'media', relative_path)
            ]
            
            for path in potential_paths:
                if os.path.exists(path):
                    product_image_path = path
                    product_image_url = product_image_input  # Keep original URL
                    logger.info(f"Found media image at: {product_image_path}")
                    break
            else:
                logger.error(f"Media file not found: {product_image_input}")
                return JsonResponse({
                    "status": "error", 
                    "message": f"Image not found at any expected location"
                })
        else:
            # For any other case, check if it's a direct path
            if os.path.exists(product_image_input):
                product_image_path = product_image_input
                product_image_url = f"/media/{os.path.basename(product_image_input)}"
                logger.info(f"Using direct file path: {product_image_path}")
            else:
                logger.error(f"Invalid image path: {product_image_input}")
                return JsonResponse({
                    "status": "error", 
                    "message": f"Invalid or inaccessible image path"
                })
        
        # Get available model images
        models = []
        if os.path.exists(MODEL_DIR):
            for filename in os.listdir(MODEL_DIR):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    models.append({
                        "id": filename,
                        "path": f"/media/viton/models/{filename}"
                    })
        
        if not models:
            return JsonResponse({
                "status": "error", 
                "message": "No model images available"
            })
        
        # Create a URL for the product image
        product_image_url = f"{settings.MEDIA_URL}{product_filename}"
        
        # Render the HTML template
        from django.template import Template, Context
        from django.middleware.csrf import get_token
        
        # HTML template content
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Virtual Try-On</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="text-center mb-10">
            <h1 class="text-3xl font-extrabold tracking-tight text-gray-900 sm:text-4xl">
                Virtual Try-On
            </h1>
            <p class="mt-3 max-w-2xl mx-auto text-xl text-gray-500 sm:mt-4">
                Try on {{ product_name }} with our AI-powered virtual fitting room
            </p>
        </div>

        <div class="bg-white overflow-hidden shadow rounded-lg divide-y divide-gray-200">
            <div class="px-6 py-5 bg-gray-50">
                <div class="flex items-center justify-center">
                    <div class="flex items-center">
                        <div class="flex-shrink-0 h-10 w-10 flex items-center justify-center rounded-full bg-blue-600 text-white font-bold">
                            1
                        </div>
                        <div class="ml-4">
                            <p class="text-sm font-medium text-gray-900">Select Model</p>
                        </div>
                    </div>
                    <div class="w-16 h-0.5 bg-gray-200 mx-4"></div>
                    <div class="flex items-center">
                        <div class="flex-shrink-0 h-10 w-10 flex items-center justify-center rounded-full bg-gray-200 text-gray-500 font-bold">
                            2
                        </div>
                        <div class="ml-4">
                            <p class="text-sm font-medium text-gray-500">View Result</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="p-6">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div class="lg:col-span-1 space-y-4">
                        <h2 class="text-lg font-medium text-gray-900">Selected Product</h2>
                        <div class="border border-gray-200 rounded-lg overflow-hidden bg-gray-50 flex items-center justify-center p-4" style="height: 400px;">
                            <img src="{{ product_image }}" alt="{{ product_name }}" class="max-h-full max-w-full object-contain">
                        </div>
                        <div class="text-center">
                            <h3 class="text-lg font-medium text-gray-900">{{ product_name }}</h3>
                        </div>
                    </div>
                    
                    <div class="lg:col-span-2">
                        <div class="flex justify-between items-center mb-4">
                            <h2 class="text-lg font-medium text-gray-900">Choose a Model</h2>
                            <p class="text-sm text-gray-500">Select a person to try this item on</p>
                        </div>
                        
                        <form id="tryOnForm" action="/process-try-on/" method="post" class="space-y-6">
                            <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
                            <input type="hidden" name="product_image_path" value="{{ product_image_path }}">
                            <input type="hidden" name="model_id" id="selectedModel">
                            
                            <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
                                {% for model in models %}
                                <div class="model-option rounded-lg border-2 border-transparent hover:border-blue-500 cursor-pointer transition-all" 
                                     data-model-id="{{ model.id }}" onclick="selectModel(this)">
                                    <div class="aspect-w-2 aspect-h-3 relative overflow-hidden rounded-t-lg">
                                        <img src="{{ model.path }}" alt="Model" class="object-cover w-full h-full">
                                        <div class="selected-indicator opacity-0 absolute inset-0 bg-blue-500 bg-opacity-10 flex items-center justify-center">
                                            <div class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
                                                <svg class="w-5 h-5 text-white" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                                                </svg>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="py-2 text-center">
                                        <span class="text-sm font-medium text-gray-700">{{ model.id }}</span>
                                    </div>
                                </div>
                                {% endfor %}
                            </div>
                            
                            <div class="flex justify-center">
                                <button type="submit" id="submitBtn" class="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed" disabled>
                                    <svg class="w-5 h-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                    Generate Try-On Result
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <!-- Results Section (initially hidden) -->
            <div id="resultsSection" class="p-6 hidden">
                <div class="text-center">
                    <!-- Loading Spinner -->
                    <div id="loadingSpinner" class="py-12">
                        <div class="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-500 mx-auto"></div>
                        <p class="mt-4 text-gray-600">Processing your virtual try-on request...</p>
                        <p class="mt-2 text-sm text-gray-500">This may take a moment as we generate your personalized result</p>
                    </div>

                    <!-- Results Container -->
                    <div id="resultContainer" class="hidden">
                        <h2 class="text-xl font-bold text-gray-900 mb-6">Your Try-On Result</h2>

                        <div class="grid grid-cols-1 md:grid-cols-4 gap-8">
                            <div class="md:col-span-1">
                                <div class="border border-gray-200 rounded-lg p-4 bg-gray-50">
                                    <h3 class="text-sm font-medium text-gray-500 mb-2">Original Product</h3>
                                    <img id="originalProductImg" src="{{ product_image }}" alt="Original Product" class="max-w-full mx-auto">
                                </div>
                            </div>
                            <div class="md:col-span-1">
                                <div class="border border-gray-200 rounded-lg p-4 bg-gray-50">
                                    <h3 class="text-sm font-medium text-gray-500 mb-2">Processed Cloth</h3>
                                    <img id="processedClothImg" src="" alt="Processed Cloth" class="max-w-full mx-auto">
                                </div>
                            </div>
                            <div class="md:col-span-1">
                                <div class="border border-gray-200 rounded-lg p-4 bg-gray-50">
                                    <h3 class="text-sm font-medium text-gray-500 mb-2">Selected Model</h3>
                                    <img id="selectedModelImg" src="" alt="Selected Model" class="max-w-full mx-auto">
                                </div>
                            </div>
                            <div class="md:col-span-1">
                                <div class="border border-gray-200 rounded-lg p-4 bg-gray-50">
                                    <h3 class="text-sm font-medium text-gray-500 mb-2">Try-On Result</h3>
                                    <img id="resultImg" src="" alt="Try-On Result" class="max-w-full mx-auto">
                                </div>
                            </div>
                        </div>
                        <div class="mt-8 flex justify-center space-x-4">
                            <a id="downloadBtn" href="#" download class="inline-flex items-center px-4 py-2 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700">
                                <svg class="w-5 h-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                Download Result
                            </a>
                            <button id="tryAnotherBtn" class="inline-flex items-center px-4 py-2 border border-gray-300 text-base font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50">
                                <svg class="w-5 h-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                </svg>
                                Try Another Model
                            </button>
                        </div>
                    </div>

                    <!-- Error Container -->
                    <div id="errorContainer" class="hidden py-8">
                        <div class="mx-auto max-w-md bg-red-50 border border-red-200 rounded-md p-4">
                            <div class="flex">
                                <div class="flex-shrink-0">
                                    <svg class="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                                    </svg>
                                </div>
                                <div class="ml-3">
                                    <h3 class="text-sm font-medium text-red-800">Error Processing Try-On</h3>
                                    <p id="errorMessage" class="mt-2 text-sm text-red-700"></p>
                                </div>
                            </div>
                        </div>
                        <div class="mt-6">
                            <button id="tryAgainBtn" class="inline-flex items-center px-4 py-2 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700">
                                Try Again
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Model selection
        function selectModel(element) {
            // Get model ID
            const modelId = element.dataset.modelId;
            document.getElementById('selectedModel').value = modelId;
            
            // Update visual selection
            document.querySelectorAll('.model-option').forEach(option => {
                option.classList.remove('border-blue-500', 'bg-blue-50');
                option.querySelector('.selected-indicator').classList.add('opacity-0');
            });
            
            element.classList.add('border-blue-500', 'bg-blue-50');
            element.querySelector('.selected-indicator').classList.remove('opacity-0');
            
            // Enable submit button
            document.getElementById('submitBtn').disabled = false;
        }

        // Form submission
        document.getElementById('tryOnForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Show results section with loading spinner
            document.getElementById('resultsSection').classList.remove('hidden');
            document.getElementById('loadingSpinner').classList.remove('hidden');
            document.getElementById('resultContainer').classList.add('hidden');
            document.getElementById('errorContainer').classList.add('hidden');
            
            // Disable button
            const submitBtn = document.getElementById('submitBtn');
            const originalText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = `
                <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing...
            `;
            
            // Scroll to results section
            document.getElementById('resultsSection').scrollIntoView({
                behavior: 'smooth'
            });
            
            // Submit the form via AJAX
            const formData = new FormData(this);
            
            fetch(this.action, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // Hide loading spinner
                document.getElementById('loadingSpinner').classList.add('hidden');
                
                if (data.status === 'success') {
                    // Show result
                    document.getElementById('resultImg').src = data.result_url;
                    document.getElementById('downloadBtn').href = data.result_url;
                    document.getElementById('selectedModelImg').src = "/media/viton/models/" + data.model_image;
                    
                    // Set the processed cloth image if available
                    if (data.cloth_image) {
                        document.getElementById('processedClothImg').src = "/media/viton/datasets/test/cloth/" + data.cloth_image;
                    } else {
                        document.getElementById('processedClothImg').src = data.product_image;
                    }
                    
                    document.getElementById('resultContainer').classList.remove('hidden');
                } else {
                    // Show error
                    document.getElementById('errorMessage').textContent = data.message || 'An unknown error occurred';
                    document.getElementById('errorContainer').classList.remove('hidden');
                }
                
                // Reset button
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            })
            .catch(error => {
                // Hide loading spinner
                document.getElementById('loadingSpinner').classList.add('hidden');
                
                // Show error
                document.getElementById('errorMessage').textContent = 'Network error: ' + error.message;
                document.getElementById('errorContainer').classList.remove('hidden');
                
                // Reset button
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            });
        });
        
        // Try another button
        document.getElementById('tryAnotherBtn').addEventListener('click', function() {
            document.getElementById('resultsSection').classList.add('hidden');
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
        
        // Try again button
        document.getElementById('tryAgainBtn').addEventListener('click', function() {
            document.getElementById('errorContainer').classList.add('hidden');
            document.getElementById('resultsSection').classList.add('hidden');
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
        
        // Add debug info for image loading
        document.addEventListener('DOMContentLoaded', function() {
            console.log('Page loaded, product image:', '{{ product_image }}');
            
            // Debug image loading errors
            document.querySelectorAll('img').forEach(img => {
                img.onerror = function() {
                    console.error('Failed to load image:', this.src);
                    this.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20width%3D%22300%22%20height%3D%22300%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Crect%20width%3D%22300%22%20height%3D%22300%22%20fill%3D%22%23f3f4f6%22%2F%3E%3Ctext%20x%3D%2250%25%22%20y%3D%2250%25%22%20font-size%3D%2220%22%20text-anchor%3D%22middle%22%20alignment-baseline%3D%22middle%22%20font-family%3D%22system-ui%2C%20sans-serif%22%20fill%3D%22%236b7280%22%3EImage%20Not%20Found%3C%2Ftext%3E%3C%2Fsvg%3E';
                }
            });
        });
    </script>
</body>
</html>"""
        
        # Render template with context
        template = Template(html_content)
        context = {
            'product_name': product_name,
            'product_image': product_image_url,  # URL for displaying
            'product_image_path': product_image_path,  # Path for processing
            'models': models,
            'csrf_token': get_token(request)
        }
        rendered_html = template.render(Context(context))
        
        # Return the rendered HTML directly
        return HttpResponse(rendered_html)
        
    except Exception as e:
        logger.error(f"Try-on error: {str(e)}", exc_info=True)
        return JsonResponse({
            "status": "error", 
            "message": str(e)
        })
    

from django.http import JsonResponse, HttpResponse
from django.template import Template, Context




def clear_gpu_memory():
    """Clear CUDA cache to free up GPU memory"""
    try:
        import torch
        if torch.cuda.is_available():
            # Print initial GPU memory usage
            logger.info(f"Initial GPU memory: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB allocated, "
                        f"{torch.cuda.memory_reserved(0) / 1024**2:.2f} MB reserved")
            
            # Empty cache
            torch.cuda.empty_cache()
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Print GPU memory after clearing
            logger.info(f"After clearing: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB allocated, "
                        f"{torch.cuda.memory_reserved(0) / 1024**2:.2f} MB reserved")
            
            return True
        else:
            logger.info("CUDA not available, no need to clear GPU memory")
            return False
    except Exception as e:
        logger.error(f"Error clearing GPU memory: {str(e)}")
        return False

def set_gpu_optimizations():
    """Set PyTorch GPU optimizations"""
    try:
        import torch
        if torch.cuda.is_available():
            # Reduce memory fragmentation
            torch.backends.cudnn.benchmark = True
            
            # Set fastest algorithms for fixed input sizes
            torch.backends.cudnn.fastest = True
            
            # Disable debugging features
            torch.autograd.set_detect_anomaly(False)
            
            # Set default tensor type to save CPU-GPU transfers
            torch.set_default_tensor_type('torch.cuda.FloatTensor')
            
            logger.info("GPU optimizations applied")
            return True
        else:
            logger.info("CUDA not available, no GPU optimizations applied")
            return False
    except Exception as e:
        logger.error(f"Error setting GPU optimizations: {str(e)}")
        return False
    
    

def setup_viton_media():
    """Set up the media directory structure and copy model images"""
    try:
        # Define source and destination paths
        model_source_dir = MODEL_DIR
        media_model_dir = os.path.join(settings.MEDIA_ROOT, 'viton', 'models')
        
        # Create destination directory if it doesn't exist
        os.makedirs(media_model_dir, exist_ok=True)
        
        # Log paths for debugging
        logger.info(f"Setting up VITON media:")
        logger.info(f"  Source model directory: {model_source_dir}")
        logger.info(f"  Destination media directory: {media_model_dir}")
        
        # Check if source directory exists
        if not os.path.exists(model_source_dir):
            logger.error(f"Source model directory does not exist: {model_source_dir}")
            return False
            
        # Copy model images to media directory
        copied_count = 0
        for filename in os.listdir(model_source_dir):
            if filename.lower().endswith(('.jpg', '.png', '.jpeg')):
                source_path = os.path.join(model_source_dir, filename)
                dest_path = os.path.join(media_model_dir, filename)
                
                # Copy if destination doesn't exist or is older
                if not os.path.exists(dest_path) or os.path.getmtime(source_path) > os.path.getmtime(dest_path):
                    shutil.copy2(source_path, dest_path)
                    copied_count += 1
        
        logger.info(f"Copied {copied_count} model images to media directory")
        return True
        
    except Exception as e:
        logger.error(f"Error setting up VITON media: {str(e)}")
        return False
    


def update_test_pairs_file(model_basename, cloth_basename):
    """Update test_pairs.txt with model and cloth basenames - keeping extensions in the data"""
    try:
        # Find the actual files with their extensions
        model_files = os.listdir(MODEL_DIR)
        cloth_files = os.listdir(CLOTH_DIR)
        
        # Find the matching files by basename (without checking extensions)
        model_file = None
        for f in model_files:
            if os.path.splitext(f)[0] == model_basename:
                model_file = f
                break
                
        cloth_file = None
        for f in cloth_files:
            if os.path.splitext(f)[0] == cloth_basename:
                cloth_file = f
                break
        
        if not model_file or not cloth_file:
            logger.error(f"Could not find model or cloth files matching basenames: {model_basename}, {cloth_basename}")
            return False
            
        # Use the full filenames including extensions in test_pairs.txt
        with open(TEST_PAIRS_FILE, 'w') as f:
            f.write(f"{model_file} {cloth_file}\n")
            
        logger.info(f"Updated test_pairs.txt with: {model_file} {cloth_file}")
        return True
    
    except Exception as e:
        logger.error(f"Error updating test_pairs.txt: {str(e)}")
        return False
    

def find_result_image(model_basename, cloth_basename, result_name='test'):
    """Find the output image from any possible location"""
    possible_paths = [
        os.path.join(RESULT_DIR, f"{result_name}/try-on/{model_basename}_{cloth_basename}.png"),
        os.path.join(RESULT_DIR, f"{result_name}/try-on/results/{model_basename}_{cloth_basename}.png"),
        os.path.join(RESULT_DIR, f"test/try-on/{model_basename}_{cloth_basename}.png"),
        os.path.join(RESULT_DIR, f"test/try-on/results/{model_basename}_{cloth_basename}.png"),
        os.path.join(RESULT_DIR, f"t/try-on/{model_basename}_{cloth_basename}.png"),
        os.path.join(RESULT_DIR, f"t/try-on/results/{model_basename}_{cloth_basename}.png")
    ]
    
    # Check standard paths first
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"Found result at standard path: {path}")
            return path
    
    # If not found in standard paths, search recursively
    logger.info(f"Searching for result image: {model_basename}_{cloth_basename}.png")
    for root, dirs, files in os.walk(RESULT_DIR):
        for file in files:
            if f"{model_basename}_{cloth_basename}" in file and file.endswith('.png'):
                result_path = os.path.join(root, file)
                logger.info(f"Found result by searching: {result_path}")
                return result_path
                
    logger.error(f"Could not find result image for {model_basename}_{cloth_basename}")
    return None



@csrf_exempt
def test_image_path(request):
    """Debug function to test image path handling"""
    if request.method == "POST":
        image_path = request.POST.get('image_path', '')
        
        # Log various attempts to access the image
        results = {
            "path": image_path,
            "exists_directly": os.path.exists(image_path),
            "abs_path": os.path.abspath(image_path) if image_path else "",
            "media_paths_tested": []
        }
        
        # Test multiple possible path constructions
        if image_path and image_path.startswith('/media/'):
            relative_path = image_path.replace('/media/', '', 1)
            
            paths_to_check = [
                os.path.join(settings.MEDIA_ROOT, relative_path),
                os.path.join(settings.BASE_DIR, 'media', relative_path),
                os.path.join(settings.BASE_DIR, relative_path),
                relative_path
            ]
            
            for path in paths_to_check:
                results["media_paths_tested"].append({
                    "path": path,
                    "exists": os.path.exists(path)
                })
        
        return JsonResponse(results)
    
    # Simple HTML test form
    return HttpResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Image Path</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .form-group { margin-bottom: 15px; }
            input[type="text"] { width: 100%; padding: 5px; }
            button { padding: 8px 15px; background: #007bff; color: white; border: none; cursor: pointer; }
            #result { margin-top: 20px; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
            .path-test { margin-bottom: 10px; padding: 5px; border-bottom: 1px solid #eee; }
            .exists { color: green; }
            .not-exists { color: red; }
        </style>
    </head>
    <body>
        <h1>Test Image Path</h1>
        <div class="form-group">
            <label>Enter image path to test:</label>
            <input type="text" id="imagePath" placeholder="/media/products/shirt.jpg" value="/media/products/shirt.jpg">
        </div>
        <button id="testBtn">Test Path</button>
        
        <div id="result" style="display: none;"></div>
        
        <script>
            document.getElementById('testBtn').addEventListener('click', function() {
                const path = document.getElementById('imagePath').value;
                
                // Create form data
                const formData = new FormData();
                formData.append('image_path', path);
                
                // Add CSRF token if available
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
                if (csrfToken) {
                    formData.append('csrfmiddlewaretoken', csrfToken);
                }
                
                // Send request
                fetch(window.location.href, {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    const resultDiv = document.getElementById('result');
                    resultDiv.style.display = 'block';
                    
                    let html = `
                        <h3>Test Results</h3>
                        <div class="path-test">
                            <strong>Original Path:</strong> ${data.path}<br>
                            <strong>Absolute Path:</strong> ${data.abs_path}<br>
                            <strong>Exists Directly:</strong> <span class="${data.exists_directly ? 'exists' : 'not-exists'}">
                                ${data.exists_directly ? '✓ Yes' : '✗ No'}
                            </span>
                        </div>
                        <h4>Media Path Tests:</h4>
                    `;
                    
                    if (data.media_paths_tested && data.media_paths_tested.length > 0) {
                        data.media_paths_tested.forEach(test => {
                            html += `
                                <div class="path-test">
                                    <strong>Path:</strong> ${test.path}<br>
                                    <strong>Exists:</strong> <span class="${test.exists ? 'exists' : 'not-exists'}">
                                        ${test.exists ? '✓ Yes' : '✗ No'}
                                    </span>
                                </div>
                            `;
                        });
                    } else {
                        html += '<p>No media paths were tested.</p>';
                    }
                    
                    resultDiv.innerHTML = html;
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('result').innerHTML = `<p>Error: ${error.message}</p>`;
                    document.getElementById('result').style.display = 'block';
                });
            });
        </script>
    </body>
    </html>
    """)
    
    
    

def find_existing_cloth(product_image_path, force_new=False):
    """Find if a similar cloth already exists in the cloth directory based on image hash.
    
    Args:
        product_image_path: Path to the product image
        force_new: If True, always return None to force creation of a new cloth
        
    Returns:
        Filename of existing cloth if found, None otherwise
    """
    if force_new:
        return None
        
    try:
        # Calculate hash of input image
        img = cv2.imread(product_image_path)
        if img is None:
            logger.error(f"Cannot read image at {product_image_path}")
            return None
            
        # Generate perceptual hash of image
        resized = cv2.resize(img, (32, 32))
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        img_hash = hashlib.md5(gray.tobytes()).hexdigest()
        logger.info(f"Generated hash for {product_image_path}: {img_hash}")
        
        # Check existing cloth files
        if not os.path.exists(CLOTH_DIR):
            logger.warning(f"Cloth directory doesn't exist: {CLOTH_DIR}")
            return None
            
        for filename in os.listdir(CLOTH_DIR):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
                
            cloth_path = os.path.join(CLOTH_DIR, filename)
            cloth_img = cv2.imread(cloth_path)
            
            if cloth_img is None:
                continue
                
            # Calculate hash of existing cloth
            cloth_resized = cv2.resize(cloth_img, (32, 32))
            cloth_gray = cv2.cvtColor(cloth_resized, cv2.COLOR_BGR2GRAY)
            cloth_hash = hashlib.md5(cloth_gray.tobytes()).hexdigest()
            
            # If hashes match, this is a similar image
            if img_hash == cloth_hash:
                logger.info(f"Found matching cloth: {filename}")
                return filename
                
        # No match found
        return None
        
    except Exception as e:
        logger.error(f"Error in find_existing_cloth: {str(e)}")
        return None