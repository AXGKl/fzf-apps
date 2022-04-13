"""
Process is the Preview Process.


We do not want to import expensive libs, so main app has to format all for us, we only
print it out.


"""


import fzf_app

psep = fzf_app.preview_args_sep


def serialize_fzf_preview_cmd(menu, d_tmp, name):
    """only function called from the main process - kept here for better transparency
    about deserializiation"""
    return 'fui ' + psep.join(('', d_tmp, name, '{1}'))


class fifo:
    """
    Running the communication with the main process from the preview process.


    The main process counterpart is a descendant of this:
    It listens on our queries and replies from the main proc, formatted already - we
    simply print it out, and not load expensive formatter libs.

    Remember:

    This proc is simply killed and restarted with another item nr by FZF,
    every time when the user tem selection changes or fzf exits.


    TODO: build in support for answers which are
    
    - static
    - streaming (fzf can handle that - displays what we print, in the preview window)
    
    """

    d_tmp = None  # must be set by app and preview prog

    def fns():
        return {'q': fifo.d_tmp + '/fifo.q', 'a': fifo.d_tmp + '/fifo.a'}

    def write(which, s):
        with open(fifo.fns()[which], 'w') as fd:
            fd.write(s + '\n')

    def preview_proc_query(menu_name, id):
        fifo.write('q', '%s:%s' % (menu_name, id))

        with open(fifo.fns()['a']) as fdanswer:
            while True:
                s = fdanswer.readline().strip()
                if not s:
                    break
                print(s)


import os

# debug:
def n(*msg, c=[-1], **kw):
    c[0] += 1
    nr, a = c[0], ' '.join(msg)
    os.system(f'notify-send "preview {nr} {a} {kw}"')


def main(argv):
    _, fifo.d_tmp, name, itemnr = argv[1].split(psep)
    k = fifo.d_tmp
    return fifo.preview_proc_query(name, itemnr)
