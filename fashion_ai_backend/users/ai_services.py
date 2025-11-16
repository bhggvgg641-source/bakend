
import google.generativeai as genai
import os
import json
import cv2
import numpy as np
from serpapi import GoogleSearch
import requests
from django.conf import settings
import uuid
import base64

# قراءة مفاتيح Gemini و SerpApi من متغيرات البيئة (بدلاً من قيم صريحة)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")

# مفاتيح Banana.dev يتم قراءتها من متغيرات البيئة
BANANA_API_KEY = os.environ.get("BANANA_API_KEY")
BANANA_MODEL_KEY = os.environ.get("BANANA_MODEL_KEY")

# تهيئة Gemini إن كان المفتاح متوفرًا
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"خطأ في تهيئة Gemini: {e}")
else:
    print("تحذير: لم يتم العثور على GEMINI_API_KEY في البيئة.")

def analyze_user_and_generate_prompts(user, location_info):
    """
    يحلل بيانات المستخدم وصورته الشخصية لتوليد أوصاف (prompts) دقيقة للملابس.
    """
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    analysis_prompt = f"""
    تحليل شامل للمستخدم لتقديم توصيات أزياء:

    **بيانات المستخدم:**
    - الطول: {user.height} سم
    - الوزن: {user.weight} كجم
    - لون البشرة: {user.skin_color}
    - الموقع الجغرافي: {location_info}

    **المهمة:**
    1.  بناءً على بيانات المستخدم، قم بتحليل نوع الجسم (نحيف، متوسط، رياضي، ممتلئ) ونظرية الألوان المناسبة للون بشرته.
    2.  مع الأخذ في الاعتبار الموقع الجغرافي (الذي قد يؤثر على الطقس والثقافة)، اقترح 3 أنماط أزياء مختلفة قد تناسب هذا المستخدم (مثال: كلاسيكي، عصري، رياضي، بوهيمي).
    3.  لكل نمط مقترح، قم بإنشاء وصف نصي دقيق ومفصل (prompt) لتوليد صورة لقطعة ملابس واحدة (بدون عارض أزياء) تمثل هذا النمط. يجب أن يكون الوصف جاهزًا للاستخدام في نموذج توليد الصور.

    **شروط وصف الصورة (Prompt):**
    - يجب أن يصف قطعة الملابس فقط (مثال: "قميص"، "بنطال"، "فستان").
    - يجب أن تكون الخلفية بسيطة ومحايدة (مثال: "خلفية استوديو رمادية فاتحة").
    - يجب أن تكون الصورة واقعية (photorealistic).
    - يجب تحديد ألوان وأنواع أقمشة دقيقة.
    - يجب أن تولد 3 أوصاف مختلفة لقطع ملابس مختلفة.

    **مثال على المخرجات المطلوبة (بتنسيق JSON):**
    {{
        "analysis": "المستخدم لديه بنية جسم متوسطة ويميل الطول. الألوان الدافئة مثل البيج والزيتي تناسب لون بشرته. موقعه في الرياض يقترح الحاجة لملابس صيفية خفيفة.",
        "prompts": [
            "صورة واقعية لبنطال تشينو رجالي بلون بيج، بقصة مستقيمة، مصنوع من القطن الخفيف، معروض على خلفية استوديو رمادية فاتحة.",
            "صورة واقعية لقميص بولو أبيض اللون، بقصة ضيقة (slim-fit)، مصنوع من قماش البيكيه، معروض على خلفية استوديو رمادية فاتحة.",
            "صورة واقعية لجاكيت خفيف (bomber jacket) بلون زيتي، مصنوع من النايلون، معروض على خلفية استوديو رمادية فاتحة."
        ]
    }}
    """

    response = model.generate_content(analysis_prompt)

    try:
        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        return cleaned_response
    except Exception as e:
        print(f"خطأ في تحليل استجابة Gemini: {e}")
        return None

def generate_image_from_prompt(prompt, request):
    """
    يولد صورة فعلية للوصف النصي باستخدام Banana.dev إذا توفرت المفاتيح،
    وإلا يعود لصورة بديلة.
    """
    print(f"توليد صورة للوصف عبر Banana.dev إن أمكن: {prompt}")

    output_dir = os.path.join(settings.MEDIA_ROOT, "generated_images")
    os.makedirs(output_dir, exist_ok=True)
    image_filename = f"generated_image_{abs(hash(prompt))}_{uuid.uuid4().hex[:6]}.jpg"
    output_path = os.path.join(output_dir, image_filename)

    saved = False
    if BANANA_API_KEY and BANANA_MODEL_KEY:
        try:
            payload = {
                "apikey": BANANA_API_KEY,
                "modelKey": BANANA_MODEL_KEY,
                "modelInputs": {"prompt": prompt},
                "startOnly": False,
            }
            resp = requests.post("https://api.banana.dev/v4/", json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            outputs = data.get("modelOutputs") or data.get("output") or {}
            image_b64 = None
            image_url = None
            if isinstance(outputs, list) and len(outputs) > 0:
                first = outputs[0]
                image_b64 = first.get("image_base64") or first.get("base64")
                image_url = first.get("image_url") or first.get("url")
            elif isinstance(outputs, dict):
                image_b64 = outputs.get("image_base64") or outputs.get("base64")
                image_url = outputs.get("image_url") or outputs.get("url")

            if image_b64:
                try:
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(image_b64))
                    saved = True
                except Exception as e:
                    print(f"خطأ في فك ترميز الصورة Base64: {e}")
            elif image_url:
                try:
                    rimg = requests.get(image_url, timeout=60)
                    rimg.raise_for_status()
                    with open(output_path, "wb") as f:
                        f.write(rimg.content)
                    saved = True
                except Exception as e:
                    print(f"خطأ في تنزيل الصورة من الرابط: {e}")
            
            if not saved:
                 print("استجابة Banana لم تتضمن صورة قابلة للحفظ؛ سنستخدم صورة بديلة.")

        except Exception as e:
            print(f"خطأ في استدعاء Banana.dev: {e}")

    if not saved:
        dummy_image = np.zeros((512, 512, 3), dtype=np.uint8)
        dummy_image.fill(200)
        cv2.imwrite(output_path, dummy_image)

    relative_path = os.path.join("generated_images", image_filename)
    public_url = request.build_absolute_uri(settings.MEDIA_URL + relative_path)
    return public_url

