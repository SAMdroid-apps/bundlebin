import re
import os
import unittest
from tempfile import mkdtemp
from zipfile import ZipFile
from cStringIO import StringIO

import main


ACTIVITY_INFO = '''[Activity]
name = Bibliography
bundle_id = org.sugarlabs.BibliographyActivity
icon = activity-icon
exec = sugar-activity activity.BibliographyActivity
activity_version = 2
show_launcher = yes
summary = Need a bibliography?
categories = documents teacher
repository = https://github.com/samdroid-apps/bibliography-activity
'''
PARTIAL_ACTIVITY_INFO = '''[Activity]
name = Bibliography
bundle_id = org.sugarlabs.BibliographyActivity
exec = sugar-activity activity.BibliographyActivity
'''
BAD_ACTIVITY_INFO = '''[Activity]
name = Bibliography
summary = Need a bibliography?
repository = https://github.com/samdroid-apps/bibliography-activity
'''

REDIRECT_REGEX = re.compile('<a href="(/bundle/.*\.xo)">')
FILENAME_REGEX = re.compile('<a href="/bundle/(.*\.xo)">')


class TestBundleHelpers(unittest.TestCase):
    def test_vaild(self):
        bundle = ZipFile(StringIO(), 'w')
        bundle.writestr('my.activity/activity/activity.info', ACTIVITY_INFO)
        self.assertEqual(main.vaild_bundle(bundle), True)

    def test_empty(self):
        bundle = ZipFile(StringIO(), 'w')
        self.assertEqual(main.vaild_bundle(bundle), False)

    def test_bad(self):
        bundle = ZipFile(StringIO(), 'w')
        bundle.writestr('m.activity/activity/activity.info', BAD_ACTIVITY_INFO)
        self.assertEqual(main.vaild_bundle(bundle), False)

    def test_metadata(self):
        bundle = ZipFile(StringIO(), 'w')
        bundle.writestr('my.activity/activity/activity.info', ACTIVITY_INFO)
        bundle.writestr('my.activity/activity/activity-icon', 'test')
        name, version, summary, icon = main.get_bundle_meta(bundle)
        self.assertEqual(name, 'Bibliography')
        self.assertEqual(version, '2')
        self.assertEqual(summary, 'Need a bibliography?')
        self.assertEqual(icon, 'test')

    def test_metadata_partial(self):
        bundle = ZipFile(StringIO(), 'w')
        bundle.writestr('my/activity/activity.info', PARTIAL_ACTIVITY_INFO)
        name, version, summary, icon = main.get_bundle_meta(bundle)
        self.assertEqual(name, 'Bibliography')
        self.assertEqual(version, None)
        self.assertEqual(summary, None)
        self.assertEqual(icon, None)


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        main.app.config['TESTING'] = True
        main.app.config['UPLOAD_FOLDER'] = mkdtemp()
        self.app = main.app.test_client()
        main.setup_db('sqlite:///:memory:')

    def _test_bundle(self):
        tmp_file = StringIO()
        bundle = ZipFile(tmp_file, 'w')
        bundle.writestr('my.activity/activity/activity.info', ACTIVITY_INFO)
        bundle.close()
        return StringIO(tmp_file.getvalue())

    def test_upload(self):
        r = self.app.post('/upload',
                          data={'file': (self._test_bundle(), 'bundle.xo')})
        self.assertEqual(r.status, '302 FOUND')

    def test_upload_bad(self):
        tmp_file = StringIO()
        bundle = ZipFile(tmp_file, 'w')
        bundle.writestr('m.activity/activity/activity.info', BAD_ACTIVITY_INFO)
        bundle.close()
        f = StringIO(tmp_file.getvalue())

        r = self.app.post('/upload', data={'file': (f, 'bundle.xo')})
        self.assertEqual(r.status, '415 UNSUPPORTED MEDIA TYPE')

    def test_info(self):
        r = self.app.post('/upload',
                          data={'file': (self._test_bundle(), 'bundle.xo')})
        self.assertEqual(r.status, '302 FOUND')
        info_url = REDIRECT_REGEX.search(r.data).group(1)

        r = self.app.get(info_url)
        self.assertTrue('Bibliography' in r.data)
        self.assertTrue('Version 2' in r.data)
        self.assertTrue('Need a bibliography?' in r.data)

    def test_no_delete(self):
        r = self.app.post('/upload',
                          data={'file': (self._test_bundle(), 'bundle.xo')})
        info_url = REDIRECT_REGEX.search(r.data).group(1)

        main.app.config['DELETE_AFTER'] = 12 * 60 * 60
        self.app.get('/delete')

        r = self.app.get(info_url)
        self.assertEqual(r.status, '200 OK')

    def test_delete(self):
        r = self.app.post('/upload',
                          data={'file': (self._test_bundle(), 'bundle.xo')})
        info_url = REDIRECT_REGEX.search(r.data).group(1)

        main.app.config['DELETE_AFTER'] = -1
        self.app.get('/delete')

        r = self.app.get(info_url)
        self.assertEqual(r.status, '404 NOT FOUND')

    def test_move_to_mirror(self):
        r = self.app.post('/upload',
                          data={'file': (self._test_bundle(), 'bundle.xo')})
        filename = FILENAME_REGEX.search(r.data).group(1)

        r = self.app.get('/mirror/{}/mirrorfilename.xo'.format(filename))
        self.assertEqual(r.status, '200 OK')

        r = self.app.get('/raw/' + filename)
        self.assertEqual(r.status, '301 MOVED PERMANENTLY')

    def test_no_move_to_mirror(self):
        r = self.app.post('/upload',
                          data={'file': (self._test_bundle(), 'bundle.xo')})
        filename = FILENAME_REGEX.search(r.data).group(1)

        r = self.app.get('/raw/' + filename)
        self.assertEqual(r.status, '200 OK')

if __name__ == '__main__':
    unittest.main()
