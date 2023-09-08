from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError

from oauth.models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm):
        model = CustomUser
        fields = ('username',)


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('username',)


class LoginForm(forms.Form):
    username = forms.CharField(max_length=128)
    password = forms.CharField(max_length=128)


class UserForm(forms.Form):
    username = forms.CharField(max_length=128, strip=True)
    password = forms.CharField(min_length=6, max_length=128, strip=True)

    def clean_username(self):
        if CustomUser.objects.filter(username=self.cleaned_data['username']):
            raise ValidationError('The Chosen Username is Not Available.')
        return self.cleaned_data['username']
