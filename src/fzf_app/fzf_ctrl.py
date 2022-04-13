#!/usr/bin/env python

"""
Here we actually start fzf - with arguments dependent on the actual app params

We start using popen.
"""


"""
# Dev

# We rely on our input being modifed by hijack - which cannot be started within our process
# but fzfui must run within it. So we restart ourselves, hijack wrapped.
# We do this already here for fast startups, this restart adds just 20-30ms on my laptop:
"""
import sys

# from termcontrol import wrap_process, breakpoint, tc_set, tc
# d_tmp = wrap_process(cmd_mode=True, cmd_upper=True, ins_mode='/', cmd_signal=101,)
import os
import sys
import shutil
import subprocess as sp
import re
import json
import time
import shutil
import threading
from pygments import highlight
from pygments.lexers.data import JsonLexer, YamlLexer
from pygments.formatters.terminal import TerminalFormatter
from .app import get_app, write_file, read_file, exists, env, now
from ast import literal_eval
from operator import setitem
from fzf_app import preview
import tempfile

S = {'d_tmp': tempfile.mkdtemp('fzf-app')}
tc_set = None
# ------------------------------------------------------------------------------- Tools
fzf_default_binds = 'K:up,J:down,/:change-prompt(🔎 ),alt-e:change-prompt(  )'
env_prefix = 'FUI_'
env_app_mod = env_prefix + 'APP_MOD'
env_app_entry = env_prefix + 'APP_ENTRY'

os.environ['SHELL'] = '/bin/sh'
g = lambda k, v, d=None: getattr(k, v, d)
fn_tmp = lambda n: S['d_tmp'] + '/' + n
menu_by_name = lambda n: getattr(S['App'], n, None) if isinstance(n, str) else n
me = os.path.abspath(__file__)
me_flat = me.replace('/', '_')

Event = threading.Event

app = get_app(level='dbg')  # set log level

FZF = 'fzf'
# FZF = 'fui fzf-debug'


class cfg:
    dir = '%(HOME)s/.config/fzfui' % env


class form:
    pass


read_tmp = lambda n: read_file(fn_tmp(n))
write_tmp = lambda n, content: write_file(fn_tmp(n), content)


class menu:
    items_fmt = '%s'
    preview_max_item_width = 50  # overwrite
    actions_help_in_header = True
    actions = {}

    def items():
        return ['n.a. - provide items method in your child class']

    @classmethod
    def preview_info(menu, nr):
        r = S.get('cur_items')
        if not r:
            return 'n.a.'
        item = r['items'][int(nr)]
        # implemented?:
        p = g(menu, 'preview')
        if p:
            return p(item, r)
        return item


class confirm_delete(menu):
    preview_ipc = True
    offer_refresh = True
    callbacks = {'Yes': 'confirmed', 'No': 'cancel'}

    def items():
        return ['Yes', 'No']

    def preview_info(id):
        m = Hist.back(confirm_delete)
        c = S[m.__name__]
        return {'selected': c['sel'], 'items': selected_items(c), 'name': m.__name__}

    def preview(id, items):
        _ = add_fzf_view_items
        l = _(menu_by_name(items['name']), into=items, calc_widths=False)
        n = []
        n.append('Delete %s Item%s!' % (len(l), 's' if len(l) > 1 else ''))
        n += ['Hit Enter to confirm' if int(id) == 0 else 'Enter to cancel']
        [n.append(i) for i in l]
        n.append('')
        n.append('Details:')
        n.append(pretty(items['items']))
        return '\n'.join(n)

    @classmethod
    def confirmed(m):
        items = m.preview_info(0)
        menu = menu_by_name(items['name'])
        res = menu.delete(items)
        cache.invalidate(menu)
        # menu could deliver other subseq. view in it's delete func:
        return fzf.show(res or menu)

    def cancel():
        return fzf.show(Hist.back(confirm_delete))


class s:
    def __getattr__(self, k, v=None):
        return S.get(k, v)


# just for faster typing in pdb: ss.actions = S['actions']
ss = s()


