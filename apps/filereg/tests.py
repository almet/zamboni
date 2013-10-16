import urllib

from django.conf import settings
from django.contrib.auth.models import User

import mock
from nose.tools import ok_, eq_
from rest_framework.test import APIClient

from amo.urlresolvers import reverse
from amo.tests import TestCase
from apps.filereg.views import IsOwnerOrReadOnly
from apps.filereg.models import NonAMOAddon, Hash
from apps.filereg.serializers import (NonAMOAddonSerializer,
                                      AddonHashSerializer,
                                      HashSerializer)
from users.models import UserProfile


@mock.patch.object(settings, 'SECRET_KEY', 'gubbish')
class FileRegistrationAPITest(TestCase):

    def setUp(self):
        self.guid = u'{9c51bd27-6ed8-4000-a2bf-36cb95c0c947}'
        self.name = u'Super Addon'
        self.description = u'Some super description'
        self.sha256 = (u'31f7a65e315586ac198bd798b6629ce4903d0899476d5741a9f32'
                       'e2e521b6a66')

        self._email = 'cfinke@m.com'
        self._auth = (self._email + ',56b6f1a3dd735d962c56'
                      'ce7d8f46e02ec1d4748d2c00c407d75f0969d08bb'
                      '9c68c31b3371aa8130317815c89e5072e31bb94b4'
                      '121c5c165f3515838d4d6c60c4,165d631d3c3045'
                      '458b4516242dad7ae')

        auth_qs = '?_user=%s' % self._auth

        self.hash_list_url = reverse('nonamo-hash-list') + auth_qs
        self.hash_detail_url = reverse('nonamo-hash-detail',
                                       kwargs={'pk': self.sha256}) + auth_qs
        self.addon_detail_url = reverse('nonamo-addon-detail',
                                        kwargs={'pk': self.guid}) + auth_qs

        self.client = APIClient()

        self._to_clean = []

    def tearDown(self):
        # Be sure to delete objects we created after running the test.
        for obj in self._to_clean:
            obj.delete()

    def _create_user(self):
        user = User.objects.create_user('cfinke', self._email, 'P455W0rD')
        profile = UserProfile(email=self._email, user=user)
        profile.update(email=profile.user.email)
        profile.save()

        self.user = user
        self._to_clean.append(user)
        return self.user

    def _create_addon(self, hashes=False):
        """Creates an addon and returns it.

        Used as a conveniance method by the tests.
        """
        addon = NonAMOAddon.objects.create(
            guid=self.guid, name=self.name, description=self.description)
        if hashes:
            obj = Hash(addon=addon, sha256=self.sha256, version='1.0',
                       registered=True)
            obj.save()
        self._to_clean.append(addon)
        return addon

    def test_hash_serialization(self):
        addon = NonAMOAddon(guid=self.guid)
        obj = Hash(addon=addon, sha256=self.sha256, version='1.0',
                   registered=True)
        serializer = HashSerializer(obj)
        expected = {'sha256': self.sha256,
                    'addon': self.guid,
                    'version': u'1.0',
                    'registered': True}

        eq_(serializer.data, expected)

    def test_addon_hash_serialization(self):
        addon = NonAMOAddon()
        obj = Hash(addon=addon, sha256=self.sha256, version='1.0',
                   registered=True)
        serializer = AddonHashSerializer(obj)
        eq_(serializer.data, {'sha256': self.sha256})

    def test_addon_hash_deserialization(self):
        serializer = AddonHashSerializer(data={'sha256': self.sha256})
        ok_(serializer.is_valid())

    def test_addon_serialization(self):
        # Test that we are able to represent an already existing addon, with
        # its hashes.
        obj = NonAMOAddon.objects.create(
            guid=self.guid, name=self.name, description=self.description)
        self._to_clean.append(obj)
        obj.hashes.create(sha256=self.sha256)
        serializer = NonAMOAddonSerializer(obj)
        self.assertDictEqual(serializer.data, {
            'guid': self.guid, 'name': self.name,
            'description': self.description,
            'hashes': [{'sha256': self.sha256}], 'authors': []})

    def test_addon_validation(self):
        # Test we know how to convert a dict back to an object.
        data = {'guid': self.guid, 'name': self.name,
                'description': self.description,
                'hashes': [{'sha256': self.sha256}], 'authors': []}

        serializer = NonAMOAddonSerializer(data=data)
        ok_(serializer.is_valid())

    def test_addon_metadata_update(self):
        # It should be possible to register the metadata about an addon as
        # a later step, by doing a PUT / PATCH.
        self._create_user()
        self._create_addon(hashes=False)

        data = {'name': 'Youpi', 'description': 'Oh yeah'}
        resp = self.client.patch(self.addon_detail_url, data, format='json')

        eq_(resp.status_code, 200, resp.content)

        addon = NonAMOAddon.objects.get(guid=self.guid)
        eq_(addon.name, data['name'])
        eq_(addon.description, data['description'])

    def test_unregister_hash(self):
        self._create_user()
        self._create_addon()

        data = {'hashes': []}
        resp = self.client.patch(self.addon_detail_url, data, format='json')

        eq_(resp.status_code, 200, resp.content)

        addon = NonAMOAddon.objects.get(guid=self.guid)
        eq_(addon.hashes.count(), 0)

    def test_addon_creation_with_hash_works(self):
        self._create_user()
        # A single call to the PUT API should create a new addon and register
        # a new hash to it.

        # Note that we're only defining the guid + hashes here (no name,
        # description etc. since they're not mandatory)
        data = {'guid': self.guid, 'hashes': [{'sha256': self.sha256}]}
        url = reverse('nonamo-addon-detail', kwargs={'pk': self.guid})
        url += '?' + urllib.urlencode({'_user': self._auth})
        resp = self.client.put(url, data, format='json')

        eq_(resp.status_code, 201)

        # The addon was created successfully
        addon = NonAMOAddon.objects.get(guid=self.guid)
        self._to_clean.append(addon)
        eq_(addon.hashes.count(), 1)
        eq_(addon.authors.count(), 1)

    def test_addon_creation_without_hash(self):
        # A call to the PUT API without hash information should just register
        # the addon and let it possible to register the hash as a second step.
        self._create_user()

        # Note that we're only defining the guid + hashes here (no name,
        # description etc. since they're not mandatory)
        data = {'guid': self.guid}
        resp = self.client.put(self.addon_detail_url, data, format='json')

        eq_(resp.status_code, 201, resp.content)

        # The addon was created successfully
        addon = NonAMOAddon.objects.get(guid=self.guid)
        eq_(addon.hashes.count(), 0)
        eq_(addon.authors.count(), 1)

    def test_hash_addition(self):
        self._create_user()
        self._create_addon(hashes=False)

        # Create an addon and check that it's possible to add some hashes to
        # it.
        data = {'hashes': [{'sha256': self.sha256}]}
        resp = self.client.patch(self.addon_detail_url, data, format='json')

        eq_(resp.status_code, 200, resp.content)

        addon = NonAMOAddon.objects.get(guid=self.guid)
        eq_(addon.hashes.count(), 1)

    def test_hash_api_post(self):
        self._create_user()
        self._create_addon(hashes=False)

        # Create an addon and check that it's possible to add some hashes to
        # it.
        data = {'sha256': self.sha256, 'addon': self.guid}
        resp = self.client.post(self.hash_list_url, data, format='json')

        eq_(resp.status_code, 201, resp.content)

        addon = NonAMOAddon.objects.get(guid=self.guid)
        eq_(addon.hashes.count(), 1)

    def test_hash_api_put(self):
        self._create_user()
        self._create_addon(hashes=False)

        data = {'sha256': self.sha256, 'addon': self.guid}
        resp = self.client.put(self.hash_detail_url, data, format='json')

        eq_(resp.status_code, 201, resp.content)

        addon = NonAMOAddon.objects.get(guid=self.guid)
        eq_(addon.hashes.count(), 1)

    def test_update_hash_api(self):
        self._create_user()
        self._create_addon(hashes=True)

        data = {'registered': False}
        resp = self.client.patch(self.hash_detail_url, data, format='json')

        eq_(resp.status_code, 200, resp.content)

        addon = NonAMOAddon.objects.get(guid=self.guid)
        eq_(addon.hashes.filter(registered=False).count(), 1)

    def test_permission_works_for_safe_methods(self):
        auth = IsOwnerOrReadOnly()
        request = mock.MagicMock()
        request.method = 'GET'
        eq_(auth.has_object_permission(request, None, None), True)

    def test_permission_on_hashes(self):
        user = self._create_user()

        auth = IsOwnerOrReadOnly()
        request = mock.MagicMock()
        request.method = 'POST'
        request.user.id = user.id

        addon = NonAMOAddon(guid=self.guid)
        addon.save()
        addon.authors.add(user.get_profile())

        obj = Hash(addon=addon, sha256=self.sha256, version='1.0',
                   registered=True)
        obj.save()
        eq_(auth.has_object_permission(request, None, obj), True)

        request.user.id = user.id + 1
        eq_(auth.has_object_permission(request, None, obj), False)

    def test_permission_on_addon(self):
        user = self._create_user()

        auth = IsOwnerOrReadOnly()
        request = mock.MagicMock()
        request.method = 'POST'
        request.user.id = user.id

        addon = NonAMOAddon(guid=self.guid)
        addon.save()
        addon.authors.add(user.get_profile())
        eq_(auth.has_object_permission(request, None, addon), True)

    def test_permission_no_authors(self):
        auth = IsOwnerOrReadOnly()
        request = mock.MagicMock()
        request.method = 'POST'
        request.user.id = 1

        addon = NonAMOAddon(guid=self.guid)
        eq_(auth.has_object_permission(request, None, addon), True)
