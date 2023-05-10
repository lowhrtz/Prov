# Prov
# Copyright (C) 2022 Giancarlo DiMino
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import json
import os
import sqlite3
import sys
from hashlib import pbkdf2_hmac
from beaker.middleware import SessionMiddleware
if sys.version_info.major == 2:
    VERSION_MAJOR = 2
    FileNotFoundError = IOError
    import MySQLdb as mysql
    from urlparse import parse_qs
elif sys.version_info.major == 3:
    VERSION_MAJOR = 3
    import mysql.connector as mysql
    from urllib.parse import parse_qs
else:
    print('Must be either Python2 or Python3')
    sys.exit(1)

APP_TITLE = 'Phone Provisioner'
SQLITE_DB = os.path.join(os.path.dirname(__file__), 'prov.db')
TEMPLATES_FOLDER = os.path.join(os.path.dirname(__file__), 'templates')
SALT_LEN = 32

STATUS = {
    'OK': '200 OK',
    'Forbidden': '403 Forbidden',
    'Not Found': '404 Not Found',
    'Redirect': '302 Found',
    'ISE': '500 Internal Server Error',
}

HEADER = {
    'html': ('Content-type', 'text/html'),
    "css": ("Content-type", "text/css"),
    'xml': ('Content-type', 'text/xml'),
    'js': ('Content-type', 'text/javascript'),
    'json': ('Content-type', 'application/json'),
    'jpeg': ('Content-type', 'image/jpeg'),
    'gif': ('Content-type', 'image/gif'),
    'png': ('Content-type', 'image/png'),
    'bin': ('content-type', 'application/octet-stream'),
}


class AppResponse(object):
    """Object to hold html, response status, and response headers in one place"""

    def __init__(self, html_string, status=STATUS['OK'], header=[ HEADER['html'] ]):
        """Init function

        :param html_string The text string (or binary data) to be the body of the response
        :type html_string str or bytes
        :param status Response status
        :type status str
        :param header List of tuples that represent the reponse headers
        :type header list
        :return AppResponse instance
        :rtype AppResponse
        """

        self.html_string = html_string
        self.status = status
        self.header = header

    def get_html(self):
        return self.html_string

    def get_status(self):
        return self.status

    def get_header(self):
        return self.header


def get_style():
    return '''\
body {
  background-color: #002a4e;
  color: #ffffff;
  text-align: center;
}

.center {
  margin-left: auto;
  margin-right: auto;
}

div.header {
  font-size: 40px;
  color: #ad9ee3;
}

div.subheader {
  font-size: 30px;
}

div.info {
  line-height: 300%;
}

div.menu {
  margin: 30px 0px;
}

div.menu > span {
  border: 2px outset #ff00fb;
  border-radius: 15px;
  margin: 0px 15px;
  padding: 5px 10px;
  font-size: 200%;
  background: #5c028e;
  color: #ffffff;
  cursor: pointer;
}

.stage input, .stage select, .stage button {
  margin: 10px 5px;
}

.stage textarea {
  margin: 0px 5px;
}

.message {
  animation: fadeout 3s;
  animation-delay: 2s;
  animation-fill-mode: forwards;
  margin: 10px 0px;
}

@keyframes fadeout {
  from { opacity: 1; }
  to   { opacity: 0; }
}

.ext_item {
  border: 1px solid #ff00fb;
  border-radius: 10px;
  box-shadow: 5px 5px 2px -1px #ffffff38;
  display: inline-block;
  margin: 10px 0px;
  padding: 10px;
  background: #5c028e;
}

.ext_item form {
  display: inline;
}

.delete {
  background-color: #ff2f2f;
}

.grid {
  display: grid;
  align-items: center;
}

.inline-grid {
  display: inline-grid;
  align-items: center;
}

.gr-two-col {
  grid-template-columns: auto auto;
}

.gr-three-col {
  grid-template-columns: auto auto auto;
}

.gr-four-col {
  grid-template-columns: auto auto auto auto;
}

.gr-five-col {
  grid-template-columns: auto auto auto auto auto;
}
'''

def get_def_head():
    string_format = {
        'style': get_style(),
        'title': APP_TITLE,
    }
    return '''\
<head>
  <title>{title}</title>
  <style>{style}</style>
</head>'''.format(**string_format)

def get_setup(environ):
    """Returns the setup page"""

    string_format = {
        'head': get_def_head(),
        'base_dir': environ.get('SCRIPT_NAME', ''),
    }
    html_string = '''\
<html>
{head}
<body>
<div class="header">Intial Setup</div>
<div class="info">
This appears to be your first time running this application.<br />
Fill in the fields to get started.<br />
</div>
<form action="{base_dir}/submit-setup" method="post">
<div class="inline-grid gr-two-col" style="text-align: right; gap: 15px 10px;">
<label for="user">Admin Username</label><input id="user" name="user" required>
<label for="pw1">Set Password</label><input type="password" id="pw1" name="pw1" required>
<label for="pw2">Confirm Pwd</label><input type="password" id="pw2" name="pw2" required>
<label for="phone_server">Phone Server</label><input id="phone_server" name="phone_server" required>
<label for="mysql_host">MySQL Host</label><input id="mysql_host" name="mysql_host" value="localhost" required>
<label for="mysql_user">MySQL User</label><input id="mysql_user" name="mysql_user" required>
<label for="mysql_pass">MySQL Pass</label><input id="mysql_pass" name="mysql_pass" required>
<label for="mysql_db">MySQL DB</label><input id="mysql_db" name="mysql_db" value="asterisk" required>
<label for="static_folder">Static Folder</label><input id="static_folder" name="static_folder" value="/var/www/static_files" required>
</div><br /><br />
<input type="submit" value="Submit">
<form>
</body>
</html>
'''.format(**string_format)
    return AppResponse(html_string)