nil = '\x01'


def col(s, c):
    return '\x1b[0;%sm%s\x1b[0m' % (c, s)


class FlatDict:
    """Allows dotted getitems, e.g. in format strings"""

    def __init__(self, d):
        self.d = d
        self.col = 30

    def __getitem__(self, k, d=''):
        l, plus = k.split('+', 1), ''
        if len(l) > 1:
            k, plus = l[0].strip(), l[1]

        self.col += 1
        res = self.d
        for part in k.split('.'):
            if part.isdigit():  # list
                try:
                    res = res[part]
                except Exception as ex:
                    res = nil
            else:
                res = res.get(part, nil)
            if res == nil:
                return col(d, self.col)
        if isinstance(res, list):
            res = ', '.join([str(i) for i in res])
        res = str(res) + plus
        return col(res, self.col)

    def __repr__(self):
        return json.dumps(self.d, indent=2, default=str)

    __str__ = __repr__


def cast_str(s):
    if not s:
        return ''
    if s[0] in ('[', '{'):
        return json.loads(s)
    return s.splitlines()


ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
ansi_stripped = lambda s: ansi_escape.sub('', s)


item_delimiter = '\u2001'


class Hist:
    cur = -1
    menus = []

    @classmethod
    def add(h, menu):
        m = h.menus
        if h.cur > -1 and m[h.cur] == menu:
            return
        h.cur += 1
        if len(m) > h.cur and m[h.cur] != menu:
            del m[h.cur :]
        m.insert(h.cur, menu)

    @classmethod
    def back(h, menu):
        m = h.menus
        if h.cur < 1:
            return m[0]
        h.cur -= 1
        return m[h.cur]

    @classmethod
    def fwd(h, menu):
        m = h.menus
        if len(m) < h.cur + 2:
            return menu
        h.cur += 1
        return m[h.cur]

    @classmethod
    def refresh(h, menu):
        return cache.invalidate(menu)


def human(s):
    return ' '.join([i.capitalize() for i in s.split('_')])


