"""
AI Dispute Analyzer — EasyOCR + OpenCV + TextBlob version.
No Tesseract. No external installs. Pure Python.
"""

import os
import re
import numpy as np
from PIL import Image

# ============================================ #
# SAFE IMPORTS                                  #
# ============================================ #
try:
    import cv2
    CV2_AVAILABLE = True
    print("✅ OpenCV loaded")
except ImportError:
    CV2_AVAILABLE = False
    print("⚠️ opencv-python missing. Run: pip install opencv-python")

try:
    from skimage.metrics import structural_similarity as ssim
    SSIM_AVAILABLE = True
    print("✅ scikit-image loaded")
except ImportError:
    SSIM_AVAILABLE = False
    print("⚠️ scikit-image missing. Run: pip install scikit-image")

try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
    print("✅ imagehash loaded")
except ImportError:
    IMAGEHASH_AVAILABLE = False
    print("⚠️ imagehash missing. Run: pip install imagehash")

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
    print("✅ textblob loaded")
except ImportError:
    TEXTBLOB_AVAILABLE = False
    print("⚠️ textblob missing. Run: pip install textblob")

# ============================================ #
# EASYOCR SETUP                                 #
# ============================================ #
try:
    import easyocr
    print("⏳ Initializing EasyOCR (first run downloads a model, ~30 sec)...")
    _EASYOCR_READER = easyocr.Reader(['en'], gpu=False, verbose=False)
    EASYOCR_AVAILABLE = True
    print("✅ EasyOCR initialized successfully")
except Exception as e:
    _EASYOCR_READER = None
    EASYOCR_AVAILABLE = False
    print(f"⚠️ EasyOCR not available: {e}")
    print("   Run: pip install easyocr")


# ============================================ #
# IMAGE HELPERS                                 #
# ============================================ #
def _load_image(path, size=(400, 400)):
    """Load + standardize an image."""
    if not CV2_AVAILABLE:
        return None
    img = cv2.imread(path)
    if img is None:
        return None
    return cv2.resize(img, size)


# ============================================ #
# METHOD 1: Perceptual Hash                     #
# ============================================ #
def _phash_difference(path1, path2):
    if not IMAGEHASH_AVAILABLE:
        return None
    try:
        h1 = imagehash.phash(Image.open(path1))
        h2 = imagehash.phash(Image.open(path2))
        distance = h1 - h2
        return min(100, int((distance / 64) * 100))
    except Exception:
        return None


