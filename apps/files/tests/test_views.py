import json
import os
import shutil
import tempfile
import urlparse

from django.conf import settings
from django.core.cache import cache
from django.utils.encoding import iri_to_uri

from mock import patch_object
from nose.tools import eq_
from pyquery import PyQuery as pq
import test_utils

from amo.utils import Message
from amo.urlresolvers import reverse
from addons.models import Addon
from files.helpers import FileViewer, DiffHelper
from files.models import File
from users.models import UserProfile

dictionary = 'apps/files/fixtures/files/dictionary-test.xpi'
unicode_filenames = 'apps/files/fixtures/files/unicode-filenames.xpi'
not_binary = 'install.js'
binary = 'dictionaries/ar.dic'


class FilesBase:

    def login_as_editor(self):
        assert self.client.login(username='editor@mozilla.com',
                                 password='password')

    def setUp(self):
        self.addon = Addon.objects.get(pk=3615)
        self.dev = self.addon.authors.all()[0]
        self.regular = UserProfile.objects.get(pk=999)
        self.version = self.addon.versions.latest()
        self.file = self.version.all_files[0]

        self.file_two = File()
        self.file_two.version = self.version
        self.file_two.filename = 'dictionary-test.xpi'
        self.file_two.save()

        self.login_as_editor()

        self.old_tmp = settings.TMP_PATH
        self.old_addon = settings.ADDONS_PATH
        settings.TMP_PATH = tempfile.mkdtemp()
        settings.ADDONS_PATH = tempfile.mkdtemp()

        for file_obj in [self.file, self.file_two]:
            src = os.path.join(settings.ROOT, dictionary)
            try:
                os.makedirs(os.path.dirname(file_obj.file_path))
            except OSError:
                pass
            shutil.copyfile(src, file_obj.file_path)

        self.file_viewer = FileViewer(self.file)

    def tearDown(self):
        self.file_viewer.cleanup()
        settings.TMP_PATH = self.old_tmp
        settings.ADDONS_PATH = self.old_addon

    def files_redirect(self, file):
        return reverse('files.redirect', args=[self.file.pk, file])

    def files_serve(self, file):
        return reverse('files.serve', args=[self.file.pk, file])

    def test_view_access_anon(self):
        self.client.logout()
        self.check_urls(403)

    def test_view_access_anon_view_source(self):
        self.addon.update(view_source=True)
        self.file_viewer.extract()
        self.client.logout()
        self.check_urls(200)

    def test_view_access_editor(self):
        self.file_viewer.extract()
        self.check_urls(200)

    def test_view_access_editor_view_source(self):
        self.addon.update(view_source=True)
        self.file_viewer.extract()
        self.check_urls(200)

    def test_view_access_developer(self):
        self.client.logout()
        assert self.client.login(username=self.dev.email, password='password')
        self.file_viewer.extract()
        self.check_urls(200)

    def test_view_access_developer_view_source(self):
        self.client.logout()
        assert self.client.login(username=self.dev.email, password='password')
        self.addon.update(view_source=True)
        self.file_viewer.extract()
        self.check_urls(200)

    def test_view_access_another_developer(self):
        self.client.logout()
        assert self.client.login(username=self.regular.email,
                                 password='password')
        self.file_viewer.extract()
        self.check_urls(403)

    def test_view_access_another_developer_view_source(self):
        self.client.logout()
        assert self.client.login(username=self.regular.email,
                                 password='password')
        self.addon.update(view_source=True)
        self.file_viewer.extract()
        self.check_urls(200)

    def test_poll_extracted(self):
        self.file_viewer.extract()
        res = self.client.get(self.poll_url())
        eq_(res.status_code, 200)
        eq_(json.loads(res.content)['status'], True)

    def test_poll_not_extracted(self):
        res = self.client.get(self.poll_url())
        eq_(res.status_code, 200)
        eq_(json.loads(res.content)['status'], False)

    def test_poll_extracted_anon(self):
        self.client.logout()
        res = self.client.get(self.poll_url())
        eq_(res.status_code, 403)

    def test_content_headers(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url('install.js'))
        assert 'etag' in res._headers
        assert 'last-modified' in res._headers

    def test_file_header(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url(not_binary))
        url = res.context['file_link']['url']
        eq_(url, reverse('editors.review', args=[self.version.pk]))

    def test_file_header_anon(self):
        self.client.logout()
        self.file_viewer.extract()
        self.addon.update(view_source=True)
        res = self.client.get(self.file_url(not_binary))
        url = res.context['file_link']['url']
        eq_(url, reverse('addons.detail', args=[self.addon.pk]))

    def test_content_no_file(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url())
        doc = pq(res.content)
        eq_(len(doc('#content')), 0)

    def test_no_files(self):
        res = self.client.get(self.file_url())
        eq_(res.status_code, 200)
        assert 'files' not in res.context

    def test_files(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url())
        eq_(res.status_code, 200)
        assert 'files' in res.context

    def test_files_anon(self):
        self.client.logout()
        res = self.client.get(self.file_url())
        eq_(res.status_code, 403)

    def test_files_file(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url(not_binary))
        eq_(res.status_code, 200)
        assert 'selected' in res.context

    def test_files_back_link(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url(not_binary))
        doc = pq(res.content)
        eq_(doc('#files a.no-key').text(), 'Back to review')

    def test_files_back_link_anon(self):
        self.file_viewer.extract()
        self.client.logout()
        self.addon.update(view_source=True)
        res = self.client.get(self.file_url(not_binary))
        eq_(res.status_code, 200)
        doc = pq(res.content)
        eq_(doc('#files a.no-key').text(), 'Back to addon')


