import collections
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)

class Symbol: pass
class AcceptSymbol(Symbol): pass
class EndSymbol(Symbol): pass
class EmptySymbol(Symbol): pass

ACCEPT_SYMBOL = '$accept'
END_SYMBOL = '$end'
EMPTY_SYMBOL = '%empty'

ACCEPT_ACTION = 'accept'
REDUCE_ACTION = 'reduce'
SHIFT_ACTION = 'shift'


class Parser(object):

    def __init__(self, grammar, start, lexer=None, in_=None):
        if isinstance(grammar, list):
            self.start = start or (grammar[0][0] if grammar else None)
            self.grammar = [(ACCEPT_SYMBOL, (self.start, END_SYMBOL), None)]
            for nt, omega, aux in grammar:
                self.grammar.append((nt, tuple(omega), aux))
        elif isinstance(grammar, dict):
            self.start = start or (grammar.keys()[0] if grammar else None)
            self.grammar = [(ACCEPT_SYMBOL, (self.start, END_SYMBOL), None)]
            for nt, rules in grammar.items():
                for omega, action in rules:
                    self.grammar.append((nt, tuple(omega), action))
        self.rules = []
        self.rules_lookup = {}
        for nt, omega, _ in self.grammar:
            self.rules_lookup[(nt, omega)] = len(self.rules)
            self.rules.append((nt, omega))
        self._lexer = lexer
        self.in_ = in_ or ''
        self._lval = None
        self._text = ''
        self.column = 0
        self.leng = 0
        self.lineno = 0
        self.ssp = []
        self.vsp = []
        self.token = None
        self._debug = False

    def action(self, si, x):
        if not hasattr(self, '_action'):
            self._action = []
            for k, items in enumerate(self.states):
                row = {}
                self._action.append(row)
                for i, j in items:
                    nt, g = self.rules[i]
                    a = g[:j]
                    b = g[j:]
                    if nt == ACCEPT_SYMBOL and not b:
                        row[END_SYMBOL] = {ACCEPT_ACTION: True}
                    elif not b:
                        for s in self.follow(nt):
                            if s not in row:
                                row[s] = {}
                            elif REDUCE_ACTION in row[s]:
                                logger.error('reduce/reduce conflict')
                                exit(1)
                            row[s][REDUCE_ACTION] = self.rules_lookup[(nt, a)]
                    else:
                        s = b[0]
                        if s not in row:
                            row[s] = {}
                        row[s][SHIFT_ACTION] = True
        return self._action[si].get(x, {})

    def closure(self, si):
        sj = list(si)
        while 1:
            done = True
            for i, j in sj:
                beta = self.rules[i][1][j:]
                if not beta:
                    continue
                s = beta[0]
                for k, (nt, _) in enumerate(self.rules):
                    if s == nt:
                        item = (k, 0)
                        if item not in sj:
                            sj.append(item)
                            done = False
            if done:
                break
        return sj

    def get_goto(self, si, x):
        sj = []
        for i, j in self.items:
            if not j:
                continue
            if x == self.rules[i][1][j-1] and (i, j-1) in si:
                sj.append((i, j))
        return self.closure(sj)

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
            self._follow[ACCEPT_SYMBOL] = {END_SYMBOL}
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
            done = False
            while not done:
                done = True
                for nt, rule in self.rules:
                    if not rule:
                        continue
                    s = rule[-1]
                    if s not in self.nonterminals:
                        continue
                    for t in self._follow[nt]:
                        if t not in self._follow[s]:
                            self._follow[s].add(t)
                            done = False
        return self._follow[x]

    @property
    def items(self):
        if not hasattr(self, '_items'):
            self._items = []
            for i, (_, rule) in enumerate(self.rules):
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

    def parse(self):
        self.token = self.lex()
        self.push(0)
        while True:
            logger.debug('token = %r', self.token)
            logger.debug('ssp = %r', self.ssp)
            logger.debug('vsp = %r', self.vsp)
            s = self.ssp[-1]
            logger.debug('state %d = %r', s, self.states[s])
            if self.debug:
                for i, j in sorted(self.states[s]):
                    nt, rule = self.rules[i]
                    logger.debug('\t%d %r -> %s . %s', i, nt,
                                 ' '.join(map(repr, rule[:j])),
                                 ' '.join(map(repr, rule[j:])))
            logger.debug('action[%r, %r]', self.ssp[-1], self.token)
            action = self.action(self.ssp[-1], self.token)
            logger.debug('action[%r, %r] = %r', self.ssp[-1], self.token,
                         action)
            if ACCEPT_ACTION in action:
                return
            elif REDUCE_ACTION in action:
                n = action[REDUCE_ACTION]
                logger.debug('reduce by rule %d', n)
                nt, alpha, action = self.grammar[n]
                p = len(alpha)
                vsp = self.vsp[-p:] if p else []
                logger.debug('vsp = %r', vsp)
                tmp = self.lval
                if action:
                    self.lval = action(vsp)
                elif vsp:
                    self.lval = vsp[0]
                else:
                    self.lval = None
                self.pop(p)
                logger.debug('follow[%r] = %r', nt, self.follow(nt))
                self.push(self.goto[self.ssp[-1]][nt])
                self.lval = tmp
            elif SHIFT_ACTION in action:
                self.push(self.goto[self.ssp[-1]][self.token])
                self.token = self.lex()
            else:
                logger.error('syntax error at %d:%d %r', self.lineno,
                             self.column, self.text)
                exit(1)

    def pop(self, n):
        for _ in xrange(n):
            s = self.ssp.pop()
            v = self.vsp.pop()
            logger.debug('popping state = %r, value = %r', s, v)

    def push(self, state):
        logger.debug('pushing state = %r, value = %r', state, self.lval)
        self.ssp.append(state)
        self.vsp.append(self.lval)

    @property
    def states(self):
        if not hasattr(self, '_states'):
            self._states = [self.closure([(0, 0)])]
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

    def set_text(self, text):
        for c in self._text:
            if c == '\n':
                self.column = 0
                self.lineno += 1
            else:
                self.column += 1
        self._text = text
        self.leng = len(text)

    text = property(lambda self: self._text, set_text)

    def set_lval(self, lval):
        self._lval = lval

    lval = property(lambda self: self._lval, set_lval)

    def set_debug(self, debug):
        self._debug = debug
        if self._debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.WARNING)

    debug = property(lambda self: self._debug, set_debug)