def submit_setup(environ):
    request_method = environ.get('REQUEST_METHOD', '')
    base_path = environ.get('SCRIPT_NAME', '')
    if request_method != 'POST':
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_path) ])
    try:
        db = sqlite3.connect(SQLITE_DB)
        if VERSION_MAJOR == 2:
            db.text_factory = str
        db.execute('SELECT * FROM settings')
        db.close()
        return AppResponse('<div class="header">Database alread set up!</div>', STATUS['Forbidden'])
    except IOError:
        db.close()
        return AppResponse('<div class="header">Problem with database!</div>', STATUS['ISE'])
    except sqlite3.OperationalError:
        raw_post = environ.get('wsgi.input', '')
        post_input = parse_qs(raw_post.readline().decode(), True)
        return_string = '{}<div class="header">{}</div><div><a href="{}"><button>Back to Main Page</button></a></div>'
        message = 'Setup Successful!'
        user = post_input.get('user', [''])[0]
        pw1 = post_input.get('pw1', [''])[0]
        pw2 = post_input.get('pw2', [''])[0]
        phone_server = post_input.get('phone_server', [''])[0]
        mysql_host = post_input.get('mysql_host', [''])[0]
        mysql_user = post_input.get('mysql_user', [''])[0]
        mysql_pass = post_input.get('mysql_pass', [''])[0]
        mysql_db = post_input.get('mysql_db', [''])[0]
        static_folder = post_input.get('static_folder', [''])[0]
        if pw1 != pw2 or not user or not pw1 or not phone_server or not mysql_host or not mysql_user or not mysql_pass or not mysql_db:
            message = 'Problem Getting Submitted Data!'
            return AppResponse(return_string.format(get_def_head(), message, base_path), STATUS['Forbidden'])
        mysql_pass = hash_pw(mysql_pass)
        ntp_server = phone_server
        with open(os.path.join(os.path.dirname(__file__), 'db.sql')) as sql_file:
            script = sql_file.read()
            sql_file.close()
        db.executescript(script)
        db.execute('INSERT INTO settings VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (phone_server, mysql_host, mysql_user, mysql_pass, mysql_db, static_folder, ntp_server, ""))
        db.execute('INSERT INTO users VALUES (?, ?, ?)', (user, hash_pw(pw1), 0))
        db.commit()
        db.close()
        return AppResponse(return_string.format(get_def_head(), message, base_path))

def get_index(environ):
    """The root of this app.
    
    This will return get_setup if the database gives an OperationalError,
    will redirect to the admin page if is_authed is True,
    otherwise will return the login page

    :param environ The request environment as passed by wsgi
    :type environ dict
    :return AppResponse instance
    :rtype AppResponse
    """

    try:
        db = sqlite3.connect(SQLITE_DB)
        if VERSION_MAJOR == 2:
            db.text_factory = str
        db.execute('SELECT * FROM settings')
        db.close()
    except IOError:
        db.close()
        html_string = '{}Problem with database!'.format(get_def_head())
        return AppResponse(html_string, STATUS['ISE'])
    except sqlite3.OperationalError:
        session = environ['beaker.session']
        if session.pop('is_authed', None) is not None:
            print('Cleaning up stale session files.')
            session.save()
            
        return get_setup(environ)

    session = environ['beaker.session']
    is_authed = session.get('is_authed')
    if is_authed is True:
        base_url = environ.get('SCRIPT_NAME', '')
        admin_url = os.path.join(base_url, 'admin')
        return AppResponse('', STATUS['Redirect'], [ ('Location', admin_url) ])

    string_format = {
        'head': get_def_head(),
        'base_url': environ.get('SCRIPT_NAME', '')
    }
    html_string = '''\
{head}
<body>
  <form action="{base_url}/admin" method="post">
    <h1>Login</h1>
    <div class="inline-grid gr-two-col" style="text-align: left; gap: 10px 10px;">
      <label for="user">User</label><input id="user" name="user" required />
      <label for="pwd">Password</label><input type="password" name="pwd" required />
      <label></label><button style="justify-self: start; font-size: 125%;">Submit</button>
    </div>
  </form>
</body>
'''.format(**string_format)
    return AppResponse(html_string)

def get_menu(environ):
    string_format = {
        'base_url': environ.get('SCRIPT_NAME', ''),
    }
    return '''\
<script>

// Thanks to https://htmldom.dev/serialize-form-data-into-a-query-string/
const serialize = function (formEle) {
    // Get all fields
    // Note that we convert the collection of form elements to array
    const fields = [].slice.call(formEle.elements, 0);

    return fields
        .map(function (ele) {
            const name = ele.name;
            const type = ele.type;

            // We ignore
            // - field that doesn't have a name
            // - disabled field
            // - `file` input
            // - unselected checkbox/radio
            if (!name || ele.disabled || type === 'file' || (/(checkbox|radio)/.test(type) && !ele.checked)) {
                return '';
            }

            // Multiple select
            if (type === 'select-multiple') {
                return ele.options
                    .map(function (opt) {
                        return opt.selected ? `${encodeURIComponent(name)}=${encodeURIComponent(opt.value)}` : '';
                    })
                    .filter(function (item) {
                        return item;
                    })
                    .join('&');
            }

            return `${encodeURIComponent(name)}=${encodeURIComponent(ele.value)}`;
        })
        .filter(function (item) {
            return item;
        })
        .join('&');
};

function ajax_request(url, post = null, target = "stage") {
  var xhttp = new XMLHttpRequest();
  xhttp.onreadystatechange = function() {
    if (this.readyState == 4 && this.status == 200) {
      var u = new URL(this.responseURL);
      var relative_path = u.pathname;
      // console.log(relative_path + " | " + url);
      if (relative_path != url) {
        window.location = this.responseURL;
      } else {
        document.getElementById(target).innerHTML = this.responseText;
      }
    }
  };

  if (post == null) {
    xhttp.open("GET", url, true);
    xhttp.send();
  } else {
    xhttp.open("POST", url, true);
    xhttp.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
    xhttp.send(post);
  }
}

function change_select(sel_id) {
  all_brands = document.getElementsByClassName("brand_models");
  for (let i = 0; i < all_brands.length; i++) {
    brand_model = all_brands.item(i);
    brand_model.style.display = "none";
    brand_model.selectedIndex = 0;
  }
  var sel = document.getElementById(sel_id);
  var models_elem = document.getElementById(sel.value);
  models_elem.style.display = "inline";
}

function get_model_globals(url) {
  // console.log(document.getElementById('model_globals').value);
  var model = document.getElementById('model_globals').value;
  post = "model=" + model;
  ajax_request(url, post);
}

</script>
''' + '''\
<div class="menu">
  <span onclick="ajax_request('{base_url}/global-settings')">Global Settings</span>
  <span onclick="ajax_request('{base_url}/phone-list')">Phone List</span>
  <span onclick="ajax_request('{base_url}/account')">Account</span>
  <span onclick="ajax_request('{base_url}/logout')">Log Out</span>
</div>
'''.format(**string_format)

def get_admin(environ):
    """Admin page

    Will redirect to the index page if method is not POST and
    is_authed is not True
    
    :param environ Request environment
    :type environ dict
    :return AppResponse containing the admin page html
    :rtype AppResponse
    """

    base_url = environ.get('SCRIPT_NAME', '')
    request_method = environ.get('REQUEST_METHOD', '')
    session = environ['beaker.session']
    is_authed = session.get('is_authed')
    if request_method != 'POST' and is_authed is not True:
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])
    elif is_authed is None:
        raw_post = environ.get('wsgi.input', '')
        post_input = parse_qs(raw_post.readline().decode(), True)
        user = post_input.get('user', [''])[0]
        pwd = post_input.get('pwd', [''])[0]
        try:
            db = sqlite3.connect(SQLITE_DB)
            if VERSION_MAJOR == 2:
                db.text_factory = str
            c = db.execute('SELECT password FROM users WHERE username=?', (user, ))
            password = c.fetchone()
            if password is None or not compare_hash(pwd, password[0]):
                return AppResponse(
                '{}<div class="header">Wrong User Or Password</div><div><a href="{}"><button>Back to Main Page</button></a></div>'
                    .format(get_def_head(), base_url),
                STATUS['Forbidden'])
            else:
                session['is_authed'] = True
                session['user'] = user
                session.save()
            db.close()
        except IOError as e:
            print(e)
            db.close()
            return AppResponse('{}<div class="header">Problem with database!</div>'.format(get_def_head()), STATUS['ISE'])
        except sqlite3.OperationalError as e:
            print(e)
            db.close()
            return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])
    elif is_authed is False:
        return AppResponse('{}<div class="header">Forbidden!</div>'.format(get_def_head()), STATUS['Forbidden'])

    try:
        db = sqlite3.connect(SQLITE_DB)
        if VERSION_MAJOR == 2:
            db.text_factory = str
        db.execute('SELECT * FROM settings')
    except IOError as e:
        print(e)
        db.close()
        return AppResponse('{}<div class="header">Problem with database!</div>'.format(get_def_head()), STATUS['ISE'])
    except sqlite3.OperationalError as e:
        print(e)
        db.close()
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])
        
    string_format = {
        'head': get_def_head(),
        'menu': get_menu(environ),
        'global-settings': get_global_settings(environ).get_html(),
    }
    html_string = '''\
{head}
<body>
{menu}
<div class="stage" id="stage">{global-settings}</div>
</body>
'''.format(**string_format)
    return AppResponse(html_string)

