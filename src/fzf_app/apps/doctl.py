import sys

from fzf_app.fzf_ctrl import os, cast_str, menu, human, pretty, cache, form


def doctl(*args, **kw):
    f = ['doctl', '-o', 'json'] + [str(i) for i in args]
    res = os.popen(' '.join(f)).read()
    f = cast_str(res.strip())
    return f


class doctl_api_menu(menu):
    offer_refresh = True
    preview_ipc = True
    preview_key = 'name'
    fetch_filter = lambda i: True

    @classmethod
    def preview(m, item, full):
        rs = {item[m.preview_key] + ' (%s)' % human(m.__name__): item}
        return pretty(rs, 'yaml')

    @classmethod
    def items(m):
        res = doctl(*m.fetch_cmd)
        return [i for i in res if m.fetch_filter(i)]


class App:
    entry = 'droplet_list'

    class volume_list(doctl_api_menu):
        items_fmt = [
            'size_gigabytes+5GB:7',
            'name:20',
            'filesystem_type:5',
            'description',
            'created_at',
            'droplet_ids',
            'id',
        ]
        fetch_cmd = 'compute', 'volume', 'list'
        fetch_filter = lambda i: i.pop('region', 1)
        actions = {'D': 'droplets'}

    class droplet_list(doctl_api_menu):
        items_fmt = [
            'memory+MB:9',
            'size.price_monthly',
            'created_at',
            'id',
            'name:20',
            'tags',
        ]
        # prefetch = ['volume_list']
        fetch_cmd = 'compute', 'droplet', 'list'
        fetch_filter = lambda i: i.pop('region', 1)
        actions = dict(V='volume_list', A='droplet_add', X='confirm_delete')
        cache = [cache.disk, '24h']

        def delete(selected):
            res = []
            for i in selected['items']:
                res.append(doctl('compute', 'droplet', 'delete', i['id'], '-f'))

    class droplet_pick_image(doctl_api_menu):
        multi = False
        cache = [cache.disk, '24h']
        preview_key = 'description'
        items_fmt = [
            'distribution:12',
            'slug:20',
            'type:20',
            'min_disk_size+GB',
            'created_at',
            'description:27',
            'id',
        ]
        fetch_cmd = ['compute', 'image', 'list-distribution']
        fetch_filter = lambda i: i['status'] == 'available'
        actions = {'enter': 'droplet_pick_size'}

        @classmethod
        def items(m):
            """combine custom and stock ones"""
            res = doctl(*m.fetch_cmd)
            l = list(m.fetch_cmd)
            l[-1] = l[-1].replace('-distribution', '')

            def fix_custom(i):
                i['description'] = i['name']
                return i

            res += [fix_custom(d) for d in doctl(*l)]
            return [i for i in res if m.fetch_filter(i)]

    class droplet_pick_size(doctl_api_menu):
        multi = False
        cache = [cache.disk, '24h']
        preview_key = 'description'
        items_fmt = [
            'slug:20',
            'memory+MB:10',
            'vcpus+cpu:2',
            'disk+GB:5',
            'price_monthly+$:5',
            'description:27',
            'regions',
        ]
        fetch_cmd = ['compute', 'size', 'list']
        fetch_filter = lambda i: i['available'] == True
        actions = {'enter': 'droplet_pick_region'}

    class droplet_pick_region(doctl_api_menu):
        multi = False
        cache = [cache.disk, '24h']
        preview_key = 'name'
        items_fmt = ['slug:5', 'name:20', 'features']
        fetch_cmd = ['compute', 'region', 'list']
        fetch_filter = lambda i: i.get('available') == True
        actions = {'enter': 'droplet_pick_ssh_keys'}

    class droplet_pick_ssh_keys(doctl_api_menu):
        cache = [cache.disk, '24h']
        preview_key = 'name'
        items_fmt = ['name:10', 'id', 'fingerprint', 'public-key']
        fetch_cmd = ['compute', 'ssh-key', 'list']
        actions = {'enter': 'droplet_set_hostname'}

    class droplet_add(form):
        l = 'image', 'size', 'region', 'ssh_keys'
        fields = ['droplet_pick_' + n for n in l]
