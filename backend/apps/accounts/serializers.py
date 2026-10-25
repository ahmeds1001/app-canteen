from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import EmployeeRoster, User


class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    work_email = serializers.EmailField()
    employee_number = serializers.CharField(max_length=40)
    department = serializers.CharField(max_length=100, allow_blank=True, required=False, default="")
    password = serializers.CharField(write_only=True)

    def validate_work_email(self, value: str) -> str:
        if User.objects.filter(work_email=value.lower()).exists():
            raise serializers.ValidationError("An account already exists with this email.")
        return value.lower()

    def validate_employee_number(self, value: str) -> str:
        if User.objects.filter(employee_number=value).exists():
            raise serializers.ValidationError("An account already exists with this employee number.")
        return value

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


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    on_roster = serializers.SerializerMethodField()

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
            "on_roster",
        ]
        read_only_fields = fields

    def get_on_roster(self, obj: User) -> bool | None:
        roster = self.context.get("roster_numbers")
        return None if roster is None else obj.employee_number in roster


class RosterRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeRoster
        fields = ["employee_number", "full_name", "department"]