def get_global_settings(environ):
    request_method = environ.get('REQUEST_METHOD', '')
    base_url = environ.get('SCRIPT_NAME', '')
    session = environ['beaker.session']
    is_authed = session.get('is_authed')
    if is_authed is not True:
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])

    try:
        db = sqlite3.connect(SQLITE_DB)
        if VERSION_MAJOR == 2:
            db.text_factory = str
        toast = ''
        if request_method == 'POST':
            raw_post = environ.get('wsgi.input', '')
            post_input = parse_qs(raw_post.readline().decode(), True)
            phone_server = post_input.get('phone_server', [''])[0]
            mysql_host = post_input.get('mysql_host', [''])[0]
            mysql_user = post_input.get('mysql_user', [''])[0]
            mysql_pass = post_input.get('mysql_pass', [''])[0]
            mysql_db = post_input.get('mysql_db', [''])[0]
            static_folder = post_input.get('static_folder', [''])[0]
            ntp_server = post_input.get('ntp_server', [''])[0]
            if phone_server:
                query = '''UPDATE settings SET
                     phone_server=?, mysql_host=?, mysql_user=?, mysql_pass=?, mysql_db=?, static_folder=?, ntp_server=?
                     WHERE rowid=1'''
                values = phone_server, mysql_host, mysql_user, mysql_pass, mysql_db, static_folder, ntp_server
                db.execute(query, values)
                db.commit()
                toast = '<div class="message">Update Successful!</div>'

        c = db.execute('SELECT * FROM settings')
        settings = c.fetchone()
        db.close()
    except IOError as e:
        db.close()
        print(e)
        return AppResponse('{}<div class="header">Problem with database!</div>'.format(get_def_head()), STATUS['ISE'])
    except sqlite3.OperationalError as e:
        db.close()
        print(e)
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])

    try:
        walk_g = os.walk(TEMPLATES_FOLDER)
        brands = next(walk_g)[1]
        model_global_list = []
        for brand in brands:
            brand_g = os.walk(os.path.join(TEMPLATES_FOLDER, brand))
            models = next(brand_g)[1]
            for model in models:
                model_path = os.path.join(brand, model)
                model_global_list.append(model_path)
        model_global_options = ''.join(['<option name="{}">{}</option>'.format(m, m) for m in model_global_list])
    except StopIteration:
        model_global_options = 'Templates folder is missing!'


    string_format = {
        'toast': toast,
        'base_url': base_url,
        'phone_server': settings[0],
        'mysql_host': settings[1],
        'mysql_user': settings[2],
        'mysql_pass': settings[3],
        'mysql_db': settings[4],
        'static_folder': settings[5],
        'ntp_server': settings[6],
        'model_global_options': model_global_options,
    }
    html_string = '''\
{toast}<div class="header">Global Settings</div>
<form onsubmit="ajax_request('{base_url}/global-settings', serialize(this)); return false;">
<div class="inline-grid gr-two-col" style="text-align: right; gap: 0px 10px;">
<label for="phone_server">Phone Server</label><input id="phone_server" name="phone_server" value="{phone_server}" required />
<label for="mysql_host">MySQL Host</label><input id="mysql_host" name="mysql_host" value="{mysql_host}" required />
<label for="mysql_user">MySQL User</label><input id="mysql_user" name="mysql_user" value="{mysql_user}" required />
<label for="mysql_pass">MySQL Pass</label><input id="mysql_pass" name="mysql_pass" value="{mysql_pass}" required />
<label for="mysql_db">MySQL DB</label><input id="mysql_db" name="mysql_db" value="{mysql_db}" required />
<label for="static_folder">Static Folder</label><input id="static_folder" name="static_folder" value="{static_folder}" required />
<label for="ntp_server">NTP Server</label><input id="ntp_server" name="ntp_server" value="{ntp_server}" required />
</div><br />
<button>Update Settings</button>
</form>
<br />
<select id="model_globals">
  {model_global_options}
</select>
<button onclick="get_model_globals('{base_url}/model-globals')">Model Globals</button>
'''.format(**string_format)
    return AppResponse(html_string)

