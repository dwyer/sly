#-*-coding:utf-8-*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import functools
import sys
import warnings

warnings.simplefilter('always', DeprecationWarning)


def _deprecated(repl):

    def dec(func):

        @functools.wraps(func)
        def new_func(*args, **kwargs):
            warnings.warn(
                "Call to deprecated function %s. Use %s instead." % (
                    func.__name__,
                    repl.__name__ if repl else repl,
                ),
                category=DeprecationWarning, stacklevel=2)
            # warnings.simplefilter('default', DeprecationWarning)
            return func(*args, **kwargs)

        return new_func

    return dec


@_deprecated(None)
def identity(s):
    return s

def empty(_):
    return []

@_deprecated(empty)
def empty_list(_):
    return []

def nth(n):
    return lambda s: s[n]

def select(*xs):
    return lambda s: [s[x] for x in xs]

def append(*xs):
    return lambda s: reduce(list.__add__, [s[x] for x in xs])

def append_all(s):
    return reduce(list.__add__, s)


def appl(f, *idxs):
    if idxs:

        def wrapper(s):
            try:
                args = [s[x] for x in idxs]
                return f(*args)
            except TypeError:
                print(f, args, file=sys.stderr)
                raise

        return wrapper
    return lambda s: f(*s)


@_deprecated(appl)
def apply_all(f):
    return lambda s: f(*s)

@_deprecated(appl)
def apply_ns(f, *xs):
    return lambda s: f(*[s[x] for x in xs])

first = nth(0)
second = nth(1)
third = nth(2)
