from django.urls import path
from .views import UserRegistrationView, AnalyzeProfilePictureView, GetAIRecommendationsView, AdvancedSearchView

urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("analyze-profile-picture/", AnalyzeProfilePictureView.as_view(), name="analyze_profile_picture"),
    path("recommendations/", GetAIRecommendationsView.as_view(), name="get_recommendations"),
    path("advanced-search/", AdvancedSearchView.as_view(), name="advanced_search"),
]