class TestFileViewer(FilesBase, test_utils.TestCase):
    fixtures = ['base/addon_3615', 'base/users']

    def poll_url(self):
        return reverse('files.poll', args=[self.file.pk])

    def file_url(self, file=None):
        args = [self.file.pk]
        if file:
            args.append(file)
        return reverse('files.list', args=args)

    def check_urls(self, status):
        for url in [self.poll_url(), self.file_url()]:
            eq_(self.client.get(url).status_code, status)

    def add_file(self, name, contents):
        dest = os.path.join(self.file_viewer.dest, name)
        open(dest, 'w').write(contents)

    def test_files_xss(self):
        self.file_viewer.extract()
        self.add_file('<script>alert("foo")', '')
        res = self.client.get(self.file_url())
        doc = pq(res.content)
        # Note: this is text, not a DOM element, so escaped correctly.
        assert '<script>alert("' in doc('#files li a').text()

    def test_content_file(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url('install.js'))
        doc = pq(res.content)
        eq_(len(doc('#content')), 1)

    def test_content_no_file(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url())
        doc = pq(res.content)
        eq_(len(doc('#content')), 1)
        eq_(res.context['selected']['short'], 'install.rdf')

    def test_content_xss(self):
        self.file_viewer.extract()
        for name in ['file.txt', 'file.html', 'file.htm']:
            # If you are adding files, you need to clear out the memcache
            # file listing.
            cache.clear()
            self.add_file(name, '<script>alert("foo")</script>')
            res = self.client.get(self.file_url(name))
            doc = pq(res.content)
            # Note: this is text, not a DOM element, so escaped correctly.
            assert doc('#content').text().startswith('<script')

    def test_binary(self):
        self.file_viewer.extract()
        self.add_file('file.php', '<script>alert("foo")</script>')
        res = self.client.get(self.file_url('file.php'))
        eq_(res.status_code, 200)
        assert self.file_viewer.get_files()['file.php']['md5'] in res.content

    def test_tree_no_file(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url('doesnotexist.js'))
        eq_(res.status_code, 404)

    def test_directory(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url('doesnotexist.js'))
        eq_(res.status_code, 404)

    def test_unicode(self):
        self.file_viewer.src = unicode_filenames
        self.file_viewer.extract()
        res = self.client.get(self.file_url(iri_to_uri(u'\u1109\u1161\u11a9')))
        eq_(res.status_code, 200)

    def test_serve_no_token(self):
        self.file_viewer.extract()
        res = self.client.get(self.files_serve(binary))
        eq_(res.status_code, 403)

    def test_serve_fake_token(self):
        self.file_viewer.extract()
        res = self.client.get(self.files_serve(binary) + '?token=aasd')
        eq_(res.status_code, 403)

    def test_serve_bad_token(self):
        self.file_viewer.extract()
        res = self.client.get(self.files_serve(binary) + '?token=a asd')
        eq_(res.status_code, 403)

    def test_serve_get_token(self):
        self.file_viewer.extract()
        res = self.client.get(self.files_redirect(binary))
        eq_(res.status_code, 302)
        url = res['Location']
        assert url.startswith(settings.STATIC_URL)
        assert urlparse.urlparse(url).query.startswith('token=')

    def test_memcache_goes_bye_bye(self):
        self.file_viewer.extract()
        res = self.client.get(self.files_redirect(binary))
        url = res['Location'][len(settings.STATIC_URL):]
        cache.clear()
        res = self.client.get(url)
        eq_(res.status_code, 403)

    def test_bounce(self):
        self.file_viewer.extract()
        res = self.client.get(self.files_redirect(binary), follow=True)
        eq_(res.status_code, 200)
        eq_(res['X-SENDFILE'],
            self.file_viewer.get_files().get(binary)['full'])

    @patch_object(settings._wrapped, 'FILE_VIEWER_SIZE_LIMIT', 5)
    def test_file_size(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url(not_binary))
        doc = pq(res.content)
        assert doc('p.notification-box').text().startswith('File size is')

    def test_poll_failed(self):
        msg = Message('file-viewer:%s' % self.file_viewer)
        msg.save('I like cheese.')
        res = self.client.get(self.poll_url())
        eq_(res.status_code, 200)
        data = json.loads(res.content)
        eq_(data['status'], False)
        eq_(data['msg'], ['I like cheese.'])


