from rest_framework import generics, status
from rest_framework.response import Response
from .serializers import UserRegistrationSerializer
from .models import CustomUser
import cv2
import numpy as np
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os
import json
from .ai_services import (
    analyze_user_and_generate_prompts,
    generate_image_from_prompt,
    search_products_by_image,
    get_cached_recommendations,
    set_cached_recommendations,
    clear_user_cache,
    GEMINI_API_KEY
)
import google.generativeai as genai

# تهيئة Gemini باستخدام المفتاح القادم من البيئة إن توفر
try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        print("تحذير: GEMINI_API_KEY غير مضبوط في البيئة؛ بعض وظائف الذكاء قد تتعطل.")
except Exception as e:
    print(f"خطأ في تهيئة Gemini في views: {e}")

# عدد النتائج في كل صفحة
RESULTS_PER_PAGE = 5

class UserRegistrationView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class AnalyzeProfilePictureView(generics.GenericAPIView):
    def post(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user.profile_picture:
            return Response({"error": "Profile picture not found for this user"}, status=status.HTTP_400_BAD_REQUEST)

        image_path = user.profile_picture.path
        img = cv2.imread(image_path)

        if img is None:
            return Response({"error": "Could not load image"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        pixels = np.float32(img.reshape(-1, 3))
        n_colors = 1
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 200, 0.1)
        flags = cv2.KMEANS_RANDOM_CENTERS
        _, labels, palette = cv2.kmeans(pixels, n_colors, None, criteria, 10, flags)
        dominant_color_bgr = palette[0].astype(int)
        dominant_color_rgb = dominant_color_bgr[::-1]

        analysis_results = {
            "dominant_color_rgb": dominant_color_rgb.tolist(),
            "message": "Basic image analysis performed. More advanced AI analysis will be integrated later."
        }

        return Response(analysis_results, status=status.HTTP_200_OK)

class GetAIRecommendationsView(generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        user_id = request.query_params.get("user_id")
        page = int(request.query_params.get("page", 1))

        cached_data = get_cached_recommendations(user_id, page)
        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)
        
        # إذا لم يكن هناك بيانات مخزنة مؤقتًا، يمكننا إعادة توجيه الطلب إلى post() لإنشاء البيانات
        # ولكن لتجنب التعقيد، سنعيد رسالة خطأ أو سنسمح للواجهة الأمامية بإرسال POST إذا لم تجد بيانات
        return Response({"error": "No cached recommendations found. Please trigger generation via POST request."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        location_info = request.data.get("location", "Not provided")
        page = int(request.data.get("page", 1))

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        cached_data = get_cached_recommendations(user_id, page)
        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        ai_response_str = analyze_user_and_generate_prompts(user, location_info)
        if not ai_response_str:
            return Response({"error": "Failed to get analysis from AI model."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            ai_response_json = json.loads(ai_response_str)
            user_analysis_text = ai_response_json.get("analysis", "")
            prompts = ai_response_json.get("prompts", [])
        except json.JSONDecodeError:
            return Response({"error": "Failed to parse AI model response.", "raw_response": ai_response_str}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        all_recommendations = []

        for prompt in prompts:
            generated_image_url = generate_image_from_prompt(prompt, request)
            # generated_image_url هو الآن الرابط العام الذي يمكن لـ SerpAPI الوصول إليه
            shopping_results = search_products_by_image(generated_image_url, location_info)

            if shopping_results:
                format_prompt = f"""
                بناءً على تحليل المستخدم التالي: {user_analysis_text}
                وهذه قائمة بمنتجات التسوق التي تم العثور عليها: {json.dumps(shopping_results, ensure_ascii=False)}
                
                قم بصياغة {RESULTS_PER_PAGE} منشورات جذابة على طراز انستغرام. لكل منشور:
                - اختر منتجًا واحدًا من القائمة.
                - اكتب تعليقًا قصيرًا ومقنعًا يوضح لماذا هذا المنتج مناسب للمستخدم، مع الإشارة إلى صفاته الشخصية (مثل لون البشرة، نوع الجسم، الأسلوب المفضل).
                - يجب أن يتضمن المنشور رابط المنتج الأصلي (link) وصورة المنتج المصغرة (thumbnail).
                - يجب أن تكون المخرجات بتنسيق JSON.
                
                مثال على المخرجات المطلوبة:
                {{
                    "posts": [
                        {{
                            "text": "وجدنا لك هذا! قميص أزرق أنيق من متجر X. قصته الضيقة ستبرز بنيتك الرياضية، ولونه يتناغم مع بشرتك. مثالي لإطلالة صيفية.",
                            "product_link": "https://example.com/product1",
                            "image_url": "https://example.com/thumb1.jpg"
                        }}
                    ]
                }}
                """
                
                format_model = genai.GenerativeModel("gemini-1.5-flash")
                formatted_response = format_model.generate_content(format_prompt)
                
                try:
                    cleaned_formatted_response = formatted_response.text.replace("```json", "").replace("```", "").strip()
                    formatted_posts = json.loads(cleaned_formatted_response).get("posts", [])
                    all_recommendations.extend(formatted_posts)
                except json.JSONDecodeError as e:
                    print(f"خطأ في تحليل استجابة Gemini لتنسيق المنشورات: {e}")
                    all_recommendations.append({"error": "Failed to format posts", "raw_results": shopping_results})
            else:
                all_recommendations.append({"message": "No shopping results found for this image.", "prompt": prompt})

        total_results = len(all_recommendations)
        total_pages = (total_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE

        paginated_results = []
        for i in range(total_pages):
            start_index = i * RESULTS_PER_PAGE
            end_index = min((i + 1) * RESULTS_PER_PAGE, total_results)
            page_data = {
                "user_analysis": user_analysis_text,
                "recommendations": all_recommendations[start_index:end_index],
                "current_page": i + 1,
                "total_pages": total_pages,
                "has_next_page": (i + 1) < total_pages
            }
            set_cached_recommendations(user_id, i + 1, page_data)
            if (i + 1) == page:
                paginated_results = page_data

        if not paginated_results and page > total_pages:
            return Response({
                "user_analysis": user_analysis_text,
                "recommendations": [],
                "current_page": page,
                "total_pages": total_pages,
                "has_next_page": False
            }, status=status.HTTP_200_OK)

        return Response(paginated_results, status=status.HTTP_200_OK)


class AdvancedSearchView(generics.GenericAPIView):
    def post(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        location_info = request.data.get("location", "Not provided")
        search_filters = request.data.get("filters", {})
        page = int(request.data.get("page", 1))

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        cache_key_suffix = f"advanced_search_{hash(json.dumps(search_filters, sort_keys=True))}"
        cached_data = get_cached_recommendations(user_id, f"{cache_key_suffix}_{page}")
        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        from .ai_services import analyze_user_and_generate_advanced_prompts
        ai_response_str = analyze_user_and_generate_advanced_prompts(user, location_info, search_filters)
        if not ai_response_str:
            return Response({"error": "Failed to get analysis from AI model for advanced search."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            ai_response_json = json.loads(ai_response_str)
            user_analysis_text = ai_response_json.get("analysis", "")
            prompts = ai_response_json.get("prompts", [])
        except json.JSONDecodeError:
            return Response({"error": "Failed to parse AI model response for advanced search.", "raw_response": ai_response_str}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        all_recommendations = []

        for prompt in prompts:
            generated_image_url = generate_image_from_prompt(prompt, request)
            # generated_image_url هو الآن الرابط العام الذي يمكن لـ SerpAPI الوصول إليه
            shopping_results = search_products_by_image(generated_image_url, location_info)

            if shopping_results:
                format_prompt = f"""
                بناءً على تحليل المستخدم التالي: {user_analysis_text}
                وفلاتر البحث المحددة: {json.dumps(search_filters, ensure_ascii=False)}
                وهذه قائمة بمنتجات التسوق التي تم العثور عليها: {json.dumps(shopping_results, ensure_ascii=False)}
                
                قم بصياغة {RESULTS_PER_PAGE} منشورات جذابة على طراز انستغرام. لكل منشور:
                - اختر منتجًا واحدًا من القائمة.
                - اكتب تعليقًا قصيرًا ومقنعًا يوضح لماذا هذا المنتج مناسب للمستخدم، مع الإشارة إلى صفاته الشخصية (مثل لون البشرة، نوع الجسم، الأسلوب المفضل) والفلاتر التي اختارها.
                - يجب أن يتضمن المنشور رابط المنتج الأصلي (link) وصورة المنتج المصغرة (thumbnail).
                - يجب أن تكون المخرجات بتنسيق JSON.
                
                مثال على المخرجات المطلوبة:
                {{
                    "posts": [
                        {{
                            "text": "وجدنا لك هذا! قميص أزرق أنيق من متجر X. قصته الضيقة ستبرز بنيتك الرياضية، ولونه يتناغم مع بشرتك. مثالي لإطلالة صيفية.",
                            "product_link": "https://example.com/product1",
                            "image_url": "https://example.com/thumb1.jpg"
                        }}
                    ]
                }}
                """
                
                format_model = genai.GenerativeModel("gemini-1.5-flash")
                formatted_response = format_model.generate_content(format_prompt)
                
                try:
                    cleaned_formatted_response = formatted_response.text.replace("```json", "").replace("```", "").strip()
                    formatted_posts = json.loads(cleaned_formatted_response).get("posts", [])
                    all_recommendations.extend(formatted_posts)
                except json.JSONDecodeError as e:
                    print(f"خطأ في تحليل استجابة Gemini لتنسيق المنشورات للبحث المتقدم: {e}")
                    all_recommendations.append({"error": "Failed to format posts", "raw_results": shopping_results})
            else:
                all_recommendations.append({"message": "No shopping results found for this image.", "prompt": prompt})

        total_results = len(all_recommendations)
        total_pages = (total_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE

        paginated_results = []
        for i in range(total_pages):
            start_index = i * RESULTS_PER_PAGE
            end_index = min((i + 1) * RESULTS_PER_PAGE, total_results)
            page_data = {
                "user_analysis": user_analysis_text,
                "recommendations": all_recommendations[start_index:end_index],
                "current_page": i + 1,
                "total_pages": total_pages,
                "has_next_page": (i + 1) < total_pages
            }
            set_cached_recommendations(user_id, f"{cache_key_suffix}_{i + 1}", page_data)
            if (i + 1) == page:
                paginated_results = page_data

        if not paginated_results and page > total_pages:
            return Response({
                "user_analysis": user_analysis_text,
                "recommendations": [],
                "current_page": page,
                "total_pages": total_pages,
                "has_next_page": False
            }, status=status.HTTP_200_OK)

        return Response(paginated_results, status=status.HTTP_200_OK)

