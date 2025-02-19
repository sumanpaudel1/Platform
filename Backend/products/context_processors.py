from .models import Cart

def cart_context(request):
    cart_count = 0
    if request.session.get('customer_id'):
        cart_count = Cart.objects.filter(customer_id=request.session['customer_id']).count()
    return {'cart_count': cart_count}