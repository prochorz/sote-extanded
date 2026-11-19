"""Minimal glTF 2.0 reader / writer for the Guri model (harness/guri/): one .gltf file, its buffer and PNG images
embedded as data URIs. Enough for what the generator writes and Blender exports back: nodes (name, TRS, children,
mesh), meshes of triangle primitives (POSITION, COLOR_0, TEXCOORD_0, indices, material), materials (name, base
colour factor, baseColorTexture → image PNG bytes).

    doc = {'nodes': [{'name', 'translation', 'rotation', 'scale', 'children', 'mesh'}],
           'scene': [root node indices],
           'meshes': [[{'pos': (N,3), 'col': (N,4) 0..1, 'uv': (N,2), 'idx': (M,3), 'material': i}]],
           'materials': [{'name', 'png': bytes or None, 'factor': (4,)}]}
"""
import base64, json, struct
import numpy as np

F32, U8, U16, U32 = 5126, 5121, 5123, 5125
ARRAY, ELEMENT = 34962, 34963
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
DTYPE = {F32: '<f4', U8: 'u1', U16: '<u2', U32: '<u4'}
URI = 'data:application/octet-stream;base64,'


def write(path, doc):
    buf, views, accs = bytearray(), [], []

    def view(b, target=None):
        buf.extend(bytes(-len(buf) % 4))
        v = {'buffer': 0, 'byteOffset': len(buf), 'byteLength': len(b)}
        if target: v['target'] = target
        buf.extend(b); views.append(v); return len(views) - 1

    def acc(a, ctype, typ, target, minmax=False):
        a = np.ascontiguousarray(a, DTYPE[ctype])
        x = {'bufferView': view(a.tobytes(), target), 'componentType': ctype, 'count': int(a.shape[0]), 'type': typ}
        if ctype == U8: x['normalized'] = True
        if minmax:
            x['min'] = [float(v) for v in a.reshape(a.shape[0], -1).min(0)]
            x['max'] = [float(v) for v in a.reshape(a.shape[0], -1).max(0)]
        accs.append(x); return len(accs) - 1

    images, textures, mats = [], [], []
    for m in doc['materials']:
        g = {'name': m['name'], 'pbrMetallicRoughness': {'baseColorFactor': list(m.get('factor', (1, 1, 1, 1))),
                                                          'metallicFactor': 0.0, 'roughnessFactor': 1.0},
             'extensions': {'KHR_materials_unlit': {}}}
        if m.get('png'):
            images.append({'uri': 'data:image/png;base64,' + base64.b64encode(m['png']).decode()})
            textures.append({'source': len(images) - 1, 'sampler': 0})
            g['pbrMetallicRoughness']['baseColorTexture'] = {'index': len(textures) - 1}
        mats.append(g)
    meshes = []
    for prims in doc['meshes']:
        ps = []
        for p in prims:
            at = {'POSITION': acc(p['pos'], F32, 'VEC3', ARRAY, True), 'COLOR_0': acc(p['col'], F32, 'VEC4', ARRAY)}
            if p.get('uv') is not None: at['TEXCOORD_0'] = acc(p['uv'], F32, 'VEC2', ARRAY)
            ps.append({'attributes': at, 'indices': acc(np.asarray(p['idx']).reshape(-1), U16, 'SCALAR', ELEMENT),
                       'material': p['material'], 'mode': 4})
        meshes.append({'primitives': ps})
    nodes = []
    for n in doc['nodes']:
        g = {'name': n['name']}
        for k in ('translation', 'rotation', 'scale'):
            if n.get(k) is not None: g[k] = [float(v) for v in n[k]]
        if n.get('children'): g['children'] = list(n['children'])
        if n.get('mesh') is not None: g['mesh'] = n['mesh']
        nodes.append(g)
    j = {'asset': {'version': '2.0', 'generator': doc.get('generator', 'harness/guri/guri_model.py')},
         'extensionsUsed': ['KHR_materials_unlit'],
         'scene': 0, 'scenes': [{'nodes': list(doc['scene'])}], 'nodes': nodes, 'meshes': meshes,
         'materials': mats, 'accessors': accs, 'bufferViews': views,
         'buffers': [{'byteLength': len(buf), 'uri': URI + base64.b64encode(bytes(buf)).decode()}]}
    if images:
        j.update(images=images, textures=textures, samplers=[{'magFilter': 9728, 'minFilter': 9728}])
    with open(path, 'w') as f: json.dump(j, f, indent=1)


def _data(uri):
    assert uri.startswith('data:'), 'only embedded (data URI) buffers and images are read'
    return base64.b64decode(uri.split(',', 1)[1])


def read(path):
    j = json.load(open(path))
    bufs = [_data(b['uri']) for b in j['buffers']]

    def acc(i):
        a = j['accessors'][i]; v = j['bufferViews'][a['bufferView']]
        n, t = NCOMP[a['type']], a['componentType']
        size = np.dtype(DTYPE[t]).itemsize
        stride = v.get('byteStride', n * size)
        raw = bufs[v['buffer']]; off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        out = np.array([np.frombuffer(raw, DTYPE[t], n, off + stride * k) for k in range(a['count'])])
        if a.get('normalized'): out = out / {U8: 255.0, U16: 65535.0}[t]
        return out.astype(float) if t == F32 or a.get('normalized') else out

    mats = []
    for m in j.get('materials', []):
        pb = m.get('pbrMetallicRoughness', {}); png = None
        if 'baseColorTexture' in pb:
            img = j['images'][j['textures'][pb['baseColorTexture']['index']]['source']]
            png = _data(img['uri']) if 'uri' in img else bufs[0][
                j['bufferViews'][img['bufferView']].get('byteOffset', 0):][:j['bufferViews'][img['bufferView']]['byteLength']]
        mats.append({'name': m.get('name', ''), 'png': png, 'factor': tuple(pb.get('baseColorFactor', (1, 1, 1, 1)))})
    meshes = []
    for m in j.get('meshes', []):
        ps = []
        for p in m['primitives']:
            assert p.get('mode', 4) == 4, 'triangles only'
            at = p['attributes']; pos = acc(at['POSITION'])
            col = acc(at['COLOR_0']) if 'COLOR_0' in at else np.ones((len(pos), 4))
            if col.shape[1] == 3: col = np.hstack([col, np.ones((len(col), 1))])
            ps.append({'pos': pos, 'col': col, 'uv': acc(at['TEXCOORD_0']) if 'TEXCOORD_0' in at else None,
                       'idx': acc(p['indices']).reshape(-1, 3).astype(int), 'material': p.get('material')})
        meshes.append(ps)
    nodes = [{'name': n.get('name', ''), 'translation': n.get('translation'), 'rotation': n.get('rotation'),
              'scale': n.get('scale'), 'matrix': n.get('matrix'), 'children': n.get('children', []),
              'mesh': n.get('mesh')} for n in j.get('nodes', [])]
    return {'nodes': nodes, 'scene': j['scenes'][j.get('scene', 0)]['nodes'], 'meshes': meshes, 'materials': mats}
