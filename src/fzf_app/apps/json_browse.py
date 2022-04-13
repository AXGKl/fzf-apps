from fzf_app import menu, notify

R = [0, 'root']
C = [0, 'entry']


class menu(menu):
    offer_refresh = False
    preview_ipc = False
    preview_key = 'name'
    fetch_filter = lambda _: True

    @classmethod
    def preview(m, item, full):
        return 'foo'

    @classmethod
    def items(m):
        return ['foo', 'bar']


class App:
    def __getattr__(self, k, v=None):
        return S.get(k, v)


def make_struct_app(entry):
    entry_cls = type(entry, (menu,), {})
    app = type('App', (App,), {'entry': entry, entry: entry_cls})
    return app


def make_list_app(l):
    breakpoint()  # FIXME BREAKPOINT


def make_dict_app(l):
    App = make_struct_app(entry='root')
    return App


def make_app(dict_or_list):
    if isinstance(dict_or_list, dict):
        return make_dict_app(dict_or_list)
    else:
        return make_list_app(dict_or_list)
