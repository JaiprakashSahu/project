"""
NVIDIA OCR Module (FIXED)
Uses NVIDIA Vision-Llama to extract text from images/PDFs.
"""

import os
import base64
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import PyPDF2

load_dotenv()

# --------------------------------------------------
# ✅ NVIDIA CONFIG (NO FUNCTION ID! NO OLD ENDPOINT!)
# --------------------------------------------------
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
BASE_URL = "https://integrate.api.nvidia.com/v1"
VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"

# --------------------------------------------------
# OCR Extraction Instruction (SHORTENED to prevent cutoff)
# --------------------------------------------------
OCR_PROMPT = """Extract receipt data as JSON: {"vendor":"name", "date":"YYYY-MM-DD", "items":[{"name":"item", "price":0}], "subtotal":0, "tax":0, "total":0, "category":"groceries/dining/other", "payment_method":"cash/card", "confidence_score":85}"""


def get_client():
    """Initialize NVIDIA Vision API client."""
    if not NVIDIA_API_KEY:
        raise ValueError("❌ NVIDIA_API_KEY not found in .env")

    return OpenAI(
        base_url=BASE_URL,
        api_key=NVIDIA_API_KEY
    )


# --------------------------------------------------
# IMAGE OCR
# --------------------------------------------------
def extract_from_image(image_path):
    """Extract text from image using NVIDIA Vision Llama."""
    try:
        print(f"🖼️ Starting image extraction for: {image_path}")
        
        if not os.path.exists(image_path):
            print(f"❌ Image file not found: {image_path}")
            return None
            
        client = get_client()

        # Read + encode
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        print(f"📏 Image size: {len(img_bytes)} bytes")

        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp"
        }.get(Path(image_path).suffix.lower(), "image/png")

        base64_img = base64.b64encode(img_bytes).decode("utf-8")
        data_url = f"data:{mime};base64,{base64_img}"

        print("🖼️ Sending image to NVIDIA Vision...")
        print(f"📝 Using prompt: {OCR_PROMPT}")

        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            max_tokens=600,  # Reduced to prevent cutoff
            temperature=0.0
        )

        text = response.choices[0].message.content.strip()
        print(f"✅ NVIDIA Vision response received: {len(text)} characters")
        print(f"📄 Response preview: {text[:100]}...")
        
        return text

    except Exception as e:
        print(f"❌ IMAGE OCR FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


# --------------------------------------------------
# PDF OCR (Extract Text → If empty → Future OCR fallback)
# --------------------------------------------------
def extract_from_pdf(pdf_path):
    try:
        text = ""

        with open(pdf_path, "rb") as f:
            pdf = PyPDF2.PdfReader(f)
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"

        if text.strip():
            print("📄 Extracted text directly from PDF")
            return text

        print("⚠️ PDF contains no readable text. Convert to image first!")
        return None

    except Exception as e:
        print("❌ PDF extraction error:", e)
        return None


# --------------------------------------------------
# TEXT FILE READER
# --------------------------------------------------
def extract_from_text(text_path):
    try:
        with open(text_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print("❌ TEXT extraction error:", e)
        return None


# --------------------------------------------------
# UPLOAD PROCESSOR
# --------------------------------------------------
def process_uploaded_file(file_path):
    """
    Process uploaded file and return extracted TEXT (not JSON).
    The text should contain JSON that can be parsed separately.
    """
    ext = Path(file_path).suffix.lower()

    print(f"\n📄 Processing file: {file_path}")
    print(f"📋 File type: {ext}")
    print(f"📏 File exists: {os.path.exists(file_path)}")

    if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]:
        result = extract_from_image(file_path)
        print(f"🖼️ Image extraction result type: {type(result)}")
        return result

    elif ext == ".pdf":
        result = extract_from_pdf(file_path)
        print(f"📄 PDF extraction result type: {type(result)}")
        return result

    elif ext == ".txt":
        result = extract_from_text(file_path)
        print(f"📝 Text extraction result type: {type(result)}")
        return result

    print("❌ Unsupported file format")
    return None


# --------------------------------------------------
# JSON CLEANUP & VALIDATION
# --------------------------------------------------
def clean_json_response(text):
    """Remove markdown code blocks and extract JSON from LLM response."""
    if not text:
        return None
    
    # Remove markdown code blocks
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # Try to find JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    
    return text.strip()


def validate_receipt_json(data):
    """Validate that JSON has required receipt fields."""
    required_fields = ['vendor', 'date', 'total']
    
    if not isinstance(data, dict):
        return False
    
    for field in required_fields:
        if field not in data:
            return False
    
    # Check if total is a number
    try:
        float(data.get('total', 0))
    except (ValueError, TypeError):
        return False
    
    return True


def parse_json_safely(text):
    """Parse JSON with fallback and validation."""
    try:
        # Clean response
        cleaned = clean_json_response(text)
        if not cleaned:
            return None
        
        # Parse JSON
        data = json.loads(cleaned)
        
        # Validate structure
        if validate_receipt_json(data):
            print("✅ Valid JSON parsed successfully")
            return data
        else:
            print("⚠️ JSON missing required fields")
            return None
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        print(f"Raw response: {text[:200]}...")
        return None


# --------------------------------------------------
# BASIC VALIDATOR
# --------------------------------------------------
def validate_text(text):
    if not text or len(text.strip()) < 20:
        return False

    keywords = ["total", "invoice", "payment", "amount", "receipt", "rs", "$"]
    tl = text.lower()
    return any(k in tl for k in keywords)


# --------------------------------------------------
# SELF TEST
# --------------------------------------------------
if __name__ == "__main__":
    print("NVIDIA OCR module loaded.")
    print("API key available:", "YES" if NVIDIA_API_KEY else "NO")
