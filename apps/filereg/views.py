from rest_framework import permissions, viewsets

from api.authentication import RestSharedSecretAuthentication

from filereg.models import NonAMOAddon, Hash
from filereg.serializers import NonAMOAddonSerializer, HashSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Custom permission to only allow the authors of an addon to edit it."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        # Only check the authors if they are registered.
        if type(obj) == Hash:
            obj = obj.addon

        if obj.authors.count() > 0:
            return obj.authors.filter(user__id=request.user.id).count() == 1

        # If we have no authors, we have the right to edit the item.
        return True


class NonAMOAddonViewSet(viewsets.ModelViewSet):
    """ Viewset to add / edit / delete non-amo addons.  """
    serializer_class = NonAMOAddonSerializer
    permission_classes = [IsOwnerOrReadOnly]
    authentication = RestSharedSecretAuthentication
    model = NonAMOAddon

    def post_save(self, obj, created):
        obj.authors.add(self.request.user.get_profile())


class HashViewSet(viewsets.ModelViewSet):
    """Viewset to manage hashes"""
    serializer_class = HashSerializer
    permission_classes = [IsOwnerOrReadOnly]
    authentication = RestSharedSecretAuthentication
    model = Hash
