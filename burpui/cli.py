# -*- coding: utf8 -*-
"""
Burp-UI is a web-ui for burp backup written in python with Flask and
jQuery/Bootstrap

.. module:: burpui.cli
    :platform: Unix
    :synopsis: Burp-UI CLI module.

.. moduleauthor:: Ziirish <hi+burpui@ziirish.me>
"""
import os
import sys
import click
import subprocess

from .app import create_app

DEBUG = os.environ.get('BUI_DEBUG')
if DEBUG and DEBUG.lower() in ['true', 'yes', '1']:
    DEBUG = True
else:
    DEBUG = False

VERBOSE = os.environ.get('BUI_VERBOSE')
if VERBOSE:
    try:
        VERBOSE = int(VERBOSE)
    except ValueError:
        VERBOSE = 0
else:
    VERBOSE = 0

app = create_app(
    conf=os.environ.get('BUI_CONFIG'),
    verbose=VERBOSE,
    logfile=os.environ.get('BUI_LOGFILE'),
    debug=DEBUG,
    gunicorn=False
)

if app.config['WITH_SQL']:
    from .ext.sql import db
    from flask_migrate import Migrate

    mig_dir = os.getenv('BUI_MIGRATIONS')
    if mig_dir:
        migrate = Migrate(app, db, mig_dir)
    else:
        migrate = Migrate(app, db)


@app.cli.command()
@click.option('-b', '--backend', default='BASIC',
              help='User Backend (default is BASIC).')
@click.option('-p', '--password', help='Password to assign to user.',
              default=None)
@click.option('-a', '--ask', default=False, is_flag=True,
              help='If no password is provided and this flag is enabled, '
                   'you\'ll be prompted for one, else a random one will be '
                   'generated.')
@click.option('-v', '--verbose', default=False, is_flag=True,
              help='Add extra debug messages.')
@click.argument('name')
def create_user(backend, password, ask, verbose, name):
    """Create a new user."""
    click.echo(click.style('[*] Adding \'{}\' user...'.format(name), fg='blue'))
    try:
        handler = getattr(app, 'uhandler')
    except AttributeError:
        handler = None

    if not handler or len(handler.backends) == 0 or \
            backend not in handler.backends:
        click.echo(click.style('[!] No authentication backend found', fg='red'))
        sys.exit(1)

    back = handler.backends[backend]

    if back.add_user is False:
        click.echo(click.style("[!] The '{}' backend does not support user "
                               "creation".format(backend), fg='red'))
        sys.exit(2)

    if not password:
        if ask:
            import getpass
            password = getpass.getpass()
            confirm = getpass.getpass('Confirm: ')
            if password != confirm:
                click.echo(click.style("[!] Passwords missmatch", fg='red'))
                sys.exit(3)
        else:
            import random

            alphabet = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLM" \
                       "NOPQRSTUVWXYZ"
            pw_length = 8
            mypw = ""

            for i in range(pw_length):
                next_index = random.randrange(len(alphabet))
                mypw += alphabet[next_index]
            password = mypw
            click.echo(
                click.style(
                    '[+] Generated password: {}'.format(password),
                    fg='blue'
                )
            )

    success, message, _ = back.add_user(name, password)
    click.echo(click.style(
        '[+] Success: {}{}'.format(
            success, ' -> {}'.format(message) if verbose and message else ''
        ),
        fg='green' if success else 'red')
    )


@app.cli.command()
@click.argument('language')
def init_translation(language):
    """Initialize a new translation for the given language."""
    os.system('pybabel extract -F babel.cfg -k __ -k lazy_gettext -o messages.pot burpui')
    os.system('pybabel init -i messages.pot -d burpui/translations -l {}'.format(language))
    os.unlink('messages.pot')


@app.cli.command()
def update_translation():
    """Update translation files."""
    os.system('pybabel extract -F babel.cfg -k __ -k lazy_gettext -o messages.pot burpui')
    os.system('pybabel update -i messages.pot -d burpui/translations')
    os.unlink('messages.pot')


@app.cli.command()
def compile_translation():
    """Compile translations."""
    os.system('pybabel compile -f -d burpui/translations')


@app.cli.command()
@click.option('-b', '--burp-conf-cli', 'bconfcli', default=None,
              help='Burp client configuration file')
@click.option('-s', '--burp-conf-serv', 'bconfsrv', default=None,
              help='Burp server configuration file')
@click.option('-c', '--client', default='bui',
              help='Name of the burp client that will be used by Burp-UI '
                   '(defaults to "bui")')
@click.option('-h', '--host', default='::1',
              help='Address of the status server (defaults to "::1")')
@click.option('-r', '--redis', default=None,
              help='Redis URL to connect to')
@click.option('-d', '--database', default=None,
              help='Database to connect to for persistent storage')
