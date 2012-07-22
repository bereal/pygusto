import collections
import re
import urllib
from bridge import Bridge
from itertools import chain

RESERVED = ":/?#[]@!$&'()*+,;="

######################################################################
# By parts of an expression I mean pieces between commas, e.g.
# Simple part: "varname"
# Prefix part: "varname:3"
# Explode part: "varname*"
######################################################################

class BasePart(object):
    '''
    A base class for all parts;
    dispatches the calls according to the data tyle
    '''
    def __init__(self, name):
        self.name = name

    def __call__(self, variables):
        name = self.name
        value = variables.get(self.name)
        if value is None:
            return None
        if isinstance(value, collections.Mapping):
            if not value: return None
            return self.on_dict(name, value)
        elif isinstance(value, (str, unicode)):
            return self.on_string(name, value)
        elif isinstance(value, collections.Sequence):
            if not value: return None
            return self.on_list(name, value)
        else:
            return self.on_string(name, str(value))


class PartSingle(BasePart, Bridge(on_string='context.expand_string',
                                  on_list='context.expand_list',
                                  on_dict='context.expand_dict')):
    pass


class PartPrefix(BasePart):
    def __init__(self, name, prefix):
        self.name = name
        self.prefix = prefix

    def on_dict(self, name, value):
        raise ValueError("Cannot expand {}:{} as {}".format(name, self.prefix, value))

    on_list = on_dict

    def on_string(self, name, value):
        return self.context.expand_string(name, value[:self.prefix])


class PartExplode(BasePart, Bridge(on_list='context.explode_list',
                                   on_dict='context.explode_dict',
                                   on_string='context.expand_string')):

    pass


class BaseExpansionMixin():
    '''
    Expansion utility functions.
    This is supposed to be used as a mixin in a class where
    all the required values are defined:

    reserved_chars : what not to escape in values
    sep_expand     : separator between simple expand elements
    sep_explode    : separator between explode elements (e.g. '&' for queries)
    sep_keyval     : separator between name and value (e.g. '=')
    sep_parts      : what to put between expanded parts (almost always == sep_explode)
    '''
    def quote(self, val):
        return urllib.quote(val, safe=self.reserved_chars)

    def _explode_keyval(self, name, value):
        if value or self.show_empty_keyvalue:
            return ''.join((name, self.sep_keyval, self.quote(value)))

        return name

    def explode_dict(self, name, value):
        '''
        {"face": {"eyes": "green", "hair": "gray"}} => "eyes=green&color=gray"
        '''
        explode = self._explode_keyval
        parts = (explode(k, v) for k, v in value.iteritems())
        return self.sep_explode.join(parts)
    

class FlatMixin(BaseExpansionMixin):
    def expand_dict(self, name, value):
        '''
        {"face": {"eyes": "green", "hair": "gray"}} => "eyes,green,color,gray"
        '''
        quote = self.quote
        pairs = ((k, quote(v)) for k, v in value.iteritems())
        return self.sep_expand.join(chain(*pairs))

    def expand_list(self, name, value):
        '''
        {"colors": ["red", "green", "blue"]} => "red,green,blue"
        '''
        quote = self.quote
        return self.sep_expand.join(quote(v) for v in value)

    def explode_list(self, name, value):
        '''
        {"colors": ["red", "green", "blue"]} => "red/green/blue"
        '''
        quote = self.quote
        return self.sep_explode.join(quote(v) for v in value)

    def expand_string(self, name, value):
        '''
        {"key": "value"} => "value"
        '''
        return self.quote(value)


class KeyvalMixin(BaseExpansionMixin):

    def expand_dict(self, name, value):
        '''
        {"face": {"eyes": "green", "hair": "gray"}} => "face=eyes,green,color,gray"
        '''
        quote = self.quote
        pairs = ((k, quote(v)) for k, v in value.iteritems())
        val = self.sep_expand.join(chain(*pairs))
        return ''.join((name, self.sep_keyval, val))


    def expand_list(self, name, value):
        '''
        {"colors": ["red", "green", "blue"]} => "colors=red,green,blue"
        '''
        quote = self.quote
        parts = (quote(v) for v in value)
        return ('{}{}{}'.format(name, self.sep_keyval, self.sep_expand.join(parts)))


    def explode_list(self, name, value):
        '''
        {"colors": ["red", "green", "blue"]} => "colors=red&colors=green&colors=blue"
        '''
        parts = (self._explode_keyval(name, v) for v in value)
        return self.sep_explode.join(parts)

    def expand_string(self, name, value):
        '''
        {"key": "value"} => "key=value"
        '''
        if value is None:
            return None
        return self._explode_keyval(name, value)


