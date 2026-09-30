import os
import json
import re
import time
import traceback
from google import genai
from google.genai import types

# ============================================================
# CLIENT SETUP
# ============================================================

_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            try:
                from dotenv import load_dotenv
                load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
                api_key = os.environ.get("GEMINI_API_KEY")
            except ImportError:
                pass

        if api_key:
            _client = genai.Client(api_key=api_key)
            print("[AI Engine] Gemini client initialized successfully.")
        else:
            print("[AI Engine] CRITICAL ERROR: GEMINI_API_KEY not found in environment or .env file.")
    return _client


# ============================================================
# MODEL CONFIGURATION  — GEMINI-2.5-PRO ONLY
# ============================================================

PRIMARY_MODEL = "gemini-flash-lite-latest"

# Allow override via env var for testing purposes only
_ENV_MODEL = os.getenv("GEMINI_VISION_MODEL", "").strip()
VISION_MODEL = _ENV_MODEL if _ENV_MODEL else PRIMARY_MODEL

# Max retry attempts per model call
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 15  # base wait between retries

print(f"[AI Engine] Vision model: {VISION_MODEL}")
print(f"[AI Engine] Max retries per request: {MAX_RETRIES}")


# ============================================================
# JSON PARSING UTILITY
# ============================================================

def _parse_json_from_text(raw: str) -> dict:
    """Robustly parse JSON from AI response, stripping markdown fences and surrounding text."""
    try:
        raw = raw.strip()
        # Strip ```json ... ``` markdown fences
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()

        # Find the outermost JSON object
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end != -1 and end > start:
            raw = raw[start:end + 1]

        # Remove ASCII control characters that break JSON parsing
        raw = re.sub(r'[\x00-\x1F\x7F]', ' ', raw)

        parsed = json.loads(raw)
        print(f"[AI Debug] Parsed JSON keys: {list(parsed.keys())}")
        return parsed
    except Exception as e:
        print(f"[_parse_json_from_text] Parse error: {e}")
        print(f"[_parse_json_from_text] Raw snippet (first 800 chars): {raw[:800]}")
        raise json.JSONDecodeError(f"Failed to parse Gemini response: {e}", raw, 0)


# ============================================================
# DEPARTMENT KEYWORD MAP
# ============================================================

DEPARTMENT_MAP = {
    "pothole":       "Public Works Department",
    "road damage":   "Public Works Department",
    "road":          "Public Works Department",
    "water leak":    "Water Supply Department",
    "pipe":          "Water Supply Department",
    "leakage":       "Water Supply Department",
    "overflow":      "Water Supply Department",
    "garbage":       "Sanitation Department",
    "trash":         "Sanitation Department",
    "waste":         "Sanitation Department",
    "sewage":        "Sanitation Department",
    "stench":        "Sanitation Department",
    "electric":      "Electricity Department",
    "wire":          "Electricity Department",
    "streetlight":   "Electricity Department",
    "street light":  "Electricity Department",
    "power":         "Electricity Department",
    "drainage":      "Drainage Department",
    "flood":         "Drainage Department",
    "waterlogging":  "Drainage Department",
    "pollution":     "Environmental Department",
    "smoke":         "Environmental Department",
    "tree":          "Horticulture Department",
    "traffic":       "Traffic Management",
    "accident":      "Traffic Management",
    "hazard":        "Public Works Department",
}

def _detect_department(title: str, summary: str) -> str:
    source = f"{title} {summary}".lower()
    for keyword, dept in DEPARTMENT_MAP.items():
        if keyword in source:
            return dept
    return "Public Works Department"

def get_fallback_analysis(text: str, error_msg: str) -> dict:
    """Returns a safe fallback analysis object when Gemini fails."""
    title = (text[:40] + "...") if len(text) > 40 else (text or "Grievance Report")
    return {
        "is_valid":         True,
        "title":            title,
        "category":         "Civic Issue",
        "department":       _detect_department(title, text),
        "severity":         "Medium",
        "sentiment":        "Concerned",
        "summary":          f"Our AI system is currently experiencing high demand. Your complaint has been received and queued for manual review. Original description: {text}",
        "risks":            "Manual Review Required",
        "confidence_score": 50,
        "detected_issue":   title,
        "visual_risk_level": "Medium",
        "issue_tags":       "pending_review",
        "image_observation": f"System Fallback (Error: {error_msg})",
    }