def get_model_globals(environ):
    request_method = environ.get('REQUEST_METHOD', '')
    base_url = environ.get('SCRIPT_NAME', '')
    session = environ['beaker.session']
    is_authed = session.get('is_authed')
    if is_authed is not True or request_method != 'POST':
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])
    raw_post = environ.get('wsgi.input', '')
    post_input = parse_qs(raw_post.readline().decode(), True)
    model = post_input.pop('model', [''])[0]

    model_context = {
            'environ': environ,
            'post_input': post_input,
            'settings': model_global_settings(model, post_input)
    }
    model_global_fn = os.path.join(TEMPLATES_FOLDER, model, 'global-settings.template')
    try:
        with open(model_global_fn, 'r') as model_global_f:
            t = model_global_f.read()
            from jinja2 import Template
            t = Template(t).render(**model_context)
    except FileNotFoundError:
        return AppResponse('global-settings.template file not found for {}!'.format(model))
    form_html = '''\
<form onsubmit="ajax_request('{}/model-globals', serialize(this)); return false;">
<input type="hidden" name="model" id="model" value="{}" />
{}
</form>
'''
    return AppResponse(form_html.format(base_url, model, t))

def model_global_settings(model, post=None):
    message = ''
    try:
        db = sqlite3.connect(SQLITE_DB)
        if VERSION_MAJOR == 2:
            db.text_factory = str
        c = db.execute('SELECT model_misc FROM settings')
        model_misc = c.fetchone()[0]
        try:
            model_misc = json.loads(model_misc)
        except ValueError:
            model_misc = {}
        if post:
            model_misc[model] = post
            db.execute('UPDATE settings SET model_misc=? WHERE rowid=1', (json.dumps(model_misc), ))
            message = 'Update Successful!'
            db.commit()
        db.close()
    except IOError as e:
        db.close()
        print(e)
        message = 'Problem accessing the database!'
    except sqlite3.OperationalError as e:
        db.close()
        print(e)
        message = 'Database Error!'


    mm = model_misc.get(model, {})
    mm['message'] = message
    return mm

