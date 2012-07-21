import collections
from urllib import quote

def _quote(value, plus):
    result = quote(value)
    if plus:
        result = result.replace('/', '%2F')

    return result

def expand_1(template, convertors, variables):
    subst_vars = {k: f(variables) for k, f in convertors.iteritems()}
    return template.format(**subst_vars)

def subst_level1(varname, variables):
    return variables[varname]

def parse_subst(expr):
    if expr[0] in '+.?&/;#':
        expansion, expr = expr[0], expr[1:]
    else:
        expansion = ''

    if expr[-1] == '*':
        explode, expr = '*', expr[:-1]
    else:
        explode = ''

    parts = []
    for part in expr.split(','):
        var_prefix = part.split(':', 1)
        if len(var_prefix) == 1:
            var, prefix = part, None
        else:
            var, prefix = var_prefix
            prefix = int(prefix)

        parts.append(var, prefix)

    return expansion, explode, parts

class ExpandSimple(object):
    def __init__(self, name, safe=""):
        vp = name.split(':', 1)
        if len(vp) == 2:
            name, prefix = vp
            prefix = int(prefix)
        else:
            prefix = None

        self.name = name
        self.prefix = prefix
        self.safe = safe

    @property
    def names(self):
        return [self.name]
        
    def expand(self, variables):
        value = variables.get(self.name)
        quote = lambda s: _quote(s, self.safe)
        if isinstance(value, collections.Mapping):
            return ','.join('{},{}'.format(k, quote(v)) for k, v in value.iteritems())
        elif isinstance(value, (str, unicode)):
            return quote(vars.get(self.name)[:self.prefix])


class ExpandFragment(object):
    def __init__(self, name):
        self.name = name

    def expand(self, variables):
        value = variables.get(self.name)
        

    
_SEPARATORS = dict(('?&', '#,', '.,'))

def expand_simple(name, explode, variables, safe=""):
    value = variables[name]
    

class Explode(object):
    def __init__(self, name):
        pass

    def subst(self, vars, expansion_type=""):
        quote = lambda s: _quote(s, expansion_type)
        separator = dict(('?&', '#,', '.,', "+,")).get(expansion_type, expansion_type)
        value = vars.get(self.name)
        if isinstance(value, collections.Mapping):
            exploded = separator.join('{}={}'.format(self.name, quote(v)) for v in value)
        elif isinstance(val, collections.Sequence):
            exploded = '{}={}'.format(self.name, separator.join(quote(v) for v in value))
            
        

def explode(type_, var, values):
    separator = {'?': '&', '&': '&', '#': ',', '.': ',', '/': '/', ';': ';'}.get(type_)
    val = var.get(values)
    if isinstance(val, collections.Mapping):
        exploded = separator.join('{}={}'.format(var.name, quote(v)) for v in val)
    elif isinstance(val, collections.Sequence):
        exploded = separator.join(quote(v) for v in val)

    return '{}{}'.format(type_, exploded)
        
    
        

            

def gen_subst(expr):
    val = None

    expansion, explode, parts = parse_subst(expr)
    while True:
        vars = yield val
        
    

def subst_single(mode, varname, variables):
    value = variables[varname]
    pass
    

def expand(template, variables):
    result = template
    for var, value in variables.iteritems():
        result = result.replace('{%s}' % var, quote(unicode(value)))

    return result