def search_products_by_image(image_url, user_location):
    """
    يبحث عن منتجات مشابهة بصريًا باستخدام SerpApi Google Lens API.
    """
    print(f"البحث عن منتجات مشابهة للصورة: {image_url} في {user_location}")
    params = {
        "engine": "google_lens",
        "url": image_url,
        "api_key": SERPAPI_API_KEY,
        "hl": "ar",
        "gl": "us"
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    shopping_results = []
    if "shopping_results" in results:
        for item in results["shopping_results"]:
            shopping_results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "source": item.get("source"),
                "price": item.get("price"),
                "thumbnail": item.get("thumbnail"),
                "tag": item.get("tag")
            })

    return shopping_results

recommendations_cache = {}

def get_cached_recommendations(user_id, page_key):
    return recommendations_cache.get(f"{user_id}_{page_key}")

def set_cached_recommendations(user_id, page_key, data):
    recommendations_cache[f"{user_id}_{page_key}"] = data

def clear_user_cache(user_id):
    keys_to_delete = [key for key in recommendations_cache if key.startswith(f"{user_id}_")]
    for key in keys_to_delete:
        del recommendations_cache[key]

def analyze_user_and_generate_advanced_prompts(user, location_info, search_filters):
    """
    يحلل بيانات المستخدم، موقعه، وفلاتر البحث لتوليد أوصاف (prompts) دقيقة للملابس.
    """
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    filter_description = ", ".join([f"{k}: {v}" for k, v in search_filters.items()])

    analysis_prompt = f"""
    تحليل شامل للمستخدم وفلاتر البحث لتقديم توصيات أزياء دقيقة:

    **بيانات المستخدم:**
    - الطول: {user.height} سم
    - الوزن: {user.weight} كجم
    - لون البشرة: {user.skin_color}
    - الموقع الجغرافي: {location_info}

    **فلاتر البحث المطلوبة من المستخدم:**
    {filter_description}

    **المهمة:**
    1.  بناءً على بيانات المستخدم، قم بتحليل نوع الجسم ونظرية الألوان المناسبة للون بشرته.
    2.  دمج فلاتر البحث المطلوبة مع تحليل المستخدم لإنشاء 3 أوصاف نصية دقيقة ومفصلة (prompts) لتوليد صور لقطع ملابس واحدة (بدون عارض أزياء) تمثل هذه المتطلبات.
    3.  يجب أن تكون الأوصاف متنوعة قدر الإمكان ضمن الفلاتر المحددة، مع التركيز على الجودة والواقعية.

    **شروط وصف الصورة (Prompt):**
    - يجب أن يصف قطعة الملابس فقط (مثال: "قميص"، "بنطال"، "فستان").
    - يجب أن تكون الخلفية بسيطة ومحايدة (مثال: "خلفية استوديو رمادية فاتحة").
    - يجب أن تكون الصورة واقعية (photorealistic).
    - يجب تحديد ألوان وأنواع أقمشة دقيقة.
    - يجب أن تولد 3 أوصاف مختلفة لقطع ملابس مختلفة.

    **مثال على المخرجات المطلوبة (بتنسيق JSON):**
    {{
        "analysis": "المستخدم لديه بنية جسم متوسطة ويميل الطول. الألوان الدافئة مثل البيج والزيتي تناسب لون بشرته. موقعه في الرياض يقترح الحاجة لملابس صيفية خفيفة.",
        "prompts": [
            "صورة واقعية لبنطال تشينو رجالي بلون بيج، بقصة مستقيمة، مصنوع من القطن الخفيف، معروض على خلفية استوديو رمادية فاتحة.",
            "صورة واقعية لقميص بولو أبيض اللون، بقصة ضيقة (slim-fit)، مصنوع من قماش البيكيه، معروض على خلفية استوديو رمادية فاتحة.",
            "صورة واقعية لجاكيت خفيف (bomber jacket) بلون زيتي، مصنوع من النايلون، معروض على خلفية استوديو رمادية فاتحة."
        ]
    }}
    """

    response = model.generate_content(analysis_prompt)

    try:
        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        return cleaned_response
    except Exception as e:
        print(f"خطأ في تحليل استجابة Gemini للبحث المتقدم: {e}")
        return None