def get_phone_list(environ):
    request_method = environ.get('REQUEST_METHOD', '')
    base_url = environ.get('SCRIPT_NAME', '')
    session = environ['beaker.session']
    is_authed = session.get('is_authed')
    if is_authed is not True:
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])

    try:
        db = sqlite3.connect(SQLITE_DB)
        if VERSION_MAJOR == 2:
            db.text_factory = str
        if request_method == 'POST':
            #print('POST')
            raw_post = environ.get('wsgi.input', '')
            post_input = parse_qs(raw_post.readline().decode(), True)
            typ = post_input.get('type', [''])[0]
            if typ == 'add':
                ext = post_input.get('ext', [''])[0]
                mac = post_input.get('mac', [''])[0].replace(':', '').lower()
                db.execute('INSERT INTO ext_mac_map VALUES (?, ?, ?, ?)', (ext, mac, '', ''))
                db.commit()
            elif typ == 'del':
                rowid = post_input.get('rowid', [''])[0]
                db.execute('DELETE FROM ext_mac_map WHERE rowid=?', (rowid, ))
                db.commit()
        c = db.execute('SELECT rowid,* FROM ext_mac_map ORDER BY extension')
    except IOError as e:
        db.close()
        print(e)
        return AppResponse('{}<div class="header">Problem with database!</div>'.format(get_def_head()), STATUS['ISE'])
    except sqlite3.OperationalError as e:
        db.close()
        print(e)
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])

    phones = c.fetchall()
    db.close()
    phone_template = '''\
<span class="ext_item">
{ext} - {mac}
<form onsubmit="ajax_request('{base_url}/edit-phone', serialize(this)); return false;">
<input type="hidden" name="rowid" value="{rowid}" />
<button class="edit">Edit</button>
</form>
<form onsubmit="if(confirm('Delete extension {ext}?')){{ajax_request('{base_url}/phone-list', serialize(this))}} return false;">
<input type="hidden" name="type" value="del" />
<input type="hidden" name="rowid" value="{rowid}" />
<button class="delete">Delete</button>
</form>
</span>
'''
    phones_html = '<br />'.join([phone_template.format(
                                  rowid=p[0], ext=p[1], mac=p[2],
                                  base_url=base_url) for p in phones])
    string_format = {
        'base_url': base_url,
        'phones': phones_html,
    }
    html_string = '''\
<form onsubmit="ajax_request('{base_url}/phone-list', serialize(this)); return false;">
<input type="hidden" name="type" value="add" />
<label for="ext">EXT</label>
<input name="ext" id="ext" required />
<label for="mac">MAC</label>
<input name="mac" id="mac" required /><br />
<button>Add Phone</button><br />
</form>
<div class="header">Phone List</div>

{phones}
'''.format(**string_format)
    return AppResponse(html_string)