@click.option('-n', '--dry', is_flag=True,
              help='Dry mode. Do not edit the files but display changes')
def setup_burp(bconfcli, bconfsrv, client, host, redis, database, dry):
    """Setup burp client for burp-ui."""
    if app.vers != 2:
        click.echo(
            click.style(
                'Sorry, you can only setup the Burp 2 client',
                fg='red'
            ),
            err=True
        )
        sys.exit(1)

    if not app.standalone:
        click.echo(
            click.style(
                'Sorry, only the standalone mode is supported',
                fg='red'
            ),
            err=True
        )
        sys.exit(1)

    from .misc.parser.utils import Config
    from .app import get_redis_server
    import difflib
    import tempfile

    orig = source = None
    conf_orig = []
    if dry:
        try:
            with open(app.conf.options.filename) as fil:
                conf_orig = fil.readlines()
        except:
            pass

        orig = source = app.conf.options.filename
        (_, temp) = tempfile.mkstemp()
        app.conf.options.filename = temp

    if not app.conf.lookup_section('Burp2', source):
        app.conf._refresh(True)
    if (database or redis) and not app.conf.lookup_section('Production', source):
        app.conf._refresh(True)

    def _edit_conf(key, val, attr):
        if val and (((key not in app.conf.options['Burp2']) or
                    (key in app.conf.options['Burp2'] and
                    val != app.conf.options['Burp2'][key])) and
                    getattr(app.client, attr) != val):
            app.conf.options['Burp2'][key] = val
            app.conf.options.write()
            app.conf._refresh(True)

    def _color_diff(line):
        if line.startswith('+'):
            return click.style(line, fg='green')
        elif line.startswith('-'):
            return click.style(line, fg='red')
        elif line.startswith('^'):
            return click.style(line, fg='blue')
        return line

    _edit_conf('bconfcli', bconfcli, 'burpconfcli')
    _edit_conf('bconfsrv', bconfsrv, 'burpconfsrv')

    if redis:
        if ('redis' not in app.conf.options['Production'] or
            'redis' in app.conf.options['Production'] and
            app.conf.options['Production']['redis'] != redis) and \
                app.redis != redis:
            app.conf.options['Production']['redis'] = redis

        rhost, rport, _ = get_redis_server(app)
        DEVNULL = open(os.devnull, 'wb')
        ret = subprocess.call(['/bin/nc', '-z', '-w5', str(rhost), str(rport)], stdout=DEVNULL, stderr=subprocess.STDOUT)

        if ret == 0:
            app.conf.options['Production']['celery'] = 'true'

            app.conf.options['Production']['storage'] = 'redis'

            app.conf.options['Production']['cache'] = 'redis'
        else:
            click.echo(
                click.style(
                    'Unable to contact the redis server, disabling it',
                    fg='yellow'
                )
            )
            app.conf.options['Production']['storage'] = 'default'
            app.conf.options['Production']['cache'] = 'default'
            if app.use_celery:
                app.conf.options['Production']['celery'] = 'false'

        app.conf.options.write()
        app.conf._refresh(True)

    if database:
        if ('database' not in app.conf.options['Production'] or
            'database' in app.conf.options['Production'] and
            app.conf.options['Production']['database'] != database) and \
                app.database != database:
            app.conf.options['Production']['database'] = database
            app.conf.options.write()
            app.conf._refresh(True)

    if dry:
        temp = app.conf.options.filename
        app.conf.options.filename = orig
        after = []
        try:
            with open(temp) as fil:
                after = fil.readlines()
            os.unlink(temp)
        except:
            pass
        diff = difflib.unified_diff(conf_orig, after, fromfile=orig, tofile='{}.new'.format(orig))
        out = ''
        for line in diff:
            out += _color_diff(line)
        click.echo_via_pager(out)

    bconfcli = bconfcli or app.conf.options['Burp2'].get('bconfcli') or \
        getattr(app.client, 'burpconfcli')
    bconfsrv = bconfsrv or app.conf.options['Burp2'].get('bconfsrv') or \
        getattr(app.client, 'burpconfsrv')

    if not os.path.exists(bconfsrv):
        click.echo(
            click.style(
                'Unable to locate burp-server configuration, aborting!',
                fg='red'
            ),
            err=True
        )
        sys.exit(1)

    bconfcli = app.conf.options['Burp2']['bconfcli']
    dest_bconfcli = bconfcli
    if not os.path.exists(bconfcli):
        clitpl = """
mode = client
port = 4971
status_port = 4972
server = ::1
password = abcdefgh
cname = bui
protocol = 1
pidfile = /tmp/burp.client.pid
syslog = 0
stdout = 1
progress_counter = 1
network_timeout = 72000
server_can_restore = 0
cross_all_filesystems=0
ca_burp_ca = /usr/sbin/burp_ca
ca_csr_dir = /etc/burp/CA-client
ssl_cert_ca = /etc/burp/ssl_cert_ca.pem
ssl_cert = /etc/burp/ssl_cert-bui-client.pem
ssl_key = /etc/burp/ssl_cert-bui-client.key
ssl_key_password = password
ssl_peer_cn = burpserver
include = /home
exclude_fs = sysfs
exclude_fs = tmpfs
nobackup = .nobackup
exclude_comp=bz2
exclude_comp=gz
"""

        if dry:
            (_, dest_bconfcli) = tempfile.mkstemp()
        with open(dest_bconfcli, 'w') as confcli:
            confcli.write(clitpl)

    parser = app.client.get_parser()

    confcli = Config()
    data, path, _ = parser._readfile(dest_bconfcli, insecure=True)
    parsed = parser._parse_lines(data, path, 'srv')
    confcli.add_file(parsed, dest_bconfcli)
    confcli.set_default(dest_bconfcli)

    if confcli.get('cname') != client:
        confcli['cname'] = client
    if confcli.get('server') != host:
        confcli['server'] = host

    if confcli.dirty:
        if dry:
            (_, dstfile) = tempfile.mkstemp()
        else:
            dstfile = bconfcli
        parser.store_conf(confcli, dstfile, insecure=True, source=bconfcli)
        if dry:
            before = []
            after = []
            try:
                with open(bconfcli) as fil:
                    before = fil.readlines()
            except:
                pass
            try:
                with open(dstfile) as fil:
                    after = fil.readlines()
                os.unlink(dstfile)
            except:
                pass

            if dest_bconfcli != bconfcli:
                os.unlink(dest_bconfcli)

            diff = difflib.unified_diff(before, after, fromfile=bconfcli, tofile='{}.new'.format(bconfcli))
            out = ''
            for line in diff:
                out += _color_diff(line)
            click.echo_via_pager(out)

    confsrv = Config()
    data, path, _ = parser._readfile(bconfsrv, insecure=True)
    parsed = parser._parse_lines(data, path, 'srv')
    confsrv.add_file(parsed, bconfsrv)
    confsrv.set_default(bconfsrv)

    if host not in ['::1', '127.0.0.1']:
        bind = confsrv.get('status_address')
        if (bind and bind not in [host, '::', '0.0.0.0']) or not bind:
            click.echo(
                click.style(
                    'It looks like your burp server is not exposing it\'s '
                    'status port in a way that is reachable by Burp-UI!',
                    fg='yellow'
                )
            )
            click.echo(
                click.style(
                    'You may want to set the \'status_address\' setting with '
                    'either \'{}\', \'::\' or \'0.0.0.0\' in the {} file '
                    'in order to make Burp-UI work'.format(host, bconfsrv),
                    fg='blue'
                )
            )

    if 'restore_client' not in confsrv:
        confsrv['restore_client'] = client
    else:
        restore = confsrv.getlist('restore_client')
        if client not in restore:
            confsrv['restore_client'].append(client)

    confsrv['monitor_browse_cache'] = True

    if confsrv.dirty:
        if dry:
            (_, dstfile) = tempfile.mkstemp()
        else:
            dstfile = bconfsrv
        parser.store_conf(confsrv, dstfile, insecure=True, source=bconfsrv)
        if dry:
            before = []
            after = []
            try:
                with open(bconfsrv) as fil:
                    before = fil.readlines()
            except:
                pass
            try:
                with open(dstfile) as fil:
                    after = fil.readlines()
                os.unlink(dstfile)
            except:
                pass
            diff = difflib.unified_diff(before, after, fromfile=bconfsrv, tofile='{}.new'.format(bconfsrv))
            out = ''
            for line in diff:
                out += _color_diff(line)
            click.echo_via_pager(out)

    bconfagent = os.path.join(parser.clientconfdir, client)
    if not os.path.exists(bconfagent):

        agenttpl = """
password = abcdefgh
"""

        if not dry:
            with open(bconfagent, 'w') as confagent:
                confagent.write(agenttpl)
        else:
            before = []
            after = ['{}\n'.format(x) for x in agenttpl.splitlines()]
            diff = difflib.unified_diff(before, after, fromfile='None', tofile=agenttpl)
            out = ''
            for line in diff:
                out += _color_diff(line)
            click.echo_via_pager(out)

    else:
        confagent = Config()
        data, path, _ = parser._readfile(bconfagent, insecure=True)
        parsed = parser._parse_lines(data, path, 'cli')
        confagent.add_file(parsed, bconfagent)
        confagent.set_default(bconfagent)

        if confagent.get('password') != confcli.get('password'):
            click.echo(
                click.style(
                    'It looks like the passwords in the {} and the {} files '
                    'missmatch. Burp-UI will not work properly untill you fix '
                    'this'.format(bconfcli, bconfagent),
                    fg='yellow'
                )
            )