class TestDiffViewer(FilesBase, test_utils.TestCase):
    fixtures = ['base/addon_3615', 'base/users']

    def setUp(self):
        super(TestDiffViewer, self).setUp()
        self.file_viewer = DiffHelper(self.file, self.file_two)

    def poll_url(self):
        return reverse('files.compare.poll', args=[self.file.pk,
                                                   self.file_two.pk])

    def add_file(self, file_obj, name, contents):
        dest = os.path.join(file_obj.dest, name)
        open(dest, 'w').write(contents)

    def file_url(self, file=None):
        args = [self.file.pk, self.file_two.pk]
        if file:
            args.append(file)
        return reverse('files.compare', args=args)

    def check_urls(self, status):
        for url in [self.poll_url(), self.file_url()]:
            eq_(self.client.get(url).status_code, status)

    def test_tree_no_file(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url('doesnotexist.js'))
        eq_(res.status_code, 404)

    def test_content_file(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url(not_binary))
        doc = pq(res.content)
        eq_(len(doc('pre')), 3)

    def test_binary_serve_links(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url(binary))
        doc = pq(res.content)
        node = doc('#content-wrapper a')
        eq_(len(node), 2)
        assert node[0].text.startswith('Download ar.dic')

    def test_files_different_msg(self):
        self.file_viewer.extract()
        self.add_file(self.file_viewer.file_one, not_binary, 'something')
        res = self.client.get(self.file_url(not_binary))
        doc = pq(res.content)
        assert doc('#content-wrapper p').text().startswith('Files are diff')

    def test_files_same_msg(self):
        self.file_viewer.extract()
        res = self.client.get(self.file_url(not_binary))
        doc = pq(res.content)
        assert doc('#content-wrapper p').text().startswith('Files are the s')
