from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    work_email = serializers.EmailField()
    department = serializers.CharField(max_length=100, allow_blank=True, required=False, default="")
    password = serializers.CharField(write_only=True)

    def validate_work_email(self, value: str) -> str:
        if User.objects.filter(work_email=value.lower()).exists():
            raise serializers.ValidationError("An account already exists with this email.")
        return value.lower()

    def validate(self, attrs):
        validate_password(attrs["password"], User(**{k: v for k, v in attrs.items() if k != "password"}))
        return attrs


class EmailSerializer(serializers.Serializer):
    work_email = serializers.EmailField()


class OTPVerifySerializer(EmailSerializer):
    code = serializers.RegexField(r"^\s*\d{6}\s*$")


class LoginSerializer(EmailSerializer):
    password = serializers.CharField(write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField()


class RoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)


class EmployeeNumberSerializer(serializers.Serializer):
    employee_number = serializers.CharField(max_length=40)


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "work_email",
            "employee_number",
            "department",
            "role",
            "status",
            "preferred_language",
            "must_change_password",
            "evening_reminder",
            "created_at",
        ]
        read_only_fields = fields
