import re
import sys


def echo(yy):
    print yy.text


def generate(tokens):

    tokens = [(re.compile(pattern), action) for pattern, action in tokens]

    def lexer(yy):
        while yy.in_:
            match = False
            for pattern, action in tokens:
                match = pattern.match(yy.in_)
                if match:
                    yy.text = match.group(0)
                    yy.in_ = yy.in_[yy.leng:]
                    if callable(action):
                        token = action(yy)
                    else:
                        token = action
                    if token:
                        return token
                    # if token is None, get another
                    break
            if not match:
                print 'no match:', repr(yy.in_)
                exit(1)

    return lexer
