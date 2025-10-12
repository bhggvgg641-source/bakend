import google.generativeai as genai
import os
import json
import cv2
import numpy as np
from serpapi import GoogleSearch

GEMINI_API_KEY = "AIzaSyA1xcMptfYKSHpaeadGpUm729DYyNu7e5w"
SERPAPI_API_KEY = "97a8e4289031baed5d3d886e1466ee6d5eb23b1979bd321910dc19bed6e612ba"

genai.configure(api_key=GEMINI_API_KEY)

def analyze_user_and_generate_prompts(user, location_info):
    """
    يحلل بيانات المستخدم وصورته الشخصية لتوليد أوصاف (prompts) دقيقة للملابس.
    """
    model = genai.GenerativeModel(model_name="gemini-2.5-flash")

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

def generate_image_from_prompt(prompt):
    """
    يستخدم نموذج توليد الصور من جوجل لإنشاء صورة من وصف نصي.
    """
    print(f"محاكاة توليد صورة للوصف: {prompt}")
    
    placeholder_image_dir = "/home/ubuntu/fashion_ai_backend/media/generated_images/"
    os.makedirs(placeholder_image_dir, exist_ok=True)
    placeholder_image_path = os.path.join(placeholder_image_dir, f"generated_image_{hash(prompt)}.jpg")

    if not os.path.exists(placeholder_image_path):
        dummy_image = np.zeros((512, 512, 3), dtype=np.uint8)
        dummy_image.fill(200)
        cv2.imwrite(placeholder_image_path, dummy_image)

    return placeholder_image_path

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
    model = genai.GenerativeModel(model_name="gemini-2.5-flash")

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