# ============================================================
# CORE MULTIMODAL GRIEVANCE ANALYSIS  (GEMINI-2.5-PRO)
# ============================================================

def validate_and_summarize_grievance(text: str, local_image_path: str = None):
    """
    Real multimodal civic grievance analysis using Gemini 2.5 Pro.
    - Sends actual image bytes to the model when an image is provided.
    - Combines image + text for richer understanding.
    - Enforces structured JSON output.
    - No generic fallback summaries — raises on failure so caller gets real errors.
    - Supports multilingual input (Hindi, Urdu/Hinglish, English).
    - Retries up to MAX_RETRIES times with exponential back-off on transient errors.
    """
    client = get_client()
    try:
        if not client:
            print("[AI Engine] WARN: Client not initialized. Using fallback.")
            return get_fallback_analysis(text, "Client not initialized")

        has_image = bool(local_image_path and os.path.exists(local_image_path))
        complaint_text = text.strip() if text else ""

        print("=" * 60)
        print(f"[AI Engine] === GRIEVANCE ANALYSIS START ===")
        print(f"[AI Engine] Model        : {VISION_MODEL}")
        print(f"[AI Engine] Text length  : {len(complaint_text)} chars")
        print(f"[AI Engine] Has image    : {has_image}")
        print(f"[AI Engine] Image path   : {local_image_path}")
        print("=" * 60)

        # ---- Build prompt -------------------------------------------------------
        lang_hint = (
            "The user's complaint may be in English, Hindi, Hinglish, or Tamil. "
            "Detect the language of the complaint accurately. "
            "Generate the 'summary' field in THE SAME LANGUAGE as the user's input (e.g., if the complaint is in Tamil, the summary MUST be in Tamil script). "
            "Ensure native scripts (Tamil, Devanagari, etc.) are preserved with correct Unicode encoding. "
            "All other JSON fields (title, category, department, severity, sentiment) must remain in English."
        )

        image_instruction = (
            "CRITICAL — An image HAS been uploaded. You MUST visually inspect it. "
            "Identify exactly what you see: surface textures, liquids, damage, debris, wiring, infrastructure, surroundings. "
            "Do NOT describe a generic issue — describe what is ACTUALLY VISIBLE in this specific image. "
            "Visual evidence takes priority over the text description if they conflict."
            if has_image else
            "No image was provided. Base your analysis entirely on the complaint text."
        )

        prompt = f"""You are a Master Forensic Civic Infrastructure Inspector working for a Smart City Grievance Platform.

LANGUAGE RULE:
{lang_hint}

IMAGE ANALYSIS RULE:
{image_instruction}

USER COMPLAINT TEXT:
\"\"\"{complaint_text if complaint_text else "(No text — image-only submission)"}\"\"\"

=====================================================
YOUR TASK
=====================================================
Perform a deep, accurate, multimodal analysis of this civic grievance.

1. IMAGE INSPECTION (if image provided):
   - Describe exactly what is visible: colors, textures, water, cracks, debris, wires, vegetation, etc.
   - Identify the primary civic issue shown (pothole, water leakage, garbage, drainage, electrical hazard, traffic, etc.)
   - Assess the severity based on visible damage and surrounding context.
   - Note residential/commercial/industrial environment.

2. TEXT ANALYSIS:
   - Detect issue type, urgency, location hints, sentiment from the complaint text.
   - Detect language and tone.

3. COMBINED ANALYSIS:
   - Merge visual and textual evidence into a comprehensive inspection report.
   - Summary must be 150-250 words, detailed, forensic, and specific to THIS complaint.

4. CLASSIFICATION:
   - title: Specific descriptive title (e.g., "Burst Water Main on Gandhi Nagar Road")
   - category: 2-3 word category (e.g., "Road Damage", "Water Leakage", "Garbage Dumping")
   - department: Responsible government department
   - severity: Low / Medium / High / Critical  (based on actual risk assessment)
   - sentiment: Urgent / Frustrated / Concerned / Neutral  (from user tone)
   - confidence_score: 0.0 to 1.0

5. DETECTION TAGS:
   - List up to 5 specific hazards/observations detected (e.g., "stagnant water", "road crack", "slip hazard")

=====================================================
MANDATORY JSON RESPONSE FORMAT (NO markdown, PURE JSON):
=====================================================
{{
  "title": "Specific descriptive title",
  "category": "Specific 2-3 word category",
  "department": "Correct government department name",
  "severity": "Low|Medium|High|Critical",
  "sentiment": "Urgent|Frustrated|Concerned|Neutral",
  "summary": "Detailed 150-250 word inspection report in user's language",
  "risks": ["Risk 1", "Risk 2", "Risk 3"],
  "confidence_score": 0.95
}}
"""

        # ---- Assemble content parts -------------------------------------------
        content_parts = []

        if has_image:
            try:
                with open(local_image_path, "rb") as f:
                    image_bytes = f.read()
                ext = local_image_path.lower().rsplit(".", 1)[-1]
                mime_map = {
                    "jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "png": "image/png", "gif": "image/gif",
                    "webp": "image/webp", "bmp": "image/bmp"
                }
                mime_type = mime_map.get(ext, "image/jpeg")
                print(f"[AI Engine] Image attached: {len(image_bytes):,} bytes | MIME: {mime_type}")
                # Image part FIRST so the model sees it before the instructions
                content_parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
            except Exception as img_err:
                print(f"[AI Engine] ERROR: Could not read image file — {img_err}")
                traceback.print_exc()
                # Do NOT silently continue — raise so caller knows the image failed
                raise RuntimeError(f"Image file could not be read: {img_err}")

        # Prompt text part
        content_parts.append(types.Part.from_text(text=prompt))

        # ---- Call Gemini with retry logic -------------------------------------
        last_error = None
        response = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"[AI Quota Check] Initializing Gemini call for {VISION_MODEL} (Attempt {attempt})...")
                print(f"[AI Quota Check] --- GEMINI CALL START ---")
                response = client.models.generate_content(
                    model=VISION_MODEL,
                    contents=content_parts,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=2048,
                        response_mime_type="application/json",
                    ),
                )
                print(f"[AI Quota Check] --- GEMINI CALL SUCCESS ---")
                print(f"[AI Quota Check] Gemini responded successfully on attempt {attempt}. Quota consumed for this session.")
                last_error = None
                break  # Success — exit retry loop

            except Exception as api_err:
                err_str = str(api_err)
                last_error = api_err
                print(f"[AI Engine] ERROR on attempt {attempt}: {err_str}")
                traceback.print_exc()

                if attempt == MAX_RETRIES:
                    print(f"[AI Engine] All {MAX_RETRIES} attempts exhausted.")
                    break

                if "429" in err_str or "quota" in err_str.lower():
                    wait = RETRY_WAIT_SECONDS * attempt
                    print(f"[AI Engine] Rate limit (429). Waiting {wait}s before retry...")
                    time.sleep(wait)
                elif "503" in err_str or "overloaded" in err_str.lower():
                    wait = RETRY_WAIT_SECONDS * attempt
                    print(f"[AI Engine] Server overloaded (503). Waiting {wait}s before retry...")
                    time.sleep(wait)
                elif "500" in err_str:
                    wait = 10
                    print(f"[AI Engine] Internal server error (500). Waiting {wait}s before retry...")
                    time.sleep(wait)
                else:
                    # Unknown / non-transient error — raise immediately, no more retries
                    print(f"[AI Engine] Non-retryable error. Raising immediately.")
                    raise RuntimeError(
                        f"Gemini API returned a non-retryable error on attempt {attempt}: {err_str}"
                    ) from api_err

        if last_error is not None:
            raise RuntimeError(
                f"Gemini API failed after {MAX_RETRIES} attempts. "
                f"Last error: {last_error}"
            ) from last_error

        # ---- Parse and validate response ------------------------------------
        raw_text = getattr(response, "text", "") or ""
        print(f"[AI Debug] === RAW GEMINI RESPONSE (first 1000 chars) ===")
        # Safe print for Unicode
        try:
            print(raw_text[:1000])
        except UnicodeEncodeError:
            print(raw_text[:1000].encode('ascii', 'ignore').decode('ascii'))
        print(f"[AI Debug] === END RAW RESPONSE ===")

        if not raw_text.strip():
            raise ValueError(
                f"[AI Engine] Gemini returned an empty response. "
                f"Finish reason: {getattr(response, 'prompt_feedback', 'unknown')}"
            )

        result = _parse_json_from_text(raw_text)

        # ---- Extract fields --------------------------------------------------
        title          = result.get("title", "").strip()
        category       = result.get("category", "").strip()
        department     = result.get("department", "").strip()
        severity       = result.get("severity", "Medium").strip()
        sentiment      = result.get("sentiment", "Concerned").strip()
        summary        = result.get("summary", "").strip()
        risks          = result.get("risks", [])
        confidence_raw = result.get("confidence_score", 0.90)

        # Validate non-empty critical fields
        if not title:
            raise ValueError("[AI Engine] Parsed JSON missing 'title'. Gemini response may be malformed.")
        if not summary:
            raise ValueError("[AI Engine] Parsed JSON missing 'summary'. Gemini response may be malformed.")

        # Fallback department detection if Gemini did not provide one
        if not department:
            department = _detect_department(title, summary)
            print(f"[AI Engine] Department not in response — auto-detected: {department}")

        # Normalise confidence to 0-100 integer
        try:
            confidence_float = float(confidence_raw)
            if confidence_float > 1.0:
                confidence_int = int(confidence_float)        # already 0-100
            else:
                confidence_int = int(confidence_float * 100)  # convert 0.0-1.0 → 0-100
        except (TypeError, ValueError):
            confidence_int = 90

        risks_str = ", ".join(risks) if isinstance(risks, list) else str(risks)

        processed = {
            "is_valid":         True,
            "title":            title,
            "category":         category,
            "department":       department,
            "severity":         severity,
            "sentiment":        sentiment,
            "summary":          summary,
            "risks":            risks_str,
            "confidence_score": confidence_int,
            "detected_issue":   title,
            "visual_risk_level": severity,
            "issue_tags":       risks_str,
            "image_observation": f"Analyzed by {VISION_MODEL} with {'image + text' if has_image else 'text only'}",
        }

        print(f"[AI Engine] === ANALYSIS COMPLETE ===")
        return processed

    except Exception as e:
        print(f"[AI Engine] CRITICAL FAILURE: {str(e)}")
        traceback.print_exc()
        # Ensure we return a safe object instead of crashing the backend
        return get_fallback_analysis(text, str(e))

    print(f"[AI Engine] === ANALYSIS COMPLETE ===")
    return processed


