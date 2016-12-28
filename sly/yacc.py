from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.level = logging.WARNING

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

    def __init__(self, grammar, start, lexer=None, in_=None, prec=None):
        self.start = start
        self.separator = ' '
        self.set_grammar(grammar)
        self._lexer = lexer
        self.in_ = in_ or ''
        self._lval = None
        self._text = ''
        self.column = 1
        self.lineno = 1
        self.ssp = []
        self.vsp = []
        self.token = None
        self.prec = prec or []
        self.default_reducer = lambda s: s

    def set_grammar(self, grammar):
        if ACCEPT_SYMBOL in grammar:
            logger.error('The nonterminal %r is reserved', ACCEPT_SYMBOL)
        self.grammar = grammar
        self.build_rules()
        self.build_states()
        self.build_first_table()
        self.build_follow_table()
        self.build_action_table()
        mystr = lambda x: unicode(x) if x in self.nonterminals else repr(x)
        if logger.level > logging.INFO:
            return
        for i, items in enumerate(self.states):
            logger.info('state %d:', i)
            logger.info('')
            for x, y in items:
                a, gamma = self.rules[x]
                alpha = ' '.join(map(mystr, gamma[:y]))
                beta = ' '.join(map(mystr, gamma[y:]))
                logger.info('\t%d %s -> %s . %s', x, a, alpha, beta)
            logger.info('')
            action_i = self.action[i]
            for s in self.terminals:
                if s in action_i:
                    for action, n in action_i[s].items():
                        if action == SHIFT_ACTION:
                            goto = self.goto[i][s]
                            action = '%s and go to state %d' % (action, goto)
                        elif action == REDUCE_ACTION:
                            a = self.rules[n][0]
                            action = '%s with rule %d (%s)' % (action, n, a)
                        logger.info('\taction[%d, %r] = %s', i, s, action)
            logger.info('')

    def build_rules(self):
        logger.debug('building rules, items, and symbol tables')
        self.rules = []
        self.rule_indices = {}
        self.items = []
        self.items_by_symbol = {}
        self.reducers = []
        augmented_grammar = dict(self.grammar)
        # FIXME: do we really need END_SYMBOL?
        # augmented_grammar[ACCEPT_SYMBOL] = [([self.start, END_SYMBOL], None)]
        augmented_grammar[ACCEPT_SYMBOL] = [([self.start], None)]
        self.nonterminals = set(augmented_grammar.keys())
        self.symbols = set(self.nonterminals)
        i = 0
        for a in [ACCEPT_SYMBOL] + self.grammar.keys():
            self.rule_indices[a] = []
            for gamma, reducer in augmented_grammar[a]:
                if isinstance(gamma, basestring):
                    gamma = gamma.split(self.separator)
                gamma = tuple(gamma)
                rule = (a, gamma)
                self.rule_indices[a].append(i)
                self.rule_indices[rule] = i
                self.rules.append(rule)
                self.reducers.append(reducer)
                for j, s in enumerate(gamma):
                    self.items.append((i, j))
                    self.symbols.add(s)
                    if s not in self.items_by_symbol:
                        self.items_by_symbol[s] = set()
                    self.items_by_symbol[s].add((i, j))
                self.items.append((i, len(gamma)))
                i += 1
        self.terminals = self.symbols.difference(self.nonterminals)

    def build_states(self):
        logger.debug('building state and goto tables')
        self.states = [self.closure([(0, 0)])]
        self.goto = []
        indices = {}
        i = 0
        while i < len(self.states):
            logger.debug('processing states %d to %d', i, len(self.states))
            for i in xrange(i, len(self.states)):
                items = self.states[i]
                logger.debug('processing state %d: %r', i, items)
                self.goto.append({})
                for s in self.symbols:
                    state = self.create_state(items, s)
                    if not state:
                        continue
                    if state in indices:
                        self.goto[i][s] = indices[state]
                    else:
                        indices[state] = len(self.states)
                        self.goto[i][s] = indices[state]
                        self.states.append(state)
            i += 1

    def create_state(self, items, s):
        state = []
        if s not in self.items_by_symbol:
            return frozenset()
        for x, y in self.items_by_symbol[s]:
            if (x, y) in items:
                state.append((x, y + 1))
        return self.closure(state)

    def build_first_table(self):
        self.first = {}
        for s in self.terminals:
            self.first[s] = {s}
        for s in self.nonterminals:
            self.create_first(s)

    def create_first(self, s):
        if s not in self.first:
            self.first[s] = set()
            for i in self.rule_indices[s]:
                _, gamma = self.rules[i]
                if not gamma:
                    self.first[s].add(EMPTY_SYMBOL)
                for t in gamma:
                    if t not in self.nonterminals:
                        self.first[s].add(t)
                        break
                    if s == t:
                        second = self.first[s]
                    else:
                        second = self.create_first(t)
                        self.first[s] |= second
                    if EMPTY_SYMBOL not in second:
                        break
        return self.first[s]

    def build_follow_table(self):
        logger.debug('building follow table')
        self.follow = {}
        self.follow[ACCEPT_SYMBOL] = {END_SYMBOL}
        for nt, rule in self.rules:
            if nt not in self.follow:
                self.follow[nt] = set()
            for i in xrange(len(rule) - 1):
                s = rule[i]
                t = rule[i+1]
                if s not in self.follow:
                    self.follow[s] = set()
                if t in self.nonterminals:
                    self.follow[s] |= self.first[t] - {EMPTY_SYMBOL}
                else:
                    self.follow[s].add(t)
        done = False
        while not done:
            done = True
            for nt, rule in self.rules:
                if not rule:
                    continue
                s = rule[-1]
                if s not in self.nonterminals:
                    continue
                for t in self.follow[nt]:
                    if t not in self.follow[s]:
                        self.follow[s].add(t)
                        done = False

    def build_action_table(self):
        shift_reduce_conflicts = collections.defaultdict(set)
        self.action = []
        for items in self.states:
            row = {}
            self.action.append(row)
            for x, y in items:
                a, gamma = self.rules[x]
                alpha = gamma[:y]
                beta = gamma[y:]
                if a == ACCEPT_SYMBOL and not beta:
                    row[END_SYMBOL] = {ACCEPT_ACTION: True}
                elif not beta:
                    for s in self.follow[a]:
                        if s not in row:
                            row[s] = {}
                        elif REDUCE_ACTION in row[s]:
                            # TODO: show a better error message
                            logger.error('reduce/reduce conflict')
                            r1 = self.rules[row[s][REDUCE_ACTION]]
                            r2 = self.rules[self.rule_indices[(a, alpha)]]
                            for b, gamma in [r1, r2]:
                                logger.error('%s -> %s', b,
                                             ' '.join(repr(s) if s in
                                                      self.terminals else s
                                                      for s in gamma))
                            exit(1)
                        elif SHIFT_ACTION in row[s]:
                            shift_reduce_conflicts[items].add(s)
                        row[s][REDUCE_ACTION] = self.rule_indices[(a, alpha)]
                else:
                    s = beta[0]
                    if s not in row:
                        row[s] = {}
                    row[s][SHIFT_ACTION] = True
                    if REDUCE_ACTION in row[s]:
                        shift_reduce_conflicts[items].add(s)
        if shift_reduce_conflicts:
            n = sum(len(xs) for xs in shift_reduce_conflicts.values())
            logger.warning('%d shift/reduce conflicts deteced', n)
            if logger.level > logging.INFO:
                logger.warning(
                    'set yacc.logger.level = logging.INFO for more info')
        for items, tokens in shift_reduce_conflicts.items():
            logger.info('shift/reduce conflict with tokens %s:', list(tokens))
            for x, y in items:
                a, gamma = self.rules[x]
                alpha = gamma[:y]
                beta = gamma[y:]
                logger.info('    %r -> %s . %s', a, ' '.join(map(repr, alpha)),
                            ' '.join(map(repr, beta)))

    def closure(self, items):
        closure_list = list(items)
        closure_set = set(items)
        i = 0
        while i < len(closure_list):
            for x, y in closure_list[i:]:
                i += 1
                beta = self.rules[x][1][y:]
                if not beta:
                    continue
                s = beta[0]
                if s not in self.nonterminals:
                    continue
                for x in self.rule_indices[s]:
                    item = (x, 0)
                    if item not in closure_set:
                        closure_list.append(item)
                        closure_set.add(item)
        del closure_list
        return frozenset(closure_set)

    def lex(self):
        if self._lexer:
            logger.debug('Reading a token:')
            self.token = self._lexer(self)
            if self.token is None:
                self.token = END_SYMBOL
            logger.debug('Next token is: %r', self.token)
        return self.token

    def parse(self):
        self.token = self.lex()
        self.ssp = []
        self.state = 0
        while True:
            logger.debug('token = %r', self.token)
            logger.debug('ssp = %r', self.ssp)
            logger.debug('vsp = %r', self.vsp)
            logger.debug('state %d = %r', self.state, self.states[self.state])
            if logger.level <= logging.DEBUG:
                for x, y in sorted(self.states[self.state]):
                    nt, rule = self.rules[x]
                    logger.debug('\t%d %r -> %s . %s', x, nt,
                                 ' '.join(map(repr, rule[:y])),
                                 ' '.join(map(repr, rule[y:])))
            try:
                action = self.action[self.state][self.token]
            except KeyError:
                logger.debug('action[%r] = %r', self.state,
                             self.action[self.state])
                logger.debug('action[%r, %r] = %r', self.state, self.token,
                             self.action[self.state].get(self.token))
                raise SyntaxError, 'syntax error at %d:%d %r' % (
                    self.lineno, self.column, self.text)
            logger.debug('action[%r, %r] = %r', self.state, self.token,
                         action)
            if ACCEPT_ACTION in action:
                return
            elif SHIFT_ACTION in action:
                self.state = self.goto[self.state][self.token]
                self.token = self.lex()
            elif REDUCE_ACTION in action:
                rule = action[REDUCE_ACTION]
                logger.debug('reduce by rule %d', rule)
                a, gamma = self.rules[rule]
                reducer = self.reducers[rule] or self.default_reducer
                n = len(gamma)
                values = self.vsp[-n:] if n else []
                logger.debug('values = %r', values)
                tmp = self.lval
                if reducer:
                    self.lval = reducer(values)
                for _ in xrange(n):
                    logger.debug('popping state = %r, value = %r',
                                 self.ssp.pop(), self.vsp.pop())
                logger.debug('follow[%r] = %r', a, self.follow[a])
                self.state = self.goto[self.state][a]
                self.lval = tmp

    def set_state(self, state):
        logger.debug('pushing state = %r, value = %r', state, self.lval)
        self.ssp.append(state)
        self.vsp.append(self.lval)

    state = property(lambda self: self.ssp[-1] if self.ssp else None, set_state)

    def set_text(self, text):
        for c in self._text:
            if c == '\n':
                self.column = 1
                self.lineno += 1
            else:
                self.column += 1
        self._text = text

    text = property(lambda self: self._text, set_text)

    def set_lval(self, lval):
        self._lval = lval

    lval = property(lambda self: self._lval, set_lval)
