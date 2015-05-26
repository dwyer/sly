import re
import sys


def echo(yy):
    print yy.text


def generate(tokens):
    tokens = [(re.compile(pattern), action) for pattern, action in tokens]

    def lexer(yy):
        while yy.in_:
            match = None
            for pattern, action in tokens:
                match = pattern.match(yy.in_)
                if not match:
                    continue
                yy.text = match.group(0)
                yy.in_ = yy.in_[len(yy.text):]
                if callable(action):
                    token = action(yy)
                else:
                    token = action
                    yy.lval = yy.text
                if token:
                    return token
                break # if token is None, get another
            if not match:
                print 'no match:', repr(yy.in_)
                exit(1)

    return lexer
