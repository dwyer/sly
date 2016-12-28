import logging
import re

EMBEDS_RE = re.compile(r'\{([A-Za-z]\w*)\}')


def echo(yy):
    print yy.text


def _expand_aliases(aliases):
    lookup_table = {}

    def lookup(name):
        if name not in lookup_table:
            pattern = aliases[name]
            for embedded_name in EMBEDS_RE.findall(pattern):
                pattern = pattern.replace(
                    '{%s}' % embedded_name, lookup(embedded_name))
            lookup_table[name] = pattern
        return lookup_table[name]

    for name, pattern in aliases.items():
        lookup(name)
    return lookup_table


def _expand_pattern(pattern, aliases):
    for name in EMBEDS_RE.findall(pattern):
        pattern = pattern.replace('{%s}' % name, aliases[name])
    return pattern


def generate(tokens, aliases=None):
    if aliases is None:
        aliases = {}
    aliases = _expand_aliases(aliases)
    _tokens = []
    for pattern, token in tokens:
        try:
            pattern = re.compile(_expand_pattern(pattern, aliases))
        except:
            logging.error('invalid regular expression: %r', pattern)
            exit(1)
        _tokens.append((pattern, token))
    tokens = _tokens

    def lexer(yy):
        while yy.in_:
            match = None
            for pattern, token in tokens:
                match = pattern.match(yy.in_)
                if not match:
                    continue
                yy.text = match.group(0)
                yy.in_ = yy.in_[len(yy.text):]
                if callable(token):
                    token = token(yy)
                elif token:
                    yy.lval = yy.text
                if token:
                    return token
                break # if token is None, get another
            if not match:
                print 'no match:', repr(yy.in_)
                exit(1)

    return lexer
