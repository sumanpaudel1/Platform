from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Vendor, VendorProfile, VendorSetting


class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',  # Explicitly setting label for password
        widget=forms.PasswordInput(attrs={
            'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',  # Changed label for password2
        widget=forms.PasswordInput(attrs={
            'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Confirm password'
        })
    )

    class Meta:
        model = Vendor
        fields = ['first_name', 'last_name', 'middle_name', 'email', 'phone_number']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter last name'
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter middle name (optional)'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter email address'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter phone number'
            }),
        }


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'appearance-none block w-full pl-10 pr-3 py-3 border border-gray-200 rounded-xl shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-500 transition-all',
            'placeholder': 'Enter your email',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'appearance-none block w-full pl-10 pr-3 py-3 border border-gray-200 rounded-xl shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-500 transition-all',
            'placeholder': '••••••••',
        })
    )
    
    



from django import forms
from .models import VendorProfile
class VendorProfileForm(forms.ModelForm):
    class Meta:
        model = VendorProfile
        exclude = ['vendor', 'profile_status', 'is_verified', 'verification_date', 'verified_by']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'gender': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'business_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'business_type': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'pan_vat_number': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'registration_number': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'street_address': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'city': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'state': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'country': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'alternate_phone': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'alternate_email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'citizenship_number': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'profile_photo': forms.FileInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'pan_vat_document': forms.FileInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'business_registration': forms.FileInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'citizenship_front': forms.FileInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            }),
            'citizenship_back': forms.FileInput(attrs={
                'class': 'mt-1 block w-full rounded-md bg-gray-50 border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
            })
        }
        
        
        


class VendorSettingForm(forms.ModelForm):
    class Meta:
        model = VendorSetting
        exclude = ['vendor', 'is_profile_complete', 'profile_completion_date', 
                  'subdomain_request_date', 'subdomain_approval_date']
        widgets = {
            'logo': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'favicon': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'store_name': forms.TextInput(attrs={'class': 'form-input'}),
            'tagline': forms.TextInput(attrs={'class': 'form-input'}),
            'about': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'announcement': forms.TextInput(attrs={'class': 'form-input'}),
            'primary_color': forms.TextInput(attrs={'type': 'color', 'class': 'h-10 w-full'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color', 'class': 'h-10 w-full'}),
            'accent_color': forms.TextInput(attrs={'type': 'color', 'class': 'h-10 w-full'}),
            'heading_font': forms.Select(attrs={'class': 'form-input'}),
            'body_font': forms.Select(attrs={'class': 'form-input'}),
            'facebook': forms.URLInput(attrs={'class': 'form-input'}),
            'instagram': forms.URLInput(attrs={'class': 'form-input'}),
            'twitter': forms.URLInput(attrs={'class': 'form-input'}),
            'meta_title': forms.TextInput(attrs={'class': 'form-input'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-input'}),
            'contact_address': forms.TextInput(attrs={'class': 'form-input'}),
            'popup_title': forms.TextInput(attrs={'class': 'form-input'}),
            'popup_text': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'popup_delay': forms.NumberInput(attrs={'class': 'form-input'}),
        }