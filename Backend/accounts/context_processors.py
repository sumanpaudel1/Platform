def notifications_context(request):
    """Context processor for notifications"""
    context = {
        'notifications': [],
        'unread_notifications_count': 0
    }
    
    # Check if user is authenticated and is a vendor
    if request.user.is_authenticated and hasattr(request.user, 'is_vendor'):
        try:
            from accounts.models import Notification
            
            # Get notifications for this vendor
            notifications = Notification.objects.filter(
                vendor=request.user
            ).order_by('-created_at')[:15]
            
            # Get unread count
            unread_count = Notification.objects.filter(
                vendor=request.user,
                is_read=False
            ).count()
            
            # Update context
            context['notifications'] = notifications
            context['unread_notifications_count'] = unread_count
                
        except Exception as e:
            print(f"Error in notifications context processor: {str(e)}")
    
    # Return the context dictionary
    return context