def edit_phone(environ):
    base_url = environ.get('SCRIPT_NAME', '')
    request_method = environ.get('REQUEST_METHOD', '')
    session = environ['beaker.session']
    is_authed = session.get('is_authed')

    if request_method != 'POST' or is_authed is not True:
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])

    raw_post = environ.get('wsgi.input', '')
    post_input = parse_qs(raw_post.readline().decode(), True)
    rowid = post_input.get('rowid', [''])[0]
    toast = ''
    try:
        db = sqlite3.connect(SQLITE_DB)
        if VERSION_MAJOR == 2:
            db.text_factory = str
        ex = post_input.get('ext', [])
        ma = post_input.get('mac', [])
        model = post_input.get('model', [''])
        model = list(filter(lambda m: m != 'Choose a Model', model))
        clear_template = post_input.get('clear_template', [])
        model_post = get_model_post(post_input)
        if ex:
            ex = ex[0]
            ma = ma[0].replace(':', '').lower()
            db.execute('UPDATE ext_mac_map SET extension=?, mac=? WHERE rowid=?', (ex, ma, rowid))
            if len(model) > 0 and model[0]:
                #print(model)
                model = model[0]
                db.execute('UPDATE ext_mac_map SET template=? WHERE rowid=?', (model, rowid))
            db.commit()
            toast = '<div class="message">Update Successful!</div>'
        if clear_template:
            clear_template = clear_template[0]
            db.execute('UPDATE ext_mac_map SET template=? WHERE rowid=?', ('', rowid))
            db.commit()
        c = db.execute('SELECT * FROM ext_mac_map WHERE rowid=?', (rowid, ))
        phone = c.fetchone()
        ext = phone[0]
        mac = phone[1]
        template = phone[2]
        misc = phone[3]
        try:
            misc_dict = json.loads(misc)
        except ValueError:
            misc_dict = {}
        if model_post:
            misc_dict[template] = model_post
            db.execute('UPDATE ext_mac_map SET misc=? WHERE rowid=?', (json.dumps(misc_dict), rowid))
            db.commit()
        db.close()
    except IOError as e:
        db.close()
        print(e)
        return AppResponse('{}<div class="header">Problem with database!</div>'.format(get_def_head()))
    except sqlite3.OperationalError as e:
        db.close()
        print(e)
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])


    if not template or not template.strip():
        template_html = get_template_select()
    else:
        context = {
                'environ': environ,
                'post_input': post_input,
                'ext': ext,
                'mac': mac,
                'template': template,
                'misc': misc_dict[template] if template in misc_dict else {},
        }
        try:
            with open(os.path.join(TEMPLATES_FOLDER, template, 'edit-phone.template'), 'r') as t_file:
                t = t_file.read()
                from jinja2 import Template
                t = Template(t).render(**context)
        except FileNotFoundError:
            t = 'Couldnt find the edit-phone.template file!'

        template_html = '''\
<button type="button" onclick="ajax_request('{}/edit-phone', 'clear_template=true&rowid={}')">Change Model</button><br />
'''.format(base_url, rowid) + t

    string_template = {
            'toast': toast,
            'base_url': base_url,
            'rowid': rowid,
            'ext': ext,
            'mac': mac,
            'misc': misc,
            'template_html': template_html,
    }
    html_string = '''\
<form onsubmit="ajax_request('{base_url}/edit-phone', serialize(this)); return false;">
{toast}<button>Update Phone</button><br />
<div class="header">Edit {ext}</div>
<input type="hidden" name="rowid" value="{rowid}" />
EXT: <input name="ext" value="{ext}" required />
MAC: <input name="mac" value="{mac}" required /><br />
{template_html}
</form>
'''.format(**string_template)

    return AppResponse(html_string)

def get_model_post(post_input):
    post_input = post_input.copy()
    post_input.pop('rowid', None)
    post_input.pop('ext', None)
    post_input.pop('mac', None)
    post_input.pop('model', None)
    post_input.pop('clear_template', None)

    return post_input

def get_template_select():
    try:
        walk_g = os.walk(TEMPLATES_FOLDER)
        brands = next(walk_g)[1]
    except StopIteration:
        return '<div class="header">The templates folder is missing!</div>'

    models_string = '<select name="model" id="{}" class="brand_models" style="display: none;"><option selected disabled>Choose a Model</option>{}</select>'
    brand_models_html = ''
    for brand in brands:
        model_walk_g = os.walk(os.path.join(TEMPLATES_FOLDER, brand))
        models = next(model_walk_g)[1]
        models_html = ''.join(['<option value="{}/{}">{}</option>'.format(brand, m, m) for m in models])
        brand_models_html += models_string.format(brand, models_html)
        #print(brand_models_html)

    brands_html = ''.join(['<option value="{}">{}</option>'.format(d, d) for d in brands])
    select_html = '''\
<select id="brands" onchange="change_select('brands')"><option selected disabled>Choose a Brand</option>{}</select>
'''.format(brands_html)
    return select_html + brand_models_html

