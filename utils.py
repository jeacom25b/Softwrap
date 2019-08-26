class DummyObj(dict):
    def __init__(self, **kargs):
        super().__init__(self)
        for key, value in zip(kargs.keys(), kargs.values()):
            self[key] = value

    def __getattr__(self, item):
        return self.get(item, None)

    def __setattr__(self, key, value):
        self[key] = value

def n_ring(v, n=300):
    seen_verts = {v}
    curr_layer = [v]
    stop = False
    x = 0
    while curr_layer:
        new_layer = []
        for vert in curr_layer:
            for other in (edge.other_vert(vert) for edge in vert.link_edges):
                if other not in seen_verts:
                    seen_verts.add(other)
                    new_layer.append(other)
                    x += 1
                    yield other
                    if x >= n:
                        return
        curr_layer, new_layer = new_layer, curr_layer
        new_layer.clear()
