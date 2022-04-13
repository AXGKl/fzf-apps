"""
No unnecessary imports if we are called by fzf for previews

"""
import sys
from fzf_app import preview_args_sep

is_preview = lambda a: a[1].startswith(preview_args_sep)
is_debug_fzf = lambda a: a[1] == 'fzf-debug'


def main():
    argv = sys.argv

    if len(argv) == 1:
        hint = 'try give me e.g. a json file or a directory'
        from .app import get_app

        return get_app().die('Require data to display', hint=hint)

    # debug: with this as first arg we do not start fzf but send a preview hit only:
    if argv[1] == 'mf':
        from fzf_app import fzf_ctrl

        fzf_ctrl.FZF = 'fui fzf-debug'
        argv.pop(1)

    if is_preview(argv):
        from fzf_app import preview

        f = preview.main

    elif is_debug_fzf(argv):
        from fzf_app import fzf_debug

        f = fzf_debug.run

    else:
        from fzf_app import app

        f = app.run

    r = f(argv)

    if isinstance(r, str):
        print(r)


# if __name__ == '__main__':
#     # main('droplet_list')
#     main()
#
#     # class create_droplet(doctl_api_menu):
#     #     size = 's-1vcpu-1gb'
#     #     region = 'fra1'
#     #     image = 'Arch-Linux-x86_64-cloudimg-20210415.20050.qcow2'
#     #     ssh_keys = 'gk'
#     #     name = 'droplet'
#
#     # doctl compute droplet create --image ubuntu-20-04-x64 --size s-1vcpu-1gb --region nyc1 example.com
