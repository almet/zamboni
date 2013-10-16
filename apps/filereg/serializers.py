from rest_framework import serializers
from filereg.models import NonAMOAddon, Hash


class HashSerializer(serializers.ModelSerializer):
    """Hash serializer exposing all the fields that could be edited.
    """
    addon = serializers.SlugRelatedField(slug_field='guid')

    class Meta:
        model = Hash
        fields = ('sha256', 'addon', 'version', 'registered')

    def get_identity(self, data):
        return data.get('sha256')


class AddonHashSerializer(serializers.ModelSerializer):
    """Hash serializer exposing the sha256 field only.

    This is to be used when interacting with the main Addon serializer.
    """
    sha256 = serializers.CharField()

    class Meta:
        model = Hash
        fields = ('sha256',)


class NonAMOAddonSerializer(serializers.ModelSerializer):
    guid = serializers.CharField()
    hashes = AddonHashSerializer(source='hashes', many=True, required=False,
                                 allow_add_remove=True)
    authors = serializers.RelatedField(many=True, read_only=True)
    name = serializers.CharField(required=False)
    description = serializers.CharField(required=False)

    class Meta:
        model = NonAMOAddon
        fields = ('guid', 'name', 'description', 'hashes', 'authors')

    def get_identity(self, data):
        return data.get('guid')
