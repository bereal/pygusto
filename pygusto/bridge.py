
class AttrDispatch(object):
    def __init__(self, *path):
        self.path = path
        
    def __get__(self, inst, cls):
        result = inst
        for p in self.path:
            result = getattr(result, p)

        return result
            

def Bridge(**mapping):
    class_dict = {}
    for k, v in mapping.iteritems():
        descr = AttrDispatch(*v.split('.'))
        class_dict[k] = descr

    return type('_Bridge', (), class_dict)
