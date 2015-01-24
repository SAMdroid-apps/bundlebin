import os
import time
import shutil
import os.path
import zipfile
from tempfile import mktemp
from base64 import b64encode
from ConfigParser import ConfigParser

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
from werkzeug import secure_filename
import dataset


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'data/uploads/'
app.config['DELETE_AFTER'] = 12 * 60 * 60
app.config['MIRROR_ROOT'] = 'https://download.sugarlabs.org/activities2/'


def vaild_bundle(zip_):
    if len(zip_.namelist()) == 0:
        return False

    base = zip_.namelist()[0].split('/')[0]
    if os.path.join(base, 'activity/activity.info') not in zip_.namelist():
        return False
    activity_info = zip_.open(os.path.join(base, 'activity/activity.info'))

    cp = ConfigParser()
    cp.readfp(activity_info)
    section = 'Activity'

    if cp.has_option(section, 'name') and cp.has_option(section, 'bundle_id'):
        return True
    else:
        return False


def get_bundle_meta(zip_):
    cp = ConfigParser()
    base = zip_.namelist()[0].split('/')[0]
    cp.readfp(zip_.open(os.path.join(base, 'activity/activity.info')))
    section = 'Activity'
    dict_ = dict(cp.items(section))

    icon_name = dict_.get('icon')
    icon = None
    paths = [os.path.join(base, 'activity/{}'.format(icon_name)),
             os.path.join(base, 'activity/{}.svg'.format(icon_name))]
    for path in paths:
        if path in zip_.namelist():
            icon = zip_.open(path).read()
            break

    return dict_.get('name'), dict_.get('activity_version'), \
           dict_.get('summary'), icon



db = None
def setup_db(path):
    global db
    db = dataset.connect(path)


@app.route('/upload', methods=['POST'])
def upload():
    tmp_path = mktemp()
    request.files['file'].save(tmp_path)

    try:
        with zipfile.ZipFile(tmp_path) as f:
            if not vaild_bundle(f):
                abort(415)
                return
            name, version, summary, icon = get_bundle_meta(f)
    except zipfile.BadZipfile:
        abort(415)
        return

    created = int(time.time())
    filename = secure_filename('{}-{}.xo'.format(name, created))
    shutil.move(tmp_path, os.path.join(app.config['UPLOAD_FOLDER'], filename))
    url = url_for('bundle_download', filename=filename)

    db['bundles'].insert(dict(url=url, filename=filename, name=name,
                              version=version, summary=summary, icon=icon,
                              created=created, deleted=False, redirect=''))
    return redirect(url_for('bundle_info', filename=filename))


@app.route('/raw/<filename>')
def bundle_download(filename):
    bundle = db['bundles'].find_one(filename=filename)
    if bundle is None:
        abort(404)
        return

    if bundle['redirect']:
        return redirect(app.config['MIRROR_ROOT'] + bundle['redirect'],
                        code=301)
    else:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/mirror/<filename>/<new_filename>')
def mirror(filename, new_filename):
    bundle = db['bundles'].find_one(filename=filename)
    if bundle is None:
        abort(404)
        return

    bundle['redirect'] = new_filename
    db['bundles'].update(bundle, ['filename'])
    return 'OK'

@app.route('/bundle/<filename>')
def bundle_info(filename):
    bundle = db['bundles'].find_one(filename=filename)
    if bundle is None:
        abort(404)
        return

    if bundle['icon'] is not None:
        bundle['icon'] = b64encode(bundle['icon'])
    return render_template('bundle.html', **bundle)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/delete')
def delete():
    for bundle in db['bundles']:
        if time.time() - bundle['created'] < app.config['DELETE_AFTER']:
            continue

        os.remove(os.path.join(app.config['UPLOAD_FOLDER'],
                               bundle['filename']))
        db['bundles'].delete(filename=bundle['filename'])
    return 'OK'


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(415)
def page_not_found(e):
    return render_template('415.html'), 415

if __name__ == '__main__':
    setup_db('sqlite:///data/data.db')
    app.run(debug=True)
