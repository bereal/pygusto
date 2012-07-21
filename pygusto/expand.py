import collections
import re
import urllib
from itertools import chain
from functools import partial

RESERVED = ":/?#[]@!$&'()*+,;="


class ExpandVar(object):
    def __init__(self, name, prefix):
        self.name = name
        self.prefix = prefix
        
    def __call__(self, variables, visitor):
        name = self.name
        value = variables.get(name)
        if isinstance(value, collections.Mapping):
            return visitor.expand_dict(name, value)
        elif isinstance(value, (str, unicode)):
            return visitor.expand_string(name, value[:self.prefix])
        elif isinstance(value, collections.Sequence):
            return visitor.expand_list(name, value)
        else:
            raise ValueError("Cannot expand {}".format(value))

class ExpandExplode(object):
    def __init__(self, name):
        self.name = name
        
    def expand_explode(self, variables, visitor):
        name = self.name
        value = variables.get(name)
        if isinstance(value, collections.Mapping):
            return visitor.explode_dict(name, value)
        elif isinstance(value, (str, unicode)):
            raise ValueError("Can't explode string: {}".format(value))
        elif isinstance(value, collections.Sequence):
            return visitor.explode_list(name, value)
    

class ExpandDict(object):
    class Flat(object):
        def expand_dict(self, name, value):
            quote = self.quote
            pairs = ((k, quote(v)) for k, v in value.iteritems())
            return self.sep_expand.join(chain(*pairs))

    class AsKeyval(object):
        def expand_dict(self, name, value):
            quote = self.quote
            pairs = ((k, quote(v)) for k, v in value.iteritems())
            val = self.sep_expand.join(chain(*pairs))
            return "{}{}{}".format(name, self.sep_keyval, val)

    
    class ExplodeAsKeyval(object):
            def explode_dict(self, name, value):
                quote = self.quote
                sep = self.sep_keyval
                parts = ('{}{}{}'.format(k, sep, quote(v)) for k, v in value)
                return self.sep_explode.join(parts)

    class ExplodeFlat(object):
        def explode_dict(self, name, value):
            quote = self.quote
            pairs = ((k, quote(v)) for k, v in value.iteritems())
            return self.sep_explode.join(chain(*pairs))

        
class ExpandList(object):
    class AsKeyval(object):
        def expand_list(self, name, value):
            sep = self.sep_keyval
            quote = self.quote
            parts = ('{}{}{}'.format(name, sep, quote(v)) for v in value)
            return self.sep_explode.join(parts)

    class Flat(object):
        def expand_list(self, name, value):
            quote = self.quote
            return self.sep_explode.join(quote(v) for v in value)
        

    class ExplodeAsKeyval(object):
        def explode_list(self, name, value):
            quote = self.quote
            sep = self.sep_keyval
            parts = (''.join((name, sep, quote(v))) for v in value)
            return self.sep_explode.join(parts)

    class ExplodeFlat(object):
        def explode_list(self, name, value):
            quote = self.quote
            return self.sep_explode.join(quote(v) for v in value)

class ExpandValue(object):
    class Flat(object):
        def expand_string(self, name, value):
            return self.quote(value)

    class AsKeyval(object):
        def expand_string(self, name, value):
            return ''.join((name, self.sep_keyval, value))
    

def st_partial(*args, **kw):
    return staticmethod(partial(*args, **kw))


class BaseExpand(object):
    def __init__(self, parts):
        self.parts = list(parts)

    def __call__(self, variables):
        expanded_parts = (p(variables, self) for p in self.parts)
        body = self.sep_explode.join(expanded_parts)
        return "{}{}".format(self.expansion_prefix, body)

    @property
    def names(self):
        return set(p.name for p in self.parts)

    
    
class SimpleExpand(BaseExpand,
                   ExpandValue.Flat,
                   ExpandDict.Flat,
                   ExpandDict.ExplodeAsKeyval,
                   ExpandList.Flat,
                   ):
    expansion_prefix = ""
    sep_keyval = "="
    sep_explode = ','
    sep_expand = ','
    quote = staticmethod(urllib.quote)
    

    
    
PARAM_RE = re.compile(r"{([^\}]+)}")

    
class _Template(object):
    def __init__(self, template_str, compiled_expands):
        self._template = template_str
        self._expands = compiled_expands
        self._vars = set.union(*[e.names for e in compiled_expands.values()])

    @property
    def vars(self):
        return list(self._vars)

    def __str__(self):
        return self._orig_template
        
    def expand(self, variables):
        def repl(match):
            expr = match.group(1)
            return self._expands[expr](variables)

        return PARAM_RE.sub(repl, self._template)
    
        
PREFIX_TO_EXPAND = {
    
    }


def parse_part(s):
    if s.endswith('*'):
        return ExpandExplode(name=s[:-1])

    prefix = None
    for i, v in enumerate(s.split(':', 1)):
        if i:
            prefix = int(v)
        else:
            name = v
            
    return ExpandVar(name, prefix)

def parse_template(template):
    expands = {}
    for expr in PARAM_RE.findall(template):
        parts = (parse_part(p) for p in expr.split(','))
        expands[expr] = SimpleExpand(parts)

    return _Template(template, expands)
