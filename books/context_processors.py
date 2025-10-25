"""
Context processors for the books app
These functions add variables to the template context for all templates
"""

from .models import RequestBook


def pending_requests_count(request):
    """
    Add the count of pending book requests to the template context
    This allows us to show a notification badge in the header
    """
    if request.user.is_authenticated:
        # Count requests where user is the owner and decision hasn't been made yet
        count = RequestBook.objects.filter(
            owner=request.user,
            decision_datetime__isnull=True,
            cancelled_datetime__isnull=True
        ).count()
        return {'pending_requests_count': count}
    return {'pending_requests_count': 0}
