from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class RechiroSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Keep OAuth authentication intact and only request role choice
    immediately after first successful Google sign-in.
    """

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        if sociallogin.account.provider == "google" and not sociallogin.is_existing:
            # Force post-auth role selection flow for new Google users.
            user.role = ""
            user.save(update_fields=["role"])
            request.session["needs_role_selection"] = True
        return user
