from rest_framework import serializers
from .models import CustomUser

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = (
            'username', 'email', 'password', 'height', 'weight', 'skin_color', 'profile_picture',
            'age', 'gender', 'body_type', 'style_preference', 'budget'
        )

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            height=validated_data.get('height'),
            weight=validated_data.get('weight'),
            skin_color=validated_data.get('skin_color'),
            profile_picture=validated_data.get('profile_picture'),
            age=validated_data.get('age'),
            gender=validated_data.get('gender'),
            body_type=validated_data.get('body_type'),
            style_preference=validated_data.get('style_preference'),
            budget=validated_data.get('budget')
        )
        return user

