import collections
import re
import urllib
from bridge import Bridge
from itertools import chain

RESERVED = ":/?#[]@!$&'()*+,;="

class BasePart(object):
    def __init__(self, name):
        self.name = name

    def __call__(self, variables):
        name = self.name
        value = variables[self.name]
        if isinstance(value, collections.Mapping):
            return self.on_dict(name, value)
        elif isinstance(value, (str, unicode)):
            return self.on_string(name, value)
        elif isinstance(value, collections.Sequence):
            return self.on_list(name, value)
        else:
            raise ValueError("Cannot expand {}".format(value))

class PartSingle(BasePart, Bridge(on_string='context.expand_string',
                                  on_list='context.expand_list',
                                  on_dict='context.expand_dict')):
    pass

class PartPrefix(BasePart):
    def __init__(self, name, prefix):
        self.name = name
        self.prefix = prefix

    def on_string(self, name, value):
        return self.context.expand_string(name, value[:self.prefix])

class PartExplode(BasePart, Bridge(on_list='context.explode_list',
                                   on_dict='context.explode_dict')):

    def on_string(self, name, value):
        raise ValueError("Cannot explode string {}".format(value))

class ExpansionMixin(object):
    def quote(self, val):
        return urllib.quote(val, safe=self.reserved_chars)

    def _explode_keyval(self, name, value):
        if value or self.show_empty_keyvalue:
            return ''.join((name, self.sep_keyval, self.quote(value)))

        return name
    
    def expand_dict_flat(self, name, value):
        quote = self.quote
        pairs = ((k, quote(v)) for k, v in value.iteritems())
        return self.sep_expand.join(chain(*pairs))

    def expand_dict_keyval(self, name, value):
        quote = self.quote
        pairs = ((k, quote(v)) for k, v in value.iteritems())
        val = self.sep_expand.join(chain(*pairs))
        return self._explode_keyval(name, val)

    def explode_dict_keyval(self, name, value):            
        explode = self._eplode_keyval
        parts = (explode(k, v) for k, v in value)
        return self.sep_explode.join(parts)

    def explode_dict_flat(self, name, value):
        quote = self.quote
        pairs = ((k, quote(v)) for k, v in value.iteritems())
        return self.sep_explode.join(chain(*pairs))

    def expand_list_keyval(self, name, value):
        quote = self.quote
        parts = (quote(v) for v in value)
        return ('{}{}{}'.format(name, self.sep_keyval, self.sep_expand.join(parts)))

    def expand_list_flat(self, name, value):
        quote = self.quote
        return self.sep_expand.join(quote(v) for v in value)

    def explode_list_keyval(self, name, value):
        parts = (self._explode_keyval(name, v) for v in value)
        return self.sep_explode.join(parts)

    def explode_list_flat(self, name, value):
        quote = self.quote
        return self.sep_explode.join(quote(v) for v in value)

    def expand_string_flat(self, name, value):
        return self.quote(value)

    def expand_string_keyval(self, name, value):
        return self._explode_keyval(name, value)

class BaseExpansion(object):
    def __init__(self, parts):
        self.parts = list(parts)

    def add_parts(self, parts):
        for p in parts:
            parts.context = self
            self.parts.append(p)

    def __call__(self, variables):
        for p in self.parts:
            p.context = self
        expanded_parts = (p(variables) for p in self.parts)
        body = self.sep_parts.join(expanded_parts)
        if body:
            return "{}{}".format(self.expansion_prefix, body)
        return ""

    @property
    def names(self):
        return set(p.name for p in self.parts)

    show_empty_keyvalue = True
    
def ExpansionBridge(default='flat', **kw):
    actions = ('expand_dict', 'expand_list', 'expand_string',
               'explode_dict', 'explode_list')
    opts = dict({k: '{}_{}'.format(k, default) for k in actions})
    opts.update({k: '{}_{}'.format(k, v) for k, v in kw.iteritems()})
    return type('_ExpansionBridge', (BaseExpansion, ExpansionMixin, Bridge(**opts)), {})

class SimpleExpansion(ExpansionBridge(expand_dict='keyval')):
    expansion_prefix = ""
    sep_keyval = "="
    sep_explode = sep_parts = ','
    sep_expand = ','
    reserved_chars = ''

class ReservedExpansion(SimpleExpansion):
    reserved_chars = RESERVED

class PathExpansion(ExpansionBridge(explode_dict='keyval',
                                    expand_dict='keyval')):
    expansion_prefix='/'
    sep_keyval = '='
    sep_explode = sep_parts =  '/'
    sep_expand = ','
    reserved_chars = '/'

class FormQueryContExpansion(ExpansionBridge('keyval')):

    expansion_prefix = '&'
    sep_keyval = '='
    sep_explode = sep_parts = '&'
    sep_expand = ','
    reserved_chars = ''

class FormQueryExpansion(FormQueryContExpansion):
    expansion_prefix = '?'

class PathParamExpansion(ExpansionBridge('keyval')):
    expansion_prefix = ';'
    sep_keyval = '='
    sep_explode = sep_parts = ';'
    sep_expand = ','
    reserved_chars = ''
    show_empty_keyvalue = False

class LabelExpansion(ExpansionBridge(expand_dict='keyval')):
    expansion_prefix = '.'
    sep_keyval = '='
    sep_explode = sep_parts =  '.'
    sep_expand = ','
    reserved_chars = ''

class FragmentExpansion(ExpansionBridge(explode_dict='keyval')):
    expansion_prefix = '#'
    sep_keyval = '='
    sep_explode = ';'
    sep_expand = sep_parts = ','
    reserved_chars = '/!'
    show_empty_keyvalue = False
                                        

PARAM_RE = re.compile(r"{([^\}]+)}")

class _Template(object):
    def __init__(self, template_str, compiled_expands):
        self._template = template_str
        self._expands = compiled_expands
        vars = set()
        for e in compiled_expands.values():
            vars.update(e.names)
        self._vars = vars

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
        return PartExplode(name=s[:-1])

    prefix = None
    name = None
    for i, v in enumerate(s.split(':', 1)):
        if i:
            return PartPrefix(name, int(prefix))
        else:
            name = v

    return PartSingle(name)

PREFIX_TO_EXPANSION = {
    '+': ReservedExpansion,
    '/': PathExpansion,
    '&' : FormQueryContExpansion,
    '?': FormQueryExpansion,
    ';': PathParamExpansion,
    '.': LabelExpansion,
    '#': FragmentExpansion
    }

def parse_template(template):
    expands = {}
    for expr in PARAM_RE.findall(template):
        try:
            cls = PREFIX_TO_EXPANSION[expr[0]]
            expr_body = expr[1:]
        except KeyError:
            cls = SimpleExpansion
            expr_body = expr

        parts = (parse_part(p) for p in expr_body.split(','))
        if parts:
            expands[expr] = cls(parts)

    return _Template(template, expands)


def expand(template_str, variables):
     return parse_template(template_str).expand(variables)
