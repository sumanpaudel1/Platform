from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'stock']
        
        
        
        
from django import forms
from .models import Review, ReviewImage
from django.forms.widgets import ClearableFileInput

class MultiFileInput(ClearableFileInput):
    allow_multiple_selected = True


class ReviewForm(forms.ModelForm):
    images = forms.FileField(
        # ← switch to our MultiFileInput
        widget=MultiFileInput(attrs={"multiple": True}),
        required=False
    )
    class Meta:
        model = Review
        fields = ["rating", "comment", "is_anonymous"]

    def save(self, customer, product, order, *args, **kwargs):
        rev = super().save(commit=False)
        rev.customer = customer
        rev.product  = product
        rev.order    = order
        rev.save()
        for f in self.files.getlist("images"):
            ReviewImage.objects.create(review=rev, image=f)
        return rev