class BaseExpansion(object):
    def __init__(self):
        self.parts = []

    def add_parts(self, parts):
        for p in parts:
            p.context = self
            self.parts.append(p)

    def __call__(self, variables):
        for p in self.parts:
            p.context = self
        expanded_parts = (p(variables) for p in self.parts)
        expanded_parts = [p for p in expanded_parts if p is not None]
        if not expanded_parts:
            return ''
        body = self.sep_parts.join(expanded_parts)

        return "{}{}".format(self.expansion_prefix, body)

    @property
    def names(self):
        return set(p.name for p in self.parts)

    show_empty_keyvalue = True

    
class SimpleExpansion(BaseExpansion, FlatMixin):
    expansion_prefix = ""
    sep_keyval = "="
    sep_explode = sep_parts = ','
    sep_expand = ','
    reserved_chars = ''


class ReservedExpansion(SimpleExpansion):
    reserved_chars = RESERVED


class PathExpansion(BaseExpansion, FlatMixin):
    expansion_prefix = '/'
    sep_keyval = '='
    sep_explode = sep_parts = '/'
    sep_expand = ','
    reserved_chars = ''


class FormQueryContExpansion(BaseExpansion, KeyvalMixin):
    expansion_prefix = '&'
    sep_keyval = '='
    sep_explode = sep_parts = '&'
    sep_expand = ','
    reserved_chars = ''


class FormQueryExpansion(FormQueryContExpansion):
    expansion_prefix = '?'


class PathParamExpansion(BaseExpansion, KeyvalMixin):
    expansion_prefix = ';'
    sep_keyval = '='
    sep_explode = sep_parts = ';'
    sep_expand = ','
    reserved_chars = ''
    show_empty_keyvalue = False


class LabelExpansion(BaseExpansion, FlatMixin):
    expansion_prefix = '.'
    sep_keyval = '='
    sep_explode = sep_parts = '.'
    sep_expand = ','
    reserved_chars = ''


class FragmentExpansion(BaseExpansion, FlatMixin):
    expansion_prefix = '#'
    sep_keyval = '='
    sep_explode = ','
    sep_expand = sep_parts = ','
    reserved_chars = '/!,.;'
    show_empty_keyvalue = False


_VAR_RE=r'[a-zA-Z0-9_.%]+(\*|:[0-9]+)?'
PARAM_RE = re.compile(r"{{([\+\?&/.;#]?({0},)*{0})}}".format(_VAR_RE))

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

    name = None
    for i, v in enumerate(s.split(':', 1)):
        if i:
            return PartPrefix(name, int(v))
        else:
            name = v

    return PartSingle(name)


PREFIX_TO_EXPANSION = {
    '+': ReservedExpansion,
    '/': PathExpansion,
    '&': FormQueryContExpansion,
    '?': FormQueryExpansion,
    ';': PathParamExpansion,
    '.': LabelExpansion,
    '#': FragmentExpansion
    }


def parse_template(template):
    check = PARAM_RE.sub('', template)
    if '{' in check or '}' in check:
        raise ValueError("Syntax error")
    expands = {}
    for expr in PARAM_RE.findall(template):
        expr = expr[0]
        try:
            cls = PREFIX_TO_EXPANSION[expr[0]]
            expr_body = expr[1:]
        except KeyError:
            cls = SimpleExpansion
            expr_body = expr

        parts = (parse_part(p) for p in expr_body.split(','))
        if parts:
            inst = cls()
            inst.add_parts(parts)
            expands[expr] = inst

    return _Template(template, expands)


def expand(template_str, variables):
    try:
        return parse_template(template_str).expand(variables)
    except:
        import traceback
        traceback.print_exc()
        return None