def get_account(environ):
    base_url = environ.get('SCRIPT_NAME', '')
    request_method = environ.get('REQUEST_METHOD', '')
    session = environ['beaker.session']
    is_authed = session.get('is_authed')
    user = session.get('user', '')
    if not is_authed:
        return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])

    message_html = ''

    if request_method == 'POST':
        raw_post = environ.get('wsgi.input', '')
        post_input = parse_qs(raw_post.readline().decode(), True)
        account_edit_type = post_input.get('account_edit_type', [''])[0]
        if account_edit_type == 'change_pw':
            current_pw = post_input.get('current_pw', [''])[0]
            new_pw1 = post_input.get('new_pw1', [''])[0]
            new_pw2 = post_input.get('new_pw2', [''])[0]
            try:
                db = sqlite3.connect(SQLITE_DB)
                if VERSION_MAJOR == 2:
                    db.text_factory = str
                c = db.execute('SELECT * FROM users WHERE username=?', (user, ))
                r = c.fetchone()
                pw = r[1]
                if not compare_hash(current_pw, pw):
                    message_html = '<div class="message">Wrong Password!</div>'
                elif new_pw1 != new_pw2:
                    message_html = '<div class="message">The new passwords do not match!</div>'
                else:
                    db.execute('UPDATE users SET password=? WHERE username=?', (hash_pw(new_pw1), user))
                    db.commit()
                    message_html = '<div class="message">Password Successfully Changed!</div>'
                db.close()
            except IOError as e:
                db.close()
                print(e)
                message_html = '<div class="message">Problem accessing the database!</div>'
            except sqlite3.OperationalError as e:
                db.close()
                print(e)
                message_html = '<div class="message">Problem accessing the database!</div>'


    html_string = '''\
<div class="header">Account Settings</div>
<div class="subheader">User: {user}</div>
<br />
{message_html}
<form onsubmit="ajax_request('{base_url}/account', serialize(this)); return false;" method="post">
  <div style="font-size: 125%;">Change Password</div>
  <input type="hidden" name="account_edit_type" value="change_pw" />
  <div class="inline-grid gr-two-col" style="text-align: right;">
    <label for="current_pw">Current Password</label><input type="password" id="current_pw" name="current_pw" required />
    <label for="new_pw1">New Password</label><input type="password" id="new_pw1" name="new_pw1" required />
    <label for="new_pw2">Confirm New Password</label><input type="password" id="new_pw2" name="new_pw2" required />
  </div>
  <br />
  <button>Submit</button>
</form>
'''.format(**{
        'base_url': base_url,
        'user': user,
        'message_html': message_html,
    })

    return AppResponse(html_string)

def get_logout(environ):
    base_url = environ.get('SCRIPT_NAME', '')
    session = environ['beaker.session']
    session['is_authed'] = None
    session['user'] = None
    session.save()
    return AppResponse('', STATUS['Redirect'], [ ('Location', base_url) ])

def check_brand_urls(environ):
    #print(environ['PATH_INFO'])
    path_info = environ.get('PATH_INFO', '')
    try:
        walk_g = os.walk(TEMPLATES_FOLDER)
        brands = next(walk_g)[1]
    except StopIteration:
        return

    for brand in brands:
        brand_folder = os.path.join(TEMPLATES_FOLDER, brand)
        brand_walk_g = os.walk(brand_folder)
        models = next(brand_walk_g)[1]
        for model in models:
            fn = os.path.join(TEMPLATES_FOLDER, brand, model, 'urls')
            try:
                with open(fn, 'r') as urls_file:
                    urls = urls_file.readlines()
            except FileNotFoundError:
                continue
            
            import re
            re_comment_pattern = r'\(\?#(?P<templatefile>[^\(\)]*)\)\(\?#(?P<format>[^\(\)]*)\)$'
            for url in urls:
                url = url.rstrip('\n')
                #print(url)
                m = re.search(url, path_info)
                m2 = re.search(re_comment_pattern, url)
                if not m or not m2:
                    continue
                m_dict = m.groupdict()
                m2_dict = m2.groupdict()
                mac = m_dict.get('mac', '')
                try:
                    db = sqlite3.connect(SQLITE_DB)
                    if VERSION_MAJOR == 2:
                        db.text_factory = str
                    s = db.execute('SELECT * FROM settings')
                    settings = s.fetchone()
                except IOError:
                    db.close()
                    return AppResponse('{}<div class="header">Problem with the database!</div>'.format(get_def_head()), STATUS['ISE'])
                except sqlite3.OperationalError:
                    db.close()
                    return AppResponse('{}<div class="header">Problem with the database!</div>'.format(get_def_head()), STATUS['ISE'])


                phone_server = settings[0]
                mysql_host = settings[1]
                mysql_user = settings[2]
                mysql_pass = settings[3]
                mysql_db = settings[4]
                ntp_server = settings[6]
                model_misc = settings[7]
                try:
                    model_misc = json.loads(model_misc)
                except ValueError:
                    model_misc = {}
                context = {
                        'environ': environ,
                        'phone_server': phone_server,
                        'ntp_server': ntp_server,
                        'model_misc': model_misc,

                        # Helper Functions
                        'get_def_head': get_def_head,
                        'get_menu': get_menu,
                        #'handle_post': handle_custom_post,
                }

                if mac:
                    #print(mac)
                    try:
                        c = db.execute('SELECT * FROM ext_mac_map WHERE mac=?', (mac,))
                        r = c.fetchone()
                        db.close()
                    except IOError as e:
                        db.close()
                        print(e)
                        return AppResponse('{}<div class="header">Problem with the database!</div>'.format(get_def_head()), STATUS['ISE'])
                    except sqlite3.OperationalError as e:
                        db.close()
                        print(e)
                        return AppResponse('{}<div class="header">Problem with the database!</div>'.format(get_def_head()), STATUS['ISE'])
                    if not r:
                        return
                    ext = r[0]
                    template = r[2]
                    if r[3]:
                        misc = json.loads(r[3])
                    else:
                        misc = {}
                    if template != '{}/{}'.format(brand, model):
                        continue
                    template_misc = misc[template] if template in misc else {}
                    context['ext'] = ext
                    context['mac'] = mac
                    context['template'] = template
                    context['misc'] = template_misc
                    try:
                        ast_db = mysql.connect(host=mysql_host, user=mysql_user, passwd=mysql_pass, db=mysql_db)
                        ast_c = ast_db.cursor()
                        ast_c.execute("SELECT data FROM sip WHERE id=%s AND keyword='secret'", (ext,))
                        secret_r = ast_c.fetchone()
                        if not secret_r:
                            return
                        secret = secret_r[0]
                        context['secret'] = secret
                        ast_c.execute("SELECT name FROM users WHERE extension=%s", (ext,))
                        name_r = ast_c.fetchone()
                        name = name_r[0]
                        context['name'] = name
                        ast_db.close()
                    except IOError as e:
                        ast_db.close()
                        print(e)
                        return AppResponse('{}<div class="header">Problem connecting to the Freepbx Mysql DB.</div>'.format(get_def_head()), STATUS['ISE'])
                    except mysql.InterfaceError as e:
                        ast_dn.close()
                        print(e)
                        return AppResponse('{}<div class="header">Problem with MySQL/MariaDB database.</div>'.format(get_def_head()), STATUS['ISE'])
                templatefile = m2_dict.get('templatefile', '')
                fmt = m2_dict.get('format')
                #print(templatefile)
                #print(fmt)
                fn = os.path.join(TEMPLATES_FOLDER, brand, model, templatefile)
                try:
                    with open(fn, 'r') as t_file:
                        t = t_file.read()
                except FileNotFoundError:
                    return AppResponse('{}<div class="header">Template File Missing!</div>'.format(get_def_head()), STATUS['Not Found'])
                from jinja2 import Template
                t = Template(t).render(**context)
                return AppResponse(t, STATUS['OK'], [ HEADER[fmt] if fmt in HEADER else HEADER['html'] ])

