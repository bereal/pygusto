import glob
import json
import os
import os.path
from pygusto.expand import expand

def test_all():
    tests_path = os.path.join('rfc-tests', '*.json')
    max_level = int(os.environ.get('LEVEL', 4))
    for path in glob.iglob(tests_path):
        with open(path) as f:
            tests_data = json.load(f)
            for name, testcase in tests_data.iteritems():
                level = int(testcase.get('level', 4))
                if level > max_level: continue
                variables = testcase['variables']

                for template, expected in testcase['testcases']:
                    check.description = "%s: %s" % (name, template)
                    yield check, name, variables, template, expected
                

def check(name, variables, template, expected):
    result = expand(template, variables)
    msg = "%s, expected %s, got %s" % (name, expected, result)

    if isinstance(expected, (str, unicode)):
        assert (result == expected), msg
    elif isinstance(expected, list):
        assert result in expected, msg
    else:
        assert not result, msg

