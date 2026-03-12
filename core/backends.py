from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q

class EmailOrUsernameBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in using either 
    their username or their email address.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Check for user with either username or email
            user = User.objects.get(Q(username=username) | Q(email=username))
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        return None
