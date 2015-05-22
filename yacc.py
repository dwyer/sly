import collections
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Symbol: pass
class AcceptSymbol(Symbol): pass
class EndSymbol(Symbol): pass
class EmptySymbol(Symbol): pass

ACCEPT_SYMBOL = '$accept'
END_SYMBOL = '$end'
EMPTY_SYMBOL = '%empty'

ACCEPT_ACTION = 'action'
REDUCE_ACTION = 'reduce'
SHIFT_ACTION = 'shift'


class Parser(object):

    def __init__(self, grammar, start=None, lexer=None, in_=None):
        self.start = start or (grammar[0][0] if grammar else None)
        self.grammar = [(ACCEPT_SYMBOL, (self.start, END_SYMBOL), None)]
        for nt, omega, aux in grammar:
            self.grammar.append((nt, tuple(omega), aux))
        self.rules = []
        self.rules_lookup = {}
        for nt, omega, _ in self.grammar:
            self.rules_lookup[(nt, omega)] = len(self.rules)
            self.rules.append((nt, omega))
        self._lexer = lexer
        self.in_ = in_ or ''
        self._text = ''
        self.column = 0
        self.leng = 0
        self.lineno = 0
        self.lval = None
        self.ssp = []
        self.vsp = []
        self.token = None

    def action(self, i, x):
        action = {}
        for nt, a, b in self.states[i]:
            if nt == ACCEPT_SYMBOL and not b and x == END_SYMBOL:
                action[ACCEPT_ACTION] = True
            elif not b and x in self.follow(nt):
                if REDUCE_ACTION in action:
                    logger.error('reduce/reduce conflict')
                    exit(1)
                action[REDUCE_ACTION] = self.rules_lookup[(nt, a)]
            elif b and b[0] == x:
                if SHIFT_ACTION in action:
                    logger.error('shift/shift conflict')
                    exit(1)
                action[SHIFT_ACTION] = True
        return action

    def closure(self, i):
        j = list(i)
        while 1:
            done = True
            for _, _, beta in j:
                for nt, omega in self.rules:
                    if beta and beta[0] == nt:
                        item = (nt, (), omega)
                        if item not in j:
                            j.append(item)
                            done = False
            if done:
                break
        return j

    def get_goto(self, I, x):
        J = []
        for n, p in self.items:
            nt, rule = self.rules[n]
            alpha = rule[:p]
            if not alpha:
                continue
            beta = rule[p:]
            if x == alpha[-1] and (nt, alpha[:-1], (x,) + beta) in I:
                J.append((nt, alpha, beta))
        return self.closure(J)

    def error(self):
        logger.error('syntax error')
        exit(1)

    def first(self, x):
        if not hasattr(self, '_first'):
            self._first = {}
        if x not in self._first:
            self._first[x] = set()
            if x not in self.nonterminals:
                self._first[x].add(x)
                return self._first[x]
            rules = []
            for nt, rule in self.rules:
                if nt == x:
                    rules.append(rule)
                    if not rule:
                        self._first[x].add(EMPTY_SYMBOL)
            for rule in rules:
                for s in rule:
                    if s not in self.nonterminals:
                        self._first[x].add(s)
                        break
                    second = self._first[x] if s == x else self.first(s)
                    self._first[x] = self._first[x].union(second)
                    if EMPTY_SYMBOL not in second:
                        break
        return self._first[x]

    def follow(self, x):
        if not hasattr(self, '_follow'):
            self._follow = {}
            for nt, rule in self.rules:
                if nt not in self._follow:
                    self._follow[nt] = set()
                for i in xrange(len(rule) - 1):
                    s = rule[i]
                    t = rule[i+1]
                    if s not in self._follow:
                        self._follow[s] = set()
                    if t in self.nonterminals:
                        self._follow[s] = \
                            self._follow[s].union(self.first(t))
                        self._follow[s] = \
                            self._follow[s].difference({EMPTY_SYMBOL})
                    else:
                        self._follow[s].add(t)
        return self._follow[x]

    @property
    def items(self):
        if not hasattr(self, '_items'):
            self._items = []
            for i, (nt, rule) in enumerate(self.rules):
                for j in xrange(len(rule) + 1):
                    self._items.append((i, j))
        return self._items

    def lex(self):
        if self._lexer:
            logger.debug('Reading a token:')
            self.token = self._lexer(self)
            if self.token is None:
                self.token = END_SYMBOL
            logger.debug('Next token is: %r', self.token)
        return self.token

    @property
    def nonterminals(self):
        if not hasattr(self, '_nonterminals'):
            self._nonterminals = []
            for nt, _ in self.rules:
                if nt not in self._nonterminals:
                    self._nonterminals.append(nt)
        return self._nonterminals

    def parse(self, start=None):
        if start is None:
            start = ACCEPT_SYMBOL
        logger.debug('parse(%r)', start)
        self.token = self.lex()
        self.push(0)
        while True:
            action = self.action(self.ssp[-1], self.token)
            if ACCEPT_ACTION in action:
                return
            elif REDUCE_ACTION in action:
                n = action[REDUCE_ACTION]
                nt, alpha, action = self.grammar[n]
                p = len(alpha)
                vsp = self.vsp[-p:] if p else []
                tmp = self.lval
                if action:
                    self.lval = action(vsp)
                elif vsp:
                    self.lval = vsp[0]
                else:
                    self.lval = None
                self.pop(p)
                self.push(self.goto[self.ssp[-1]][nt])
                self.lval = tmp
            elif SHIFT_ACTION in action:
                self.push(self.goto[self.ssp[-1]][self.token])
                self.token = self.lex()
            else:
                self.error()

    def pop(self, n):
        for _ in xrange(n):
            self.ssp.pop()
            self.vsp.pop()

    def push(self, symbol):
        logger.debug('pushing %r %r', symbol, self.lval)
        self.ssp.append(symbol)
        self.vsp.append(self.lval)

    def reduce(self, n):
        logger.debug('reduce(%r)', n)
        nt, alpha, action = self.grammar[n]
        p = len(alpha)
        vsp = self.vsp[-p:] if p else []
        tmp = self.lval
        if action:
            self.lval = action(vsp)
        elif vsp:
            self.lval = vsp[0]
        else:
            self.lval = None
        self.pop(p)
        self.push(nt)
        self.lval = tmp

    @property
    def states(self):
        if not hasattr(self, '_states'):
            self._states = \
                [self.closure([(ACCEPT_SYMBOL, (), (self.start, END_SYMBOL))])]
            self.goto = {}
            while True:
                done = True
                for i, items in enumerate(self._states):
                    if i not in self.goto:
                        self.goto[i] = {}
                    for s in self.symbols:
                        goto = self.get_goto(items, s)
                        if goto:
                            try:
                                self.goto[i][s] = self._states.index(goto)
                            except ValueError:
                                self.goto[i][s] = len(self._states)
                                self._states.append(goto)
                                done = False
                if done:
                    break
        return self._states

    @property
    def symbols(self):
        if not hasattr(self, '_symbols'):
            self._symbols = self.nonterminals + self.terminals
        return self._symbols

    @property
    def terminals(self):
        if not hasattr(self, '_terminals'):
            self._terminals = []
            for nt, omega in self.rules:
                for s in omega:
                    if s not in self.nonterminals and s not in self._terminals:
                        self._terminals.append(s)
        return self._terminals

    def get_text(self):
        return self._text

    def set_text(self, text):
        for c in self._text:
            if c == '\n':
                self.column = 0
                self.lineno += 1
            else:
                self.column += 1
        self._text = text
        self.leng = len(text)

    text = property(get_text, set_text)
