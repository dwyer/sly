import logging
import re


def echo(yy):
    print yy.text


def generate(tokens):
    _tokens = []
    for pattern, token in tokens:
        try:
            pattern = re.compile(pattern)
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