# ============================================ #
# METHOD 2: Color Histogram (HSV)               #
# ============================================ #
def _histogram_difference(img1, img2):
    if not CV2_AVAILABLE or img1 is None or img2 is None:
        return None
    try:
        hsv1 = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)
        
        h1_hue = cv2.calcHist([hsv1], [0], None, [50], [0, 180])
        h2_hue = cv2.calcHist([hsv2], [0], None, [50], [0, 180])
        cv2.normalize(h1_hue, h1_hue, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(h2_hue, h2_hue, 0, 1, cv2.NORM_MINMAX)
        hue_sim = max(0, cv2.compareHist(h1_hue, h2_hue, cv2.HISTCMP_CORREL))
        
        h1_sat = cv2.calcHist([hsv1], [1], None, [50], [0, 256])
        h2_sat = cv2.calcHist([hsv2], [1], None, [50], [0, 256])
        cv2.normalize(h1_sat, h1_sat, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(h2_sat, h2_sat, 0, 1, cv2.NORM_MINMAX)
        sat_sim = max(0, cv2.compareHist(h1_sat, h2_sat, cv2.HISTCMP_CORREL))
        
        avg_sim = (hue_sim + sat_sim) / 2
        return int((1 - avg_sim) * 100)
    except Exception:
        return None


# ============================================ #
# METHOD 3: SSIM                                #
# ============================================ #
def _ssim_difference(img1, img2):
    if not SSIM_AVAILABLE or img1 is None or img2 is None:
        return None
    try:
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        score = ssim(gray1, gray2)
        return int((1 - score) * 100)
    except Exception:
        return None


# ============================================ #
# METHOD 4: Local Patch Analysis (STAIN DETECTOR) #
# ============================================ #
def _patch_difference(img1, img2, grid=8):
    if not SSIM_AVAILABLE or img1 is None or img2 is None:
        return None
    try:
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        
        H, W = gray1.shape
        ph, pw = H // grid, W // grid
        patch_diffs = []
        
        for i in range(grid):
            for j in range(grid):
                p1 = gray1[i*ph:(i+1)*ph, j*pw:(j+1)*pw]
                p2 = gray2[i*ph:(i+1)*ph, j*pw:(j+1)*pw]
                if p1.size > 0 and p2.size > 0 and p1.shape == p2.shape:
                    try:
                        s = ssim(p1, p2)
                        patch_diffs.append(1 - s)
                    except Exception:
                        pass
        
        if not patch_diffs:
            return None
        
        patch_diffs.sort(reverse=True)
        top_n = max(1, len(patch_diffs) // 10)
        worst_avg = sum(patch_diffs[:top_n]) / top_n
        return int(worst_avg * 100)
    except Exception:
        return None


# ============================================ #
# METHOD 5: Pixel Difference                    #
# ============================================ #
def _pixel_difference(img1, img2):
    if img1 is None or img2 is None:
        return None
    try:
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray1 = (gray1 - gray1.mean()) / (gray1.std() + 1e-6)
        gray2 = (gray2 - gray2.mean()) / (gray2.std() + 1e-6)
        diff = np.abs(gray1 - gray2)
        significant = np.sum(diff > 1.0) / diff.size
        return min(100, int(significant * 100))
    except Exception:
        return None


# ============================================ #
# METHOD 6: NLP TEXT ANALYSIS                   #
# ============================================ #
NEGATIVE_KEYWORDS = {
    'fake': 20, 'counterfeit': 20, 'scam': 20, 'fraud': 20,
    'not original': 20, 'not authentic': 20, 'duplicate': 20,
    'damaged': 12, 'broken': 12, 'torn': 12, 'defective': 12,
    'stained': 12, 'dirty': 12, 'wrong': 12, 'different': 12,
    'not as described': 12, 'wrong size': 12, 'wrong color': 12,
    'different color': 12, 'different size': 12,
    'poor quality': 6, 'cheap': 6, 'used': 6, 'worn': 6,
    'missing': 6, 'incomplete': 6, 'disappointed': 6,
    'not worth': 6, 'poor material': 6,
}

def analyze_dispute_text(text):
    if not text or not text.strip():
        return {'text_score': 0, 'matched_keywords': [], 'sentiment': 0.0}
    
    text_lower = text.lower()
    matched = []
    keyword_score = 0
    
    for kw, weight in NEGATIVE_KEYWORDS.items():
        if kw in text_lower:
            matched.append(kw)
            keyword_score += weight
    
    keyword_score = min(keyword_score, 70)
    
    sentiment = 0.0
    if TEXTBLOB_AVAILABLE:
        try:
            sentiment = TextBlob(text).sentiment.polarity
        except Exception:
            pass
    
    sentiment_score = int(abs(sentiment) * 30) if sentiment < 0 else 0
    total_score = min(keyword_score + sentiment_score, 100)
    
    return {
        'text_score': total_score,
        'matched_keywords': matched,
        'sentiment': sentiment,
    }


# ============================================ #
# METHOD 7: EasyOCR SIZE TAG ANALYSIS           #
# ============================================ #
STANDARD_SIZES = ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL',
                  '28', '30', '32', '34', '36', '38', '40', '42', '44', '46']


def analyze_size_tag(image_path, ordered_size, buyer_reported_size_issue=False):
    print("\n" + "=" * 60)
    print("🔍 SIZE TAG OCR ANALYSIS (EasyOCR)")
    print("=" * 60)
    
    if not ordered_size:
        print("❌ No ordered size to compare against")
        return {'size_mismatch': False, 'detected_tag_text': ''}
    
    ordered_size_clean = str(ordered_size).upper().strip()
    print(f"📏 Ordered size: '{ordered_size_clean}'")
    print(f"👤 Buyer reported size issue: {buyer_reported_size_issue}")
    
    # If OCR is unavailable, fall back to text signal
    if not EASYOCR_AVAILABLE or not image_path:
        print("⚠️  OCR unavailable → falling back to buyer text")
        if buyer_reported_size_issue:
            print("🚨 Buyer mentioned size issue in text → MISMATCH (weak)")
            return {'size_mismatch': True, 'detected_tag_text': 'OCR unavailable — inferred from text'}
        return {'size_mismatch': False, 'detected_tag_text': ''}
    
    print(f"🖼️  Image path: {image_path}")
    
    if not os.path.exists(image_path):
        print(f"❌ File does not exist")
        if buyer_reported_size_issue:
            return {'size_mismatch': True, 'detected_tag_text': 'File missing — inferred from text'}
        return {'size_mismatch': False, 'detected_tag_text': ''}
    
    try:
        results = _EASYOCR_READER.readtext(image_path)
        detected_words = []
        for (bbox, text, confidence) in results:
            if confidence > 0.2:
                detected_words.append(text.upper().strip())
        
        combined_text = ' '.join(detected_words)
        print(f"📝 Detected words: {detected_words}")
        print(f"📝 Combined: '{combined_text}'")
        
        # Case A: OCR read nothing useful
        if not combined_text:
            print("⚠️  OCR read nothing → falling back to buyer text")
            if buyer_reported_size_issue:
                print("🚨 Buyer mentioned size issue → MISMATCH (weak)")
                return {'size_mismatch': True, 'detected_tag_text': 'OCR empty — inferred from text'}
            return {'size_mismatch': False, 'detected_tag_text': ''}
        
        # Case B: Found the SAME size as ordered → real Match
        if re.search(r'\b' + re.escape(ordered_size_clean) + r'\b', combined_text):
            print(f"✅ Found ordered size '{ordered_size_clean}' → MATCH (strong)")
            return {'size_mismatch': False, 'detected_tag_text': combined_text}
        
        # Case C: Found a DIFFERENT standard size → real Mismatch
        for size in sorted(STANDARD_SIZES, key=len, reverse=True):
            if size == ordered_size_clean:
                continue
            if re.search(r'\b' + re.escape(size) + r'\b', combined_text):
                print(f"🚨 DIFFERENT size '{size}' → MISMATCH (strong)")
                return {
                    'size_mismatch': True,
                    'detected_tag_text': combined_text,
                    'found_size': size,
                }
        
        # Case D: Read text but no size found
        print("⚠️  No size in OCR text → falling back to buyer text")
        if buyer_reported_size_issue:
            print("🚨 Buyer mentioned size issue → MISMATCH (weak)")
            return {'size_mismatch': True, 'detected_tag_text': combined_text + ' [inferred from text]'}
        return {'size_mismatch': False, 'detected_tag_text': combined_text}
    
    except Exception as e:
        print(f"❌ OCR Exception: {e}")
        if buyer_reported_size_issue:
            return {'size_mismatch': True, 'detected_tag_text': f'OCR_ERROR: {e}'}
        return {'size_mismatch': False, 'detected_tag_text': f'OCR_ERROR: {e}'}


# ============================================ #
# IMAGE COMPARISON (combines 5 methods)         #
# ============================================ #
def compare_images(original_path, received_path):
    if not original_path or not received_path:
        return {'difference_score': 0, 'error': 'Missing image path', 'debug': {}}
    
    if not os.path.exists(original_path) or not os.path.exists(received_path):
        return {'difference_score': 0, 'error': 'File not found', 'debug': {}}
    
    img1 = _load_image(original_path) if CV2_AVAILABLE else None
    img2 = _load_image(received_path) if CV2_AVAILABLE else None
    
    scores = {
        'phash': _phash_difference(original_path, received_path),
        'histogram': _histogram_difference(img1, img2),
        'ssim': _ssim_difference(img1, img2),
        'patch': _patch_difference(img1, img2),
        'pixel': _pixel_difference(img1, img2),
    }
    
    valid_scores = {k: v for k, v in scores.items() if v is not None}
    
    if not valid_scores:
        return {
            'difference_score': 0,
            'error': 'All image comparison methods failed.',
            'debug': scores,
        }
    
    weights = {'patch': 0.40, 'ssim': 0.20, 'histogram': 0.20, 'phash': 0.10, 'pixel': 0.10}
    
    total_weight = sum(weights[k] for k in valid_scores.keys())
    weighted_sum = sum(valid_scores[k] * weights[k] for k in valid_scores.keys())
    difference_score = int(weighted_sum / total_weight) if total_weight > 0 else 0
    
    if 'patch' in valid_scores and valid_scores['patch'] > 35:
        difference_score = min(100, difference_score + 12)
    if 'histogram' in valid_scores and valid_scores['histogram'] > 40:
        difference_score = min(100, difference_score + 8)
    
    return {
        'difference_score': difference_score,
        'similarity_percent': 100 - difference_score,
        'error': None,
        'debug': scores,
    }


# ============================================ #
# MASTER ANALYZE FUNCTION                       #
# ============================================ #
# ============================================ #
# MASTER ANALYZE FUNCTION                       #
# ============================================ #
def analyze_dispute(order_image_path, received_image_path, dispute_text,
                    ordered_size=None, tag_image_path=None, selected_keywords=""):
    """Full AI analysis — called from raise_dispute view."""
    
    print("\n" + "#" * 60)
    print("# AI DISPUTE ANALYSIS START")
    print("#" * 60)
    
    # =============================================
    # 1. IMAGE COMPARISON
    # =============================================
    image_result = compare_images(order_image_path, received_image_path)
    image_score = image_result['difference_score']
    print(f"\n📊 Image comparison debug: {image_result.get('debug', {})}")
    print(f"📊 Image difference score: {image_score}")
    
    # =============================================
    # 2. TEXT ANALYSIS
    # =============================================
    combined_text = f"{dispute_text} {selected_keywords}"
    text_result = analyze_dispute_text(combined_text)
    print(f"\n📊 Text score: {text_result['text_score']}")
    print(f"📊 Matched keywords: {text_result['matched_keywords']}")
    
    # =============================================
    # 3. SIZE TAG OCR (with buyer text fallback)
    # =============================================
    # Detect if buyer mentioned size issues in their text or selected keywords
    size_keywords = [
        'wrong size', 'different size', 'size issue', 'size mismatch',
        'too small', 'too big', 'smaller', 'larger',
        "doesn't fit", 'does not fit', 'wrong fit', 'tight', 'loose',
        'wrong size', 'size'
    ]
    text_lower = combined_text.lower()
    buyer_reported_size_issue = any(kw in text_lower for kw in size_keywords)
    print(f"\n👤 Buyer reported size issue (from text): {buyer_reported_size_issue}")
    
    ocr_target = tag_image_path if tag_image_path else received_image_path
    size_result = analyze_size_tag(ocr_target, ordered_size, buyer_reported_size_issue)
    
    # =============================================
    # FINAL SCORE COMPOSITION
    # =============================================
    if image_result.get('error') and image_score == 0:
        # Image analysis failed — rely on text only
        final_score = text_result['text_score']
        print("\n⚠️  Image analysis failed → using text score only")
    else:
        # Weighted: 40% image, 60% text
        final_score = int(image_score * 0.40 + text_result['text_score'] * 0.60)
        print(f"\n📊 Base score: {image_score}×0.40 + {text_result['text_score']}×0.60 = {final_score}")
    
    # Add +25 boost if size mismatch detected
    if size_result['size_mismatch']:
        final_score = min(100, final_score + 25)
        print(f"📊 +25 boost applied for size mismatch → {final_score}")
    
    # =============================================
    # VERDICT THRESHOLDS
    # =============================================
    if final_score >= 55:
        verdict = 'ACCEPT'
    elif final_score >= 30:
        verdict = 'REVIEW'
    else:
        verdict = 'REJECT'
    
    print(f"\n{'=' * 60}")
    print(f"🎯 FINAL SCORE: {final_score}  →  VERDICT: {verdict}")
    print(f"{'=' * 60}\n")
    
    return {
        'image_score': image_score,
        'similarity_percent': image_result.get('similarity_percent', 100),
        'text_score': text_result['text_score'],
        'matched_keywords': text_result['matched_keywords'],
        'sentiment': text_result['sentiment'],
        'final_score': final_score,
        'verdict': verdict,
        'image_error': image_result.get('error'),
        'size_mismatch': size_result['size_mismatch'],
        'detected_size_text': size_result.get('detected_tag_text', ''),
        'image_debug': image_result.get('debug', {}),
    }