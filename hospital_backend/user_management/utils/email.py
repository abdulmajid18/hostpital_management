import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


def send_email(subject, recipient_list, context, template_name):
    """
    Sends an email with HTML and plain text alternatives.
    Returns True if the email was sent successfully, False otherwise.
    """
    html_message = render_to_string(f"email/{template_name}.html", context)
    plain_message = render_to_string(f"email/{template_name}.txt", context)
    from_email = (
            settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL
    )  # Fallback if EMAIL_HOST_USER is not set

    email = EmailMultiAlternatives(subject, plain_message, from_email, recipient_list)
    email.attach_alternative(html_message, "text/html")

    try:
        result = email.send()
        if result == 0:
            logger.warning(f"Email not sent to: {recipient_list}")
            return False
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_list}: {str(e)}")
        return False

    return True


def build_confirmation_link(request, user):
    """
    Build the activation link for user account confirmation.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    path = reverse(
        "user_management:confirm_account", kwargs={"uid": uidb64, "token": token}
    )
    return request.build_absolute_uri(path)


def send_activation_email(request, user):
    activation_link = build_confirmation_link(request, user)
    print("link", activation_link)
    context = {"activation_link": activation_link}
    status = send_email(
        subject="Activate Your Account",
        recipient_list=[user.email],
        context=context,
        template_name="account_activation",
    )
    return status
