import hashlib
import hmac
from functools import partial

import commonware.log
import jingo
from piston.authentication.oauth import OAuthAuthentication, views
from rest_framework.authentication import BaseAuthentication

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from access.middleware import ACLMiddleware
from users.models import UserProfile
from zadmin import jinja_for_django

# This allows the views in piston.authentication.oauth to cope with
# Jinja2 templates as opposed to Django templates.
# Piston view passes: template, context, request_context
jfd = lambda a, b, c: jinja_for_django(a, b, context_instance=c)
views.render_to_response = jfd


log = commonware.log.getLogger('z.api')


class AMOOAuthAuthentication(OAuthAuthentication):
    """^^^MOO!!!  Adds amo_user to the request object."""

    def is_authenticated(self, request):
        if request.user and request.user.is_authenticated():
            return True

        # To avoid patching django-piston, use a partial to cope with
        # piston not sending in request when called later.
        self.challenge = partial(self._challenge, request=request)

        # Authenticate the user using Piston, rv will be True or False
        # depending upon how it went.
        rv = super(AMOOAuthAuthentication, self).is_authenticated(request)

        if rv and request.user:
            # The user is there, but we need to alter the user to be
            # a user specified in the request. Specifically chose this
            # term to avoid conflict with user, which could be used elsewhere.
            if self.two_legged and 'authenticate_as' in request.REQUEST:
                pk = request.REQUEST.get('authenticate_as')
                try:
                    profile = UserProfile.objects.get(pk=pk)
                except UserProfile.DoesNotExist:
                    log.warning('Cannot find user: %s' % pk)
                    return False

                if profile.deleted or profile.confirmationcode:
                    log.warning('Tried to use deleted or unconfirmed user: %s'
                                % pk)
                    return False

                log.info('Authenticating as: %s' % pk)
                request.user = profile.user

            # If that worked and request.user got set, setup AMO specific bits.
            ACLMiddleware().process_request(request)
        else:
            # The piston middleware could find a consumer, but no
            # user on that consumer. If it does it returns True, but
            # request.user is None, which then blows up other things.
            request.user = AnonymousUser()
            return False

        return rv

    def _challenge(self, request):
        response = jingo.render(request, 'piston/oauth/challenge.html',
                                status=401)
        response['WWW-Authenticate'] = 'OAuth realm="API"'
        return response


class RestOAuthAuthentication(AMOOAuthAuthentication):
    """Open Authentication suitable for DRF"""

    def authenticate(self, request):
        result = self.is_authenticated(request)

        if not (result and request.user):
            return None
        return (request.user, None)


class RestSharedSecretAuthentication(BaseAuthentication):
    """SharedSecretAuthentication suitable for DRF."""

    def is_authenticated(self, request):
        auth = request.GET.get('_user')
        if not auth:
            log.info('API request made without shared-secret auth token')
            return False
        try:
            email, hm, unique_id = str(auth).split(',')
            consumer_id = hashlib.sha1(
                email + settings.SECRET_KEY).hexdigest()
            matches = hmac.new(unique_id + settings.SECRET_KEY,
                               consumer_id, hashlib.sha512).hexdigest() == hm
            if matches:
                try:
                    request.amo_user = UserProfile.objects.select_related(
                        'user').get(email=email)
                    request.user = request.amo_user.user
                except UserProfile.DoesNotExist:
                    log.info('Auth token matches absent user (%s)' % email)
                    return False
                ACLMiddleware().process_request(request)
            else:
                log.info('Shared-secret auth token does not match')
                return False

            log.info('Successful SharedSecret with user: %s' % request.user.pk)
            return matches
        except Exception, e:
            log.info('Bad shared-secret auth data: %s (%s)', auth, e)
            return False

    def authenticate(self, request):
        result = self.is_authenticated(request)

        if not (result and request.user):
            return None
        return (request.user, None)