class fzf:
    class opts:
        def _get_preview_win_pos(menu, items):
            return 'right' if S['fits_width'] else 'down'

        def _get_height(menu, items):
            return '50%' if S['fits_width'] else '90%'

        def _get_header(menu, items):
            H = human(menu.__name__)
            h = g(menu, 'actions_help_in_header')
            if h:
                H += '\n' + actions_help(items)
            return H

        def _get_nth(menu, items):
            return '2..%s' % (menu.fzf_item_columns + 1)

        def _get_multi(menu, items):
            return g(menu, 'multi', True)

        # fmt:off
        ansi           = True
        color          = 'dark'
        cycle          = True
        delimiter      = item_delimiter
        header         = _get_header
        height         = _get_height
        border         = 'rounded'
        multi          = _get_multi
        preview_window = _get_preview_win_pos
        print0         = True
        read0          = True
        reverse        = True
        bind           = fzf_default_binds
        print_query    = True
        with_nth       = _get_nth
        prompt         = '  '
        # fmt:on

    def get_opts(menu, items):
        S['fits_width'] = True
        if g(menu, 'preview_max_item_width', 50) + menu.max_item_width > S['cols']:
            S['fits_width'] = False

        o = g(menu, 'opts', fzf.opts)
        r = []
        for k in dir(o):
            if callable(k) or k.startswith('_'):
                continue
            v = g(o, k)
            if callable(v):
                v = v(menu, items)
            K = k.replace('_', '-')
            if v == True:
                r.append('--%s' % K)
            elif not v:
                continue
            else:
                r.append('--%s="%s"' % (K, v))
        return r

    def add_actions(menu, items, opts):
        items['actions'] = A = {
            'H': {'type': 'nav', 'action': 'back', 'key': 'H', 'help': 'back'},
            'L': {'type': 'nav', 'action': 'fwd', 'key': 'L', 'help': 'fwd'},
        }
        if g(menu, 'offer_refresh'):
            A['R'] = {'type': 'nav', 'action': 'refresh', 'key': 'R', 'help': 'refresh'}
        a = g(menu, 'actions')
        if a:
            for k, v in a.items():
                v = menu_by_name(v)
                if hasattr(v, 'items'):
                    A[k] = {'type': 'menu', 'menu': v, 'key': k, 'help': v.__name__}
        [opts.append('--expect=%s' % k) for k in A]

    def show(menu):
        """menu either class or name"""
        if tc_set:
            # if run under termcontrol:
            tc_set(tc.cmd_mode)
        n, menu = name_and_cls(menu)
        if not menu:
            app.die('menu not defined', menu_name=n)
        Hist.add(menu)
        pid = os.getpid()
        items = S['cur_items'] = cache.get(menu)
        items = add_fzf_view_items(menu, into=items)
        # items = fetcher.fetch(n, wait=True)
        for f in g(menu, 'prefetch', ()):
            # fetcher.fetch(f)
            cache.get(menu_by_name(f), prefetch=True)

        fzf_items = items['fzf_items']
        opts = []
        fzf.add_actions(menu, items, opts)
        opts.extend(fzf.get_opts(menu, items))

        # we allow multiline -> \0 + --read0:
        opts = ' '.join(opts)
        fzf_items = '\\00'.join(fzf_items)  # fzf wants NULL sepped items. thats the way
        pc = preview.serialize_fzf_preview_cmd
        preview_cmd = pc(menu=menu, d_tmp=S['d_tmp'], name=n)
        cmd = f"{FZF} --preview='{preview_cmd}' {opts}"
        res = run_fzf_all_items(fzf_items, cmd)
        fzf.process_fzf_result(res, menu, items)

    def process_fzf_result(res, menu, items):
        i = items
        if res == ['']:
            sys.exit(130)
        H = S['history']
        i['qry'] = res[0]
        i['exp'] = res[1]
        i['sel'] = res[2:]
        # log('sel', res)
        a = i['actions'].get(i['exp'])
        if a:
            if a['type'] == 'nav':
                return fzf.show(g(Hist, a['action'])(menu))
            if a['type'] == 'menu':
                return fzf.show(a['menu'])
        cbs = g(menu, 'callbacks')
        if cbs and i['sel']:
            yes = i['sel'][0].split(item_delimiter)[1]
            f = cbs[yes]
            if isinstance(f, str):
                f = g(menu, f)
            return f()
        #  exit:
        [print(json.dumps(k, default=str)) for k in selected_items(i)]
        sys.exit(0)


def run_fzf_all_items(fzf_items, cmd):
    res = os.system(f'echo -ne "{fzf_items}" | {cmd}')  # .read()
    sys.exit(0)
    res = os.popen(f'echo -ne "{fzf_items}" | {cmd}').read()
    return res.split('\x00')


def selected_items(c):
    sel = [int(i.split(item_delimiter, 1)[0]) for i in c['sel'] if i]
    return [c['items'][k] for k in sel]


def name_and_cls(menu):
    if isinstance(menu, str):
        n = menu
        menu = menu_by_name(n)
    else:
        n = menu.__name__
    return n, menu


def to_fmt_str(s):
    add = ''
    if ':' in s:
        l = s.split(':', 1)
        l[1] = int(l[1]) + len(col('', 30))
        s, add = l[0], l[1]
    return '%%(%s)-%ss' % (s, add)


