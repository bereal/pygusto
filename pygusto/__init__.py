from urllib import quote

def expand(template, variables):
    result = template
    for var, value in variables.iteritems():
        result = result.replace('{%s}' % var, quote(unicode(value)))

    return result
