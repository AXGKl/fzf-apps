import sys, time
from functools import partial
import os

env = os.environ
exists = os.path.exists
dirname = os.path.dirname
now = lambda: 1000 * int(time.time())
t0 = now()


def read_file(fn, dflt=None):
    if not exists(fn):
        return dflt
    with open(fn) as fd:
        return fd.read()


def write_file(fn, content, makedirs=False):
    d = dirname(fn)
    os.makedirs(d, exist_ok=True) if makedirs else 0
    with open(fn, 'w') as fd:
        fd.write(str(content))


def fmt(s, width, col, bold):
    b = '1' if bold else '0'
    s = str(s).ljust(width)
    return f'\x1b[{b};38;5;{col}m{s}\x1b[0m' if log.color else s


coll = {'notify': 0, 'dbg': 239, 'info': 2, 'warn': 125, 'error': 196}


class log:
    level = 'info'
    color = True

    def out(msg, *args, level=None, **kw):
        fmt_, isnotif = fmt, False
        if level == 'notify':
            fmt_ = lambda s, *_, **__: s
            isnotif = True
            timeout = kw.pop('timeout', 5)
        if log.level != 'dbg' and level == 'dbg':
            return
        msg = fmt_(msg, 60, 7, True)
        level = fmt_(
            f'[{level}]', 8, coll[level], False if level in ('dbg', 'info') else True
        )
        if args:
            kw['args'] = args
        kws = '  '.join([f'{k}:{v}' for k, v in kw.items()])
        dt = fmt_(now() - t0, 6, 237, False)
        s = f'{dt} {level} {msg} {kws}'
        if isnotif:
            os.system(f'notify-send -t {timeout} {level} "{s}" ')
        else:
            print(s, file=sys.stderr)


[
    setattr(log, ll, partial(log.out, level=ll))
    for ll in ['dbg', 'info', 'notify', 'warn', 'error']
]


def get_logger(level='info'):
    log.level = level
    return log


def notif(s):
    os.system(f'notify-send fui "{s}" ')


def get_app(level='info'):
    app = get_logger(level)
    app.die = lambda *a, **kw: (app.error(*a, **kw), sys.exit(1))
    return app


import sys, os
import importlib
import time

apps_dir = os.path.dirname(__file__) + '/apps'


def run(argv):
    from fzf_app import fzf_ctrl

    app = get_app()

    arg1 = argv[1]
    app.dbg('Starting up')
    if os.path.isdir(arg1):
        app.die('dir browsing not yet...')
        # from .apps.dir_browse import App
        #
        # App.start_dir = fn
        # fzf_app.main(App)
        # start_app(dir_browse.App)
    elif arg1 + '.py' in os.listdir(apps_dir):
        sys.path.insert(0, apps_dir)
        mod = importlib.import_module(arg1)
        return fzf_ctrl.main(mod.App)
    else:
        s = read_file(arg1)
        if s is None:
            app.die('Not found', file=arg1)

        if not s or not s[0] in ['{', '[']:
            app.die('Require json content', have=s[:100] + '...', fn=arg1)
        from .apps import json_browse
        import json

        try:
            j = json.loads(s)
        except Exception as ex:
            app.die('Cannot deserialize', content=s[:100] + '...', fn=arg1, exc=ex)
        app = json_browse.make_app(j)
        return fzf_ctrl.main(app)