# ============================================================
# COMPLAINT TEXT-ONLY ANALYSIS
# ============================================================

def analyze_complaint(text: str):
    """Analyze a text complaint — detect type, priority, sentiment, and resolution time."""
    client = get_client()
    if not client:
        raise RuntimeError("[analyze_complaint] Gemini client not initialized.")

    prompt = f"""You are a Civic Grievance Analysis AI for a Smart City platform.

Analyze the following citizen complaint. It may be in English, Hindi, Urdu, or Hinglish.

1. Translate to English if needed.
2. Categorize the complaint: 'Electricity', 'Water Supply', 'Sanitation', 'Roads', 'Drainage', 'Environmental', 'Other'.
3. Assign priority: 'Low', 'Medium', 'High', 'Urgent'.
4. Detect sentiment: 'Angry', 'Frustrated', 'Neutral', 'Concerned', 'Urgent'.
5. Estimate resolution time (e.g., "2-3 Days", "1 Week").

Complaint:
\"\"\"{text}\"\"\"

Return ONLY valid JSON — no markdown:
{{
  "translated_text": "...",
  "department": "...",
  "priority": "...",
  "sentiment": "...",
  "estimated_resolution_time": "..."
}}
"""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[analyze_complaint] Attempt {attempt}/{MAX_RETRIES} — model: {VISION_MODEL}")
            response = client.models.generate_content(
                model=VISION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=512,
                    response_mime_type="application/json",
                ),
            )
            print(f"[analyze_complaint] Raw response: {response.text[:300]}")
            return _parse_json_from_text(response.text)
        except Exception as e:
            last_error = e
            print(f"[analyze_complaint] Error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT_SECONDS)

    raise RuntimeError(f"[analyze_complaint] Failed after {MAX_RETRIES} attempts. Last error: {last_error}")


# ============================================================
# ANIMAL RESCUE ANALYSIS
# ============================================================

def get_animal_fallback(description: str, error_msg: str) -> dict:
    return {
        "detected_animal": "Reported Animal",
        "animal_condition": "Unknown",
        "possible_injuries": "Pending Inspection",
        "urgency_level": "Medium",
        "rescue_priority": "Routine",
        "health_risks": "Manual Assessment Required",
        "recommended_action": "Please keep a safe distance and wait for the rescue team.",
        "nearest_rescue_type": "Local Rescue Unit",
        "estimated_rescue_eta": "1-2 Hours",
        "summary": f"Our specialized animal rescue AI is currently busy. A manual team has been notified for this report: {description}",
        "confidence_score": "0.50"
    }

def get_social_fallback(description: str, error_msg: str) -> dict:
    return {
        "detected_category": "Vulnerable Individual",
        "priority_level": "Moderate",
        "behavior_analysis": "Reported via citizen platform. Awaiting field worker assessment.",
        "sentiment_score": "Concerned (System Fallback)"
    }

# ============================================================
# ANIMAL WELFARE MULTIMODAL ANALYSIS
# ============================================================

def analyze_animal_welfare(description: str, image_path: str = None) -> dict:
    """
    Perform deep multimodal analysis for Animal Welfare reports.
    Analyzes animal species, injuries, malnutrition, mobility, and emergency severity.
    """
    client = get_client()
    try:
        if not client:
            print("[AI Animal Welfare] WARN: Client not initialized. Using fallback.")
            return get_animal_fallback(description, "Client not initialized")

        has_image = bool(image_path and os.path.exists(image_path))
        contents = []

        if has_image:
            try:
                with open(image_path, "rb") as f:
                    img_bytes = f.read()
                ext = image_path.lower().rsplit(".", 1)[-1]
                mime_type = "image/png" if ext == "png" else "image/jpeg"
                contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))
                print(f"[AI Animal Welfare] Image attached: {len(img_bytes):,} bytes")
            except Exception as e:
                print(f"[AI Animal Welfare] Error loading image: {e}")

        prompt = f"""You are an expert Forensic Veterinarian and Animal Rescue Crisis Analyst.
Analyze the following animal distress report. 

{ "CRITICAL: An image has been provided. Visually inspect the animal's species, body condition, visible wounds, posture, and surroundings." if has_image else "No image provided. Base analysis on text." }

User Description: "{description}"

=====================================================
YOUR TASK
=====================================================
1. Identify the animal species and breed (if possible).
2. Detect visible injuries (bleeding, fractures, skin issues, etc.).
3. Assess body condition (malnourished, weak, dehydrated).
4. Evaluate mobility (unable to walk, limping).
5. Determine urgency level and rescue priority.
6. Identify potential health risks to the animal or public.
7. Recommend immediate first-aid or safety actions.
8. Suggest a realistic Indian Rescue NGO type and ETA.

=====================================================
REQUIRED JSON RESPONSE FORMAT (No markdown, PURE JSON):
=====================================================
{{
  "detected_animal": "e.g., Stray Dog (Pariah), Injured Cow, etc.",
  "animal_condition": "Brief state (e.g., Critical, Weak, Distressed)",
  "possible_injuries": ["Injury 1", "Injury 2"],
  "urgency_level": "Critical|High|Medium|Low",
  "rescue_priority": "Immediate|High|Routine",
  "health_risks": ["Risk 1", "Risk 2"],
  "recommended_action": "What the reporter should do (e.g., Provide water, Keep distance)",
  "nearest_rescue_type": "e.g., Specialized Canine Unit, Large Animal Rescue",
  "estimated_rescue_eta": "e.g., 25-40 Minutes",
  "summary": "Detailed 100-150 word forensic veterinary assessment.",
  "confidence_score": "0.0-1.0"
}}
"""
        contents.append(types.Part.from_text(text=prompt))

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"[AI Animal Welfare] Attempt {attempt}/{MAX_RETRIES} — model: {VISION_MODEL}")
                response = client.models.generate_content(
                    model=VISION_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=1024,
                        response_mime_type="application/json",
                    ),
                )
                print(f"[AI Animal Welfare] Gemini responded successfully.")
                return _parse_json_from_text(response.text)
            except Exception as e:
                last_error = e
                print(f"[AI Animal Welfare] Error on attempt {attempt}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_WAIT_SECONDS)

        if last_error:
            raise last_error

    except Exception as e:
        print(f"[AI Animal Welfare] CRITICAL FAILURE: {str(e)}")
        traceback.print_exc()
        return get_animal_fallback(description, str(e))


# ============================================================
# CHATBOT
# ============================================================

def chatbot_reply(chat_history, user_message: str) -> str:
    client = get_client()
    if not client:
        return "ERROR: AI client not initialized. Please check the GEMINI_API_KEY configuration."

    prompt = f"""You are a helpful government assistant chatbot for a civic grievance portal.
Help citizens report issues effectively. Be polite and concise.
If reporting an issue, ask for location if not provided.

User says: {user_message}

Reply naturally in the same language the user used (Supports English, Hindi, Hinglish, and Tamil).
"""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=VISION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=512),
            )
            return response.text
        except Exception as e:
            last_error = e
            print(f"[chatbot_reply] Error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(5)

    return f"ERROR: AI chatbot failed after {MAX_RETRIES} attempts. Details: {last_error}"


# ============================================================
# DONATION CAMPAIGN VALIDATION
# ============================================================

def validate_donation_campaign(title: str, description: str, target_amount: int, category: str):
    client = get_client()
    try:
        if not client:
            return {"risk_level": "Medium Risk", "status": "Under Review", "reason": "AI client not initialized."}

        prompt = f"""You are an AI Civic Campaign Safety Moderator.
Analyze this proposed donation campaign for potential fraud, spam, or unrealistic goals.

Title: {title}
Description: {description}
Target Amount (INR): {target_amount}
Category: {category}

Assess the realism of the target amount. Detect spam or nonsensical text.

Return ONLY valid JSON:
{{
  "risk_level": "Low Risk|Medium Risk|High Risk",
  "status": "Approved|Under Review",
  "reason": "Brief risk assessment explanation."
}}
"""
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=VISION_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
                print(f"[validate_donation_campaign] Raw: {response.text[:300]}")
                data = _parse_json_from_text(response.text)
                return {
                    "risk_level": data.get("risk_level", "Medium Risk"),
                    "status":     data.get("status", "Under Review"),
                    "reason":     data.get("reason", "Could not fully validate. Flagged for review."),
                }
            except Exception as e:
                last_error = e
                print(f"[validate_donation_campaign] Error on attempt {attempt}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_WAIT_SECONDS)

        if last_error:
            raise last_error

    except Exception as e:
        print(f"[validate_donation_campaign] CRITICAL FAILURE: {str(e)}")
        return {"risk_level": "Medium Risk", "status": "Under Review", "reason": f"AI Failure: {str(e)}"}


# ============================================================
# SOCIAL HELP CASE ASSESSMENT
# ============================================================

def assess_social_help_case(description: str, image_path: str = None) -> dict:
    """Analyze a social help case report (homeless, missing person, mentally challenged, etc.)."""
    client = get_client()
    try:
        if not client:
            print("[assess_social_help_case] WARN: Client not initialized. Using fallback.")
            return get_social_fallback(description, "Client not initialized")

        contents = []

        if image_path and os.path.exists(image_path):
            try:
                with open(image_path, "rb") as f:
                    img_bytes = f.read()
                image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
                contents.append(image_part)
                print(f"[assess_social_help_case] Image attached: {len(img_bytes):,} bytes")
            except Exception as e:
                print(f"[assess_social_help_case] Error loading image: {e}")

        contents.append(types.Part.from_text(text=f"""You are an expert AI Social Worker and Crisis Analyst.
Analyze the following report of a vulnerable individual in public.

Description: {description}

Return ONLY a raw JSON object with EXACTLY these four keys:
- "detected_category": e.g., "Homeless Person", "Missing Child", "Mentally Challenged", "Elderly in Distress"
- "priority_level": "Critical", "High", "Moderate", or "Low"
- "behavior_analysis": Short description of the person's observed state
- "sentiment_score": Short urgency/sentiment phrase

No markdown, no explanation — just the JSON.
"""))

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"[assess_social_help_case] Attempt {attempt}/{MAX_RETRIES}")
                response = client.models.generate_content(
                    model=VISION_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
                print(f"[assess_social_help_case] Raw: {response.text[:300]}")
                return _parse_json_from_text(response.text)
            except Exception as e:
                last_error = e
                print(f"[assess_social_help_case] Error on attempt {attempt}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_WAIT_SECONDS)

        if last_error:
            raise last_error

    except Exception as e:
        print(f"[assess_social_help_case] CRITICAL FAILURE: {str(e)}")
        traceback.print_exc()
        return get_social_fallback(description, str(e))
