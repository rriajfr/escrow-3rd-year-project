from django.core import signing
from .models import User

COOKIE_NAME = 'escrow_accounts'
COOKIE_SALT = 'multi-account-switcher'


def switchable_accounts(request):
    """Makes a list of other logged-in accounts available in every template."""
    if not request.user.is_authenticated:
        return {'switchable_accounts': []}
    
    raw = request.COOKIES.get(COOKIE_NAME, '')
    try:
        ids = signing.loads(raw, salt=COOKIE_SALT) if raw else []
        if not isinstance(ids, list):
            ids = []
    except Exception:
        ids = []
    
    other_ids = [uid for uid in ids if uid != request.user.id]
    users = User.objects.filter(id__in=other_ids)
    return {'switchable_accounts': users}