class cache:
    fetching = {}
    units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}

    def serialize(items):
        return str(items)

    def deserialize(s):
        return literal_eval(s)

    def expiry(cache_spec):
        ma = -1  # max age: never
        if len(cache_spec) == 1:
            return now() + 100
        ma = cache_spec[1]
        return int(ma) if ma.isdigit() else int(ma[:-1]) * cache.units[ma[-1]]

    def hirarchy(menu):
        # default: ram, no expiry
        impl = g(menu, 'cache')
        if not impl:
            impl = menu.cache = [cache.ram]
        impl = impl[0]
        hir = impl.first + [impl]
        return impl, hir

    def get(menu, prefetch=False):
        if menu in cache.fetching:
            if prefetch:
                return
            ev = cache.fetching.get(menu)
            if ev:
                ev.wait()
            return cache.get(menu)

        impl, hir = cache.hirarchy(menu)
        missed = []
        items = None
        try:
            for c in hir:
                items = c.has(menu)
                if items is not False:
                    return items
                missed.append(c)

            if not prefetch:
                items = cache.fetch_items(menu)
                return items
            # when main thread wants it, he'' block on that:
            cache.fetching[menu] = Event()
            t = threading.Thread
            t(target=cache.prefetch_async, args=(menu, hir), daemon=True).start()
        finally:
            # fill all we tried previously (the faster ones, e.g. ram for disk cache)
            if items is not None:
                [cache.set(c, menu, items) for c in missed]

    def set(impl, menu, items):
        impl.set(menu, items)
        return items

    def invalidate(menu):
        impl, hir = cache.hirarchy(menu)
        [c.invalidate(menu) for c in hir]
        return menu

    def prefetch_async(menu, hir):
        """not in main thread"""
        items = cache.fetch_items(menu)
        [cache.set(c, menu, items) for c in hir]
        ev = cache.fetching.pop(menu, 0)
        ev.set() if ev else 0

    def fetch_items(menu):
        items = menu.items()
        return {'ts_fetched': now(), 'items': items}


class ram_cache:
    # FIXME: check expiry here as well (against ts_fetched)
    first = []
    set = lambda menu, items: setitem(S, menu.__name__, items)
    invalidate = lambda menu: S.pop(menu.__name__, 0)

    def has(menu):
        h = S.get(menu.__name__, False)
        if h is False:
            return h
        return h if now() - h['ts_fetched'] < cache.expiry(menu.cache) else False


class disk_cache:
    first = [ram_cache]
    fn = lambda m: '%s/.cache/fzfui/menus/%s/%s' % (env['HOME'], me_flat, m.__name__)

    @classmethod
    def has(disk, menu):
        fn = disk.fn(menu)
        if not exists(fn):
            return False
        return cache.deserialize(read_file(fn))

    @classmethod
    def set(disk, menu, items):
        fn = disk.fn(menu)
        i = cache.serialize(items)
        write_file(fn, i, makedirs=True)

    @classmethod
    def invalidate(disk, menu):
        fn = disk.fn(menu)
        os.unlink(fn) if exists(fn) else 0


cache.ram = ram_cache
cache.disk = disk_cache

# class fetcher:
#     """Prefetch items"""

#     def fetch(menu, wait=False):
#         n, menu = name_and_cls(menu)
#         res = S.get(n)
#         if res:
#             if isinstance(res, Event):
#                 if wait:
#                     res.wait()
#                     return S[n]
#             return res
#         if wait:
#             return fetcher.fetch_async(n, menu)
#         ev = S[n] = threading.Event()
#         threading.Thread(
#             target=fetcher.fetch_async, args=(n, menu, ev), daemon=True
#         ).start()

#     def fetch_async(n, menu, ev=None):
#         items = cache.get(menu)
#         res = {'items': items}  # the prefetch call to get all
#         l = add_fzf_view_items(menu, into=res)
#         if not g(menu, 'max_item_width'):
#             k = max([(i, len(i)) for i in l], key=lambda j: j[1])
#             setattr(menu, 'max_item_width', len(ansi_stripped(k[0])))
#         S[n] = res
#         if ev:
#             ev.set()
#         return res


from inspect import signature


def add_fzf_view_items(menu, into, calc_widths=True):
    items = into['items']
    if not items:
        into['fzf_items'] = []
        menu.fzf_item_columns = 1
        return into

    fmt = g(menu, 'items_fmt', nil)
    # %s may be inhertied
    if fmt in (nil, '%s'):
        if isinstance(items[0], dict):
            fmt = [k for k, v in items[0].items() if not isinstance(v, dict)]
    fzf_item_columns = g(menu, 'fzf_item_columns', nil)
    if fzf_item_columns == nil:
        fzf_item_columns = menu.fzf_item_columns = 1
    if isinstance(fmt, list):
        menu.fzf_item_columns = len(fmt)
        fmt = item_delimiter.join([to_fmt_str(s) for s in fmt])
    if isinstance(fmt, str):
        fmt = lambda i, f=fmt: f % FlatDict(i)
    counted = zip(range(len(items)), items)
    d = item_delimiter
    # space needed at beginning, otherwise --read0 fails, no detection of item seps:
    into['fzf_items'] = l = [' %s%s%s' % (i, d, fmt(r)) for i, r in counted]
    if calc_widths:
        if not g(menu, 'max_item_width'):
            k = max([(i, len(i)) for i in l], key=lambda j: j[1])
            setattr(menu, 'max_item_width', len(ansi_stripped(k[0])))
    return into


def set_term_size():
    S['rows'], S['cols'] = [int(i) for i in os.popen('stty size', 'r').read().split()]


def actions_help(items):
    A = items['actions']
    return ' '.join(['%s:%s' % (a['key'], a['help']) for a in A.values()])


def cli_help(args, App=None):
    a = args[1] if len(args) > 0 else '<app>'
    me = os.path.basename(args[0])
    s = ['%s <app> [menu]' % a]
    s += ['\nApps:']
    for k in [k for k in os.listdir(cfg.dir + '/apps') if k.endswith('.py')]:
        s += ['* ' + k.rsplit('.py', 1)[0]]
    if App:
        s += ['\nMenus in %s:' % a]
        for k in [m for m in dir(App) if not m.startswith('_')]:
            v = g(App, k)
            if not isinstance(v, type):
                continue
            r = ''
            if k == App.entry:
                r = ' [*]'
            s += ['- ' + k + r]

    return '\n'.join(s)


def pretty(d, typ='json'):
    if typ == 'yaml':
        import yaml

        d = yaml.dump(d)
        return highlight(d, YamlLexer(), TerminalFormatter())
    if isinstance(d, str):
        return d
    d = json.dumps(d, indent=4, sort_keys=True, default=str)
    return highlight(d, JsonLexer(), TerminalFormatter())


class fifo(preview.fifo):
    def main_proc_query_listen():
        while True:
            with open(fifo.fns()['q']) as fd:
                query = fd.readline().strip()
                n, id = query.split(':', 1)
                menu = menu_by_name(n)
                res = menu.preview_info(id)
                # res = time.ctime()
                if isinstance(res, (dict, list, tuple)):
                    res = json.dumps(res, default=str)
            fifo.write('a', res)

            # with open(fifo.fns()['a'], 'w') as fdanswer:
            #    fdanswer.write(res)

    def main_proc_fifo_start_listen():
        for t, fn in fifo.fns().items():
            if exists(fn):
                os.unlink(fn)
            os.mkfifo(fn)
        threading.Thread(target=fifo.main_proc_query_listen, daemon=True).start()


def main(App):
    S['App'] = App
    # if len(args) > 1 and args[1] == 'preview':
    #     S['d_tmp'], n, id = args[2], args[3], args[4]
    #     menu = menu_by_name(n)
    #     args = (id,)
    #     if g(menu, 'preview_ipc'):
    #         args += (fifo.preview_proc_query(n, id),)
    #     p = menu.preview(*args)
    #     print(p)
    #     sys.exit(0)
    # if '-h' in args or '--help' in args:
    #     sys.exit(cli_help(sys.argv, App))
    App.confirm_delete = confirm_delete
    S['history'] = Hist
    set_term_size()
    # for termcontrol:
    if not exists(fn_tmp('io')):
        os.mkdir(fn_tmp('io'))
    preview.fifo.d_tmp = S['d_tmp']
    fifo.main_proc_fifo_start_listen()
    try:
        fzf.show(env.get(env_app_entry, App.entry))
    finally:
        pass
