from .models import Cart

def cart_context(request):
    cart_count = 0
    if request.session.get('customer_id'):
        cart_count = Cart.objects.filter(customer_id=request.session['customer_id']).count()
    return {'cart_count': cart_count}



from .models import Cart, Wishlist

def cart_and_wishlist_counts(request):
    """Context processor to provide cart and wishlist counts."""
    cart_count = 0
    wishlist_count = 0
    
    if request.session.get('customer_id'):
        customer_id = request.session['customer_id']
        cart_count = Cart.objects.filter(customer_id=customer_id).count()
        wishlist_count = Wishlist.objects.filter(customer_id=customer_id).count()
    
    return {
        'cart_count': cart_count,
        'wishlist_count': wishlist_count
    }