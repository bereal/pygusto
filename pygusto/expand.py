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

    def __call__(self, variables, visitor):
        name = self.name
        value = variables.get(name)
        if isinstance(value, collections.Mapping):
            return visitor.explode_dict(name, value)
        elif isinstance(value, (str, unicode)):
            raise ValueError("Can't explode string: {}".format(value))
        elif isinstance(value, collections.Sequence):
            return visitor.explode_list(name, value)

def ExpandActions(**opts):
    def quote(self, val):
        return urllib.quote(val, safe=self.reserved_chars)

    def expand_dict_flat(self, name, value):
        quote = self.quote
        pairs = ((k, quote(v)) for k, v in value.iteritems())
        return self.sep_expand.join(chain(*pairs))

    def expand_dict_keyval(self, name, value):
        quote = self.quote
        pairs = ((k, quote(v)) for k, v in value.iteritems())
        val = self.sep_expand.join(chain(*pairs))
        return "{}{}{}".format(name, self.sep_keyval, val)

    def explode_dict_keyval(self, name, value):
        quote = self.quote
        sep = self.sep_keyval
        parts = ('{}{}{}'.format(k, sep, quote(v)) for k, v in value)
        return self.sep_explode.join(parts)

    def explode_dict_flat(self, name, value):
        quote = self.quote
        print value
        pairs = ((k, quote(v)) for k, v in value.iteritems())
        return self.sep_explode.join(chain(*pairs))

    def expand_list_keyval(self, name, value):
        sep = self.sep_keyval
        quote = self.quote
        parts = ('{}{}{}'.format(name, sep, quote(v)) for v in value)
        return self.sep_explode.join(parts)

    def expand_list_flat(self, name, value):
        quote = self.quote
        return self.sep_explode.join(quote(v) for v in value)

    def explode_list_keyval(self, name, value):
        quote = self.quote
        sep = self.sep_keyval
        parts = (''.join((name, sep, quote(v))) for v in value)
        return self.sep_explode.join(parts)

    def explode_list_flat(self, name, value):
        quote = self.quote
        return self.sep_explode.join(quote(v) for v in value)

    def expand_string_flat(self, name, value):
        return self.quote(value)

    def expand_string_keyval(self, name, value):
        return ''.join((name, self.sep_keyval, value))

    class_dict = {'quote': quote}
    for action in ('expand_string', 'expand_list', 'expand_dict'):
        value = opts.get(action, 'flat')
        class_dict[action] = locals()['{}_{}'.format(action, value)]

    return type('_Expander', (), class_dict)

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
                   ExpandActions(expand_dict='keyval')):
    expansion_prefix = ""
    sep_keyval = "="
    sep_explode = ','
    sep_expand = ','
    reserved_chars = ''

class ReservedExpand(SimpleExpand):
    reserved_chars = RESERVED

class PathExpand(BaseExpand,
                 ExpandActions(explode_dict='keyval')):
    expansion_prefix='/'
    sep_keyval = '='
    sep_explode = '/'
    sep_expand = ','
    reserved_chars = '/'


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

PREFIX_TO_EXPANSION = {
    '+': ReservedExpand,
    '/': PathExpand,
    }

def parse_template(template):
    expands = {}
    for expr in PARAM_RE.findall(template):
        try:
            cls = PREFIX_TO_EXPANSION[expr[0]]
            expr_body = expr[1:]
        except KeyError:
            cls = SimpleExpand
            expr_body = expr

        parts = (parse_part(p) for p in expr_body.split(','))
        expands[expr] = cls(parts)

    return _Template(template, expands)


def expand(template_str, variables):
     return parse_template(template_str).expand(variables)
