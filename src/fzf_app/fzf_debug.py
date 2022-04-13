import os, sys, json
from .app import write_file

D = '/tmp/fzf_debug_out'


def run(argv):
    os.makedirs(D, exist_ok=True)
    r = []
    [r.extend(l.split('\x00')) for l in sys.stdin]
    m = json.dumps({'items': r, 'argv': argv}, indent=4)
    print(m, file=sys.stderr)
    write_file(D + '/invoke.json', m)
    # now call the preview command
    pcmd = [i for i in argv if i.startswith('--preview=')][0].split('=', 1)[1]
    os.system(pcmd.replace('{1}', '0'))
    return ''