def check_static_content(environ):
    filename = environ.get('PATH_INFO', '').strip('/')
    try:
        db = sqlite3.connect(SQLITE_DB)
        if VERSION_MAJOR == 2:
            db.text_factory = str
        c = db.execute('SELECT static_folder FROM settings')
        static_folder = c.fetchone()[0]
        path = os.path.join(static_folder, filename)
        if os.path.exists(path):
            f = open(path, 'rb')
            html_string = f.read()
            f.close()
        else:
            return
        db.close()
    except IOError as e:
        db.close()
        print(e)
        return
    except sqlite3.OperationalError as e:
        db.close()
        print(e)
        return

    import mimetypes
    m_type, _encoding = mimetypes.guess_type(filename)
    if not m_type:
        m_type = 'application/octet-stream'

    return AppResponse(html_string, STATUS['OK'], [ ('Content-type', m_type) ])

def hash_pw(pw):
    salt = os.urandom(SALT_LEN)
    key = pbkdf2_hmac('sha256', pw.encode('utf-8'), salt, 100000)
    return salt + key

def compare_hash(candidate, hashed_pw):
    salt, key = hashed_pw[:SALT_LEN], hashed_pw[SALT_LEN:]
    cand_key = pbkdf2_hmac('sha256', candidate.encode('utf-8'), salt, 100000)
    return cand_key == key
    
def process_request(environ):
    path_info = environ.get('PATH_INFO', '')

    if path_info == '/' or path_info == '':
        return get_index(environ)

    elif path_info == '/submit-setup':
        return submit_setup(environ)

    elif path_info == '/admin' or path_info == '/admin/':
        return get_admin(environ)

    elif path_info == '/global-settings':
        return get_global_settings(environ)

    elif path_info == '/model-globals':
        return get_model_globals(environ)

    elif path_info == '/phone-list':
        return get_phone_list(environ)

    elif path_info == '/edit-phone':
        return edit_phone(environ)

    elif path_info == '/account':
        return get_account(environ)

    elif path_info == '/logout':
        return get_logout(environ)

    else:
        cbu_ret = check_brand_urls(environ)
        if cbu_ret:
            return cbu_ret

        csc_ret = check_static_content(environ)
        if csc_ret:
            return csc_ret

    return AppResponse('{}<h1>404 File Not Found!</h1>'.format(get_def_head()), STATUS['Not Found'])

def application(environ, start_response):
    response = process_request(environ)

    html = response.get_html()
    if VERSION_MAJOR == 3 and isinstance(html, str):
        html = bytes(html, 'utf-8')

    start_response(response.get_status(), response.get_header())

    return [html]

session_opts = {
    'session.type': 'file',
    'session.data_dir': '/tmp',
    'session.cookie_expires': True,
    'session.httponly': True,
    'session.key': 'prov.session.id',
}

application = SessionMiddleware(application, session_opts)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    srv = make_server('localhost', 8080, application)
    #srv = make_server( '0.0.0.0', 8080, application )
    srv.serve_forever()
