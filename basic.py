#######################################
# IMPORTS
#######################################

from strings_with_arrows import *

import string
import os
import math
import time
import sys
from dataclasses import dataclass
from typing import Any, List, Tuple

#######################################
# OPEN FILES (so they don't get automatically closed by GC)
#######################################

files = {}

#######################################
# CONSTANTS
#######################################

IMPORT_PATH_NAME = ".path"
if not os.path.isfile(IMPORT_PATH_NAME):
  IMPORT_PATHS = [".", os.getcwd() + "/std"]
  with open(IMPORT_PATH_NAME, "w") as f:
    f.write("\n".join(IMPORT_PATHS))
else:
  with open(IMPORT_PATH_NAME, "r") as f:
    IMPORT_PATHS = list(f.readlines())
DIGITS = '0123456789'
LETTERS = string.ascii_letters
VALID_IDENTIFIERS = LETTERS + DIGITS + "$_"

#######################################
# ERRORS
#######################################

class Value:
  def __init__(self):
    self.set_pos()
    self.set_context()

  def set_pos(self, pos_start=None, pos_end=None):
    self.pos_start = pos_start
    self.pos_end = pos_end
    return self

  def set_context(self, context=None):
    self.context = context
    return self

  def added_to(self, other):
    return None, self.illegal_operation(other)

  def subbed_by(self, other):
    return None, self.illegal_operation(other)

  def multed_by(self, other):
    return None, self.illegal_operation(other)

  def dived_by(self, other):
    return None, self.illegal_operation(other)

  def powed_by(self, other):
    return None, self.illegal_operation(other)

  def get_comparison_eq(self, other):
    return Number(bool(self.value == other.value)), None

  def get_comparison_ne(self, other):
    return Number(bool(self.value != other.value)), None

  def get_comparison_lt(self, other):
    return Number(bool(self.value < other.value)), None

  def get_comparison_gt(self, other):
    return Number(bool(self.value > other.value)), None

  def get_comparison_lte(self, other):
    return Number(bool(self.value <= other.value)), None

  def get_comparison_gte(self, other):
    return Number(bool(self.value >= other.value)), None

  def anded_by(self, other):
    return Number(bool(self.value and other.value)), None

  def ored_by(self, other):
    return Number(bool(self.value or other.value)), None

  def notted(self): # why need `other` for NOT?
    return Number(bool(not self.value)), None
  
  def iter(self):
    return Iterator(self.gen)
  
  def gen(self):
    yield RTResult().failure(self.illegal_operation())
  
  def get_index(self, index):
    return None, self.illegal_operation(index)

  def set_index(self, index, value):
    return None, self.illegal_operation(index, value)

  def execute(self, args):
    return RTResult().failure(self.illegal_operation())

  def copy(self):
    raise Exception('No copy method defined')

  def is_true(self):
    return False

  def illegal_operation(self, *others):
    if len(others) == 0:
      others = self,
    
    return RTError(
      self.pos_start, others[-1].pos_end,
      'Illegal operation',
      self.context
    )

class Error(Value):
  def __init__(self, pos_start, pos_end, error_name, details):
    self.pos_start = pos_start
    self.pos_end = pos_end
    self.error_name = error_name
    self.details = details
  
  def set_pos(self, pos_start=None, pos_end=None):
    return self

  def __repr__(self) -> str:
    return f'{self.error_name}: {self.details}'

  def as_string(self):
    result  = f'{self.error_name}: {self.details}\n'
    result += f'File {self.pos_start.fn}, line {self.pos_start.ln + 1}'
    result += '\n\n' + string_with_arrows(self.pos_start.ftxt, self.pos_start, self.pos_end)
    return result
  
  def copy(self):
    return __class__(self.pos_start, self.pos_end, self.error_name, self.details)

class IllegalCharError(Error):
  def __init__(self, pos_start, pos_end, details):
    super().__init__(pos_start, pos_end, 'Illegal Character', details)

class ExpectedCharError(Error):
  def __init__(self, pos_start, pos_end, details):
    super().__init__(pos_start, pos_end, 'Expected Character', details)

class InvalidSyntaxError(Error):
  def __init__(self, pos_start, pos_end, details=''):
    super().__init__(pos_start, pos_end, 'Invalid Syntax', details)

class RTError(Error):
  def __init__(self, pos_start, pos_end, details, context):
    super().__init__(pos_start, pos_end, 'Runtime Error', details)
    self.context = context

  def set_context(self, context=None):
    return self

  def as_string(self):
    result  = self.generate_traceback()
    result += f'{self.error_name}: {self.details}'
    result += '\n\n' + string_with_arrows(self.pos_start.ftxt, self.pos_start, self.pos_end)
    return result

  def generate_traceback(self):
    result = ''
    pos = self.pos_start
    ctx = self.context

    while ctx:
      result = f'  File {pos.fn}, line {str(pos.ln + 1)}, in {ctx.display_name}\n' + result
      pos = ctx.parent_entry_pos
      ctx = ctx.parent

    return 'Traceback (most recent call last):\n' + result
  
  def copy(self):
    return __class__(self.pos_start, self.pos_end, self.details, self.context)

class TryError(RTError):
  def __init__(self, pos_start, pos_end, details, context, prev_error):
    super().__init__(pos_start, pos_end, details, context)
    self.prev_error = prev_error 
  
  def generate_traceback(self):
    result = ""
    if self.prev_error:
      result += self.prev_error.as_string()
    result += "\nDuring the handling of the above error, another error occurred:\n\n"
    return result + super().generate_traceback()
    
#######################################
# POSITION
#######################################

class Position:
  def __init__(self, idx, ln, col, fn, ftxt):
    self.idx = idx
    self.ln = ln
    self.col = col
    self.fn = fn
    self.ftxt = ftxt

  def advance(self, current_char=None):
    self.idx += 1
    self.col += 1

    if current_char == '\n':
      self.ln += 1
      self.col = 0

    return self

  def copy(self):
    return Position(self.idx, self.ln, self.col, self.fn, self.ftxt)

#######################################
# TOKENS
#######################################

TT_INT				= 'INT'
TT_FLOAT    	= 'FLOAT'
TT_STRING			= 'STRING'
TT_IDENTIFIER	= 'IDENTIFIER'
TT_KEYWORD		= 'KEYWORD'
TT_PLUS     	= 'PLUS'
TT_MINUS    	= 'MINUS'
TT_MUL      	= 'MUL'
TT_DIV      	= 'DIV'
TT_POW				= 'POW'
TT_EQ					= 'EQ'
TT_LPAREN   	= 'LPAREN'
TT_RPAREN   	= 'RPAREN'
TT_LSQUARE    = 'LSQUARE'
TT_RSQUARE    = 'RSQUARE'
TT_EE					= 'EE'
TT_NE					= 'NE'
TT_LT					= 'LT'
TT_GT					= 'GT'
TT_LTE				= 'LTE'
TT_GTE				= 'GTE'
TT_COMMA			= 'COMMA'
TT_ARROW			= 'ARROW'
TT_LCURLY     = 'LCURLY'
TT_RCURLY     = 'RCURLY'
TT_COLON      = 'COLON'
TT_NEWLINE		= 'NEWLINE'
TT_EOF				= 'EOF'

KEYWORDS = [
  'AND',
  'OR',
  'NOT',
  'IF',
  'ELIF',
  'ELSE',
  'FOR',
  'TO',
  'STEP',
  'WHILE',
  'FUN',
  'THEN',
  'END',
  'RETURN',
  'CONTINUE',
  'BREAK',
  'IMPORT',
  'DO',
  'TRY',
  'CATCH',
  'AS',
  'FROM',
  'IN',
  'SWITCH',
  'CASE',
]

class Token:
  def __init__(self, type_, value=None, pos_start=None, pos_end=None):
    self.type = type_
    self.value = value

    if pos_start:
      self.pos_start = pos_start.copy()
      self.pos_end = pos_start.copy()
      self.pos_end.advance()

    if pos_end:
      self.pos_end = pos_end.copy()

  def copy(self):
    return Token(self.type, self.value, self.pos_start.copy(), self.pos_end.copy())

  def matches(self, type_, value):
    return self.type == type_ and self.value == value
  
  def __repr__(self):
    if self.value: return f'{self.type}:{self.value}'
    return f'{self.type}'

#######################################
# LEXER
#######################################

class Lexer:
  def __init__(self, fn, text):
    self.fn = fn
    self.text = text
    self.pos = Position(-1, 0, -1, fn, text)
    self.current_char = None
    self.advance()
  
  def advance(self):
    self.pos.advance(self.current_char)
    self.current_char = self.text[self.pos.idx] if self.pos.idx < len(self.text) else None

  def make_tokens(self):
    tokens = []

    while self.current_char != None:
      if self.current_char in ' \t':
        self.advance()
      elif self.current_char == '#':
        self.skip_comment()
      elif self.current_char in ';\n':
        tokens.append(Token(TT_NEWLINE, pos_start=self.pos))
        self.advance()
      elif self.current_char in DIGITS:
        tokens.append(self.make_number())
      elif self.current_char in VALID_IDENTIFIERS:
        tokens.append(self.make_identifier())
      elif self.current_char == '"':
        tokens.append(self.make_string())
      elif self.current_char == '+':
        tokens.append(Token(TT_PLUS, pos_start=self.pos))
        self.advance()
      elif self.current_char == '-':
        tokens.append(self.make_minus_or_arrow())
      elif self.current_char == '*':
        tokens.append(Token(TT_MUL, pos_start=self.pos))
        self.advance()
      elif self.current_char == '/':
        tokens.append(Token(TT_DIV, pos_start=self.pos))
        self.advance()
      elif self.current_char == '^':
        tokens.append(Token(TT_POW, pos_start=self.pos))
        self.advance()
      elif self.current_char == '(':
        tokens.append(Token(TT_LPAREN, pos_start=self.pos))
        self.advance()
      elif self.current_char == ')':
        tokens.append(Token(TT_RPAREN, pos_start=self.pos))
        self.advance()
      elif self.current_char == '[':
        tokens.append(Token(TT_LSQUARE, pos_start=self.pos))
        self.advance()
      elif self.current_char == ']':
        tokens.append(Token(TT_RSQUARE, pos_start=self.pos))
        self.advance()
      elif self.current_char == '{':
        tokens.append(Token(TT_LCURLY, pos_start=self.pos))
        self.advance()
      elif self.current_char == '}':
        tokens.append(Token(TT_RCURLY, pos_start=self.pos))
        self.advance()
      elif self.current_char == ':':
        tokens.append(Token(TT_COLON, pos_start=self.pos))
        self.advance()
      elif self.current_char == '!':
        token, error = self.make_not_equals()
        if error: return [], error
        tokens.append(token)
      elif self.current_char == '=':
        tokens.append(self.make_equals())
      elif self.current_char == '<':
        tokens.append(self.make_less_than())
      elif self.current_char == '>':
        tokens.append(self.make_greater_than())
      elif self.current_char == ',':
        tokens.append(Token(TT_COMMA, pos_start=self.pos))
        self.advance()
      elif self.current_char == '\\':
        self.advance()
        self.advance()
      else:
        pos_start = self.pos.copy()
        char = self.current_char
        self.advance()
        return [], IllegalCharError(pos_start, self.pos, "'" + char + "'")

    tokens.append(Token(TT_EOF, pos_start=self.pos))
    return tokens, None

  def make_number(self):
    num_str = ''
    dot_count = 0
    pos_start = self.pos.copy()

    while self.current_char != None and self.current_char in DIGITS + '.':
      if self.current_char == '.':
        if dot_count == 1: break
        dot_count += 1
      num_str += self.current_char
      self.advance()

    if dot_count == 0:
      return Token(TT_INT, int(num_str), pos_start, self.pos)
    else:
      return Token(TT_FLOAT, float(num_str), pos_start, self.pos)

  def make_string(self):
    string = ''
    pos_start = self.pos.copy()
    escape_character = False
    self.advance()

    while self.current_char != None and (self.current_char != '"' or escape_character):
      if escape_character:
        escape_character = False
      elif self.current_char == '\\':
        escape_character = True
      string += self.current_char
      self.advance()
    
    self.advance()
    return Token(TT_STRING, string.encode('raw_unicode_escape').decode('unicode_escape'), pos_start, self.pos)

  def make_identifier(self):
    id_str = ''
    pos_start = self.pos.copy()

    while self.current_char != None and self.current_char in VALID_IDENTIFIERS:
      id_str += self.current_char
      self.advance()

    tok_type = TT_KEYWORD if id_str in KEYWORDS else TT_IDENTIFIER
    return Token(tok_type, id_str, pos_start, self.pos)

  def make_minus_or_arrow(self):
    tok_type = TT_MINUS
    pos_start = self.pos.copy()
    self.advance()

    if self.current_char == '>':
      self.advance()
      tok_type = TT_ARROW

    return Token(tok_type, pos_start=pos_start, pos_end=self.pos)

  def make_not_equals(self):
    pos_start = self.pos.copy()
    self.advance()

    if self.current_char == '=':
      self.advance()
      return Token(TT_NE, pos_start=pos_start, pos_end=self.pos), None

    self.advance()
    return None, ExpectedCharError(pos_start, self.pos, "'=' (after '!')")
  
  def make_equals(self):
    tok_type = TT_EQ
    pos_start = self.pos.copy()
    self.advance()

    if self.current_char == '=':
      self.advance()
      tok_type = TT_EE

    return Token(tok_type, pos_start=pos_start, pos_end=self.pos)

  def make_less_than(self):
    tok_type = TT_LT
    pos_start = self.pos.copy()
    self.advance()

    if self.current_char == '=':
      self.advance()
      tok_type = TT_LTE

    return Token(tok_type, pos_start=pos_start, pos_end=self.pos)

  def make_greater_than(self):
    tok_type = TT_GT
    pos_start = self.pos.copy()
    self.advance()

    if self.current_char == '=':
      self.advance()
      tok_type = TT_GTE

    return Token(tok_type, pos_start=pos_start, pos_end=self.pos)

  def skip_comment(self):
    multi_line_comment = False
    self.advance()
    if self.current_char == "*":
      multi_line_comment = True

    while self.current_char is not None:
      if self.current_char == "*" and multi_line_comment:
        self.advance()
        if self.current_char != "#": continue
        else: break
      elif self.current_char == "\n" and not multi_line_comment: break
      self.advance()

    self.advance()

#######################################
# NODES
#######################################

class NumberNode:
  def __init__(self, tok):
    self.tok = tok

    self.pos_start = self.tok.pos_start
    self.pos_end = self.tok.pos_end

  def __repr__(self):
    return f'{self.tok}'

class StringNode:
  def __init__(self, tok):
    self.tok = tok

    self.pos_start = self.tok.pos_start
    self.pos_end = self.tok.pos_end

  def __repr__(self):
    return f'{self.tok}'

class ListNode:
  def __init__(self, element_nodes, pos_start, pos_end):
    self.element_nodes = element_nodes

    self.pos_start = pos_start
    self.pos_end = pos_end

class VarAccessNode:
  def __init__(self, var_name_tok):
    self.var_name_tok = var_name_tok

    self.pos_start = self.var_name_tok.pos_start
    self.pos_end = self.var_name_tok.pos_end

class VarAssignNode:
  def __init__(self, var_name_tok, value_node):
    self.var_name_tok = var_name_tok
    self.value_node = value_node

    self.pos_start = self.var_name_tok.pos_start
    self.pos_end = self.value_node.pos_end

class BinOpNode:
  def __init__(self, left_node, op_tok, right_node):
    self.left_node = left_node
    self.op_tok = op_tok
    self.right_node = right_node

    self.pos_start = self.left_node.pos_start
    self.pos_end = self.right_node.pos_end

  def __repr__(self):
    return f'({self.left_node}, {self.op_tok}, {self.right_node})'

class UnaryOpNode:
  def __init__(self, op_tok, node):
    self.op_tok = op_tok
    self.node = node

    self.pos_start = self.op_tok.pos_start
    self.pos_end = node.pos_end

  def __repr__(self):
    return f'({self.op_tok}, {self.node})'

class IfNode:
  def __init__(self, cases, else_case):
    self.cases = cases
    self.else_case = else_case

    self.pos_start = self.cases[0][0].pos_start
    self.pos_end = (self.else_case or self.cases[len(self.cases) - 1])[0].pos_end

class ForNode:
  def __init__(self, var_name_tok, start_value_node, end_value_node, step_value_node, body_node, should_return_null):
    self.var_name_tok = var_name_tok
    self.start_value_node = start_value_node
    self.end_value_node = end_value_node
    self.step_value_node = step_value_node
    self.body_node = body_node
    self.should_return_null = should_return_null

    self.pos_start = self.var_name_tok.pos_start
    self.pos_end = self.body_node.pos_end

class WhileNode:
  def __init__(self, condition_node, body_node, should_return_null):
    self.condition_node = condition_node
    self.body_node = body_node
    self.should_return_null = should_return_null

    self.pos_start = self.condition_node.pos_start
    self.pos_end = self.body_node.pos_end

class FuncDefNode:
  def __init__(self, var_name_tok, arg_name_toks, defaults, dynamics, body_node, should_auto_return):
    self.var_name_tok = var_name_tok
    self.arg_name_toks = arg_name_toks
    self.defaults = defaults
    self.dynamics = dynamics
    self.body_node = body_node
    self.should_auto_return = should_auto_return

    if self.var_name_tok:
      self.pos_start = self.var_name_tok.pos_start
    elif len(self.arg_name_toks) > 0:
      self.pos_start = self.arg_name_toks[0].pos_start
    else:
      self.pos_start = self.body_node.pos_start

    self.pos_end = self.body_node.pos_end

class CallNode:
  def __init__(self, node_to_call, arg_nodes):
    self.node_to_call = node_to_call
    self.arg_nodes = arg_nodes

    self.pos_start = self.node_to_call.pos_start

    if len(self.arg_nodes) > 0:
      self.pos_end = self.arg_nodes[len(self.arg_nodes) - 1].pos_end
    else:
      self.pos_end = self.node_to_call.pos_end

class ReturnNode:
  def __init__(self, node_to_return, pos_start, pos_end):
    self.node_to_return = node_to_return

    self.pos_start = pos_start
    self.pos_end = pos_end

class ContinueNode:
  def __init__(self, pos_start, pos_end):
    self.pos_start = pos_start
    self.pos_end = pos_end

class BreakNode:
  def __init__(self, pos_start, pos_end):
    self.pos_start = pos_start
    self.pos_end = pos_end

@dataclass
class ImportNode:
  string_node: StringNode
  pos_start: Position
  pos_end: Position

  def __repr__(self) -> str:
    return f"IMPORT {self.string_node!r}"

@dataclass
class DoNode:
  statements: ListNode
  pos_start: Position
  pos_end: Position

  def __repr__(self) -> str:
    return f'(DO {self.statements!r} END)'

@dataclass
class TryNode:
  try_block: ListNode
  exc_iden: Token
  catch_block: Any
  pos_start: Position
  pos_end: Position

  def __repr__(self) -> str:
    return f'(TRY {self.try_block!r} CATCH AS {self.exc_iden!r} THEN {self.catch_block!r})'

@dataclass
class ForInNode:
  var_name_tok: Token
  iterable_node: Any
  body_node: Any
  pos_start: Position
  pos_end: Position
  should_return_null: bool

  def __repr__(self) -> str:
    return f"(FOR {self.var_name_tok} IN {self.iterable_node!r} THEN {self.body_node!r})"

@dataclass
class IndexGetNode:
  indexee: Any
  index: Any
  pos_start: Position
  pos_end: Position

  def __repr__(self):
    return f"({self.indexee!r}[{self.index!r}])"

@dataclass
class IndexSetNode:
  indexee: Any
  index: Any
  value: Any
  pos_start: Position
  pos_end: Position

  def __repr__(self):
    return f"({self.indexee!r}[{self.index!r}]={self.value!r})"

@dataclass
class DictNode:
  pairs: (Any, Any)
  pos_start: Position
  pos_end: Position

  def __repr__(self):
    result = "({"
    for key, value in self.pairs:
      result += f"{key!r}: {value!r}"
    return result + "})"

INDENTATION = 4

@dataclass
class SwitchNode:
  condition: Any
  cases: List[Tuple[Any, ListNode]]
  else_case: ListNode
  pos_start: Position
  pos_end: Position

  def __repr__(self): # holy shit
    return f"(SWITCH {self.condition!r}\n " + (" " * INDENTATION) + ("\n "+ " " * INDENTATION).join(
      f"CASE {case_cond!r}\n " + (" " * INDENTATION * 2) + f"{case_body!r}" for case_cond, case_body in self.cases
    ) + "\n " + (" " * INDENTATION) + "ELSE\n" + (" " * INDENTATION * 2) + f"{self.else_case!r})"

#######################################
# PARSE RESULT
#######################################

class ParseResult:
  def __init__(self):
    self.error = None
    self.node = None
    self.last_registered_advance_count = 0
    self.advance_count = 0
    self.to_reverse_count = 0

  def register_advancement(self):
    self.last_registered_advance_count = 1
    self.advance_count += 1

  def register(self, res):
    self.last_registered_advance_count = res.advance_count
    self.advance_count += res.advance_count
    if res.error: self.error = res.error
    return res.node

  def try_register(self, res):
    if res.error:
      self.to_reverse_count = res.advance_count
      return None
    return self.register(res)

  def success(self, node):
    self.node = node
    return self

  def failure(self, error):
    if not self.error or self.last_registered_advance_count == 0:
      self.error = error
    return self

#######################################
# PARSER
#######################################

class Parser:
  def __init__(self, tokens):
    self.tokens = tokens
    self.tok_idx = -1
    dummy = ParseResult()
    self.advance(dummy)

  def advance(self, res: ParseResult):
    self.tok_idx += 1
    self.update_current_tok()
    res.register_advancement()
    return self.current_tok

  def reverse(self, amount=1):
    self.tok_idx -= amount
    self.update_current_tok()
    return self.current_tok

  def update_current_tok(self):
    if self.tok_idx >= 0 and self.tok_idx < len(self.tokens):
      self.current_tok = self.tokens[self.tok_idx]

  def parse(self):
    res = self.statements()
    if not res.error and self.current_tok.type != TT_EOF:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Token cannot appear after previous tokens"
      ))
    return res

  ###################################

  def statements(self):
    res = ParseResult()
    statements = []
    pos_start = self.current_tok.pos_start.copy()

    while self.current_tok.type == TT_NEWLINE:
      self.advance(res)

    statement = res.register(self.statement())
    if res.error: return res
    statements.append(statement)

    more_statements = True

    while True:
      newline_count = 0
      while self.current_tok.type == TT_NEWLINE:
        self.advance(res)
        newline_count += 1
      if newline_count == 0:
        more_statements = False
      
      if not more_statements: break
      statement = res.try_register(self.statement())
      if not statement:
        self.reverse(res.to_reverse_count)
        more_statements = False
        continue
      statements.append(statement)

    return res.success(ListNode(
      statements,
      pos_start,
      self.current_tok.pos_end.copy()
    ))

  def statement(self):
    res = ParseResult()
    pos_start = self.current_tok.pos_start.copy()

    if self.current_tok.matches(TT_KEYWORD, 'RETURN'):
      self.advance(res)

      expr = res.try_register(self.expr())
      if not expr:
        self.reverse(res.to_reverse_count)
      return res.success(ReturnNode(expr, pos_start, self.current_tok.pos_start.copy()))
    
    if self.current_tok.matches(TT_KEYWORD, 'CONTINUE'):
      self.advance(res)
      return res.success(ContinueNode(pos_start, self.current_tok.pos_start.copy()))
      
    if self.current_tok.matches(TT_KEYWORD, 'BREAK'):
      self.advance(res)
      return res.success(BreakNode(pos_start, self.current_tok.pos_start.copy()))
    
    if self.current_tok.matches(TT_KEYWORD, 'IMPORT'):
      self.advance(res)

      if not self.current_tok.type == TT_STRING:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          "Expected string"
        ))
      
      string = res.register(self.atom())
      return res.success(ImportNode(string, pos_start, self.current_tok.pos_start.copy()))

    if self.current_tok.matches(TT_KEYWORD, 'TRY'):
      self.advance(res)
      try_node = res.register(self.try_statement())
      return res.success(try_node)
    
    if self.current_tok.matches(TT_KEYWORD, 'SWITCH'):
      self.advance(res)
      switch_node = res.register(self.switch_statement())
      return res.success(switch_node)

    expr = res.register(self.expr())
    if res.error:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected 'SWITCH', 'RETURN', 'CONTINUE', 'BREAK', 'IF', 'FOR', 'WHILE', 'FUN', int, float, identifier, '+', '-', '(', '[', '{' or 'NOT'"
      ))
    return res.success(expr)

  def expr(self):
    res = ParseResult()

    var_assign_node = res.try_register(self.assign_expr())
    if var_assign_node: return res.success(var_assign_node)
    else: self.reverse(res.to_reverse_count)

    node = res.register(self.bin_op(self.comp_expr, ((TT_KEYWORD, 'AND'), (TT_KEYWORD, 'OR'))))

    if res.error:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected 'IF', 'FOR', 'WHILE', 'FUN', int, float, identifier, '+', '-', '(', '[', '{' or 'NOT'"
      ))
    
    if self.current_tok.type == TT_EQ:
      return res.failure(InvalidSyntaxError(
        node.pos_start, node.pos_end,
        "Invalid assignment"
      ))

    return res.success(node)

  def assign_expr(self):
    res = ParseResult()
    pos_start = self.current_tok.pos_start

    if self.current_tok.type != TT_IDENTIFIER: 
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected 'IF', 'FOR', 'WHILE', 'FUN', int, float, identifier, '+', '-', '(', '[', '{' or 'NOT'"
      ))
    
    var_name_tok = self.current_tok

    self.advance(res)
    
    if self.current_tok.type != TT_EQ:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected '='"
      ))
    
    self.advance(res)

    assign_expr = res.register(self.expr())
    if res.error: return res

    return res.success(VarAssignNode(var_name_tok, assign_expr))

  def comp_expr(self):
    res = ParseResult()

    if self.current_tok.matches(TT_KEYWORD, 'NOT'):
      op_tok = self.current_tok
      self.advance(res)

      node = res.register(self.comp_expr())
      if res.error: return res
      return res.success(UnaryOpNode(op_tok, node))
    
    node = res.register(self.bin_op(self.arith_expr, (TT_EE, TT_NE, TT_LT, TT_GT, TT_LTE, TT_GTE)))
    
    if res.error:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected int, float, identifier, '+', '-', '(', '[', 'IF', 'FOR', 'WHILE', 'FUN' or 'NOT'"
      ))

    return res.success(node)

  def arith_expr(self):
    return self.bin_op(self.term, (TT_PLUS, TT_MINUS))

  def term(self):
    return self.bin_op(self.factor, (TT_MUL, TT_DIV))

  def factor(self):
    res = ParseResult()
    tok = self.current_tok

    if tok.type in (TT_PLUS, TT_MINUS):
      self.advance(res)
      factor = res.register(self.factor())
      if res.error: return res
      return res.success(UnaryOpNode(tok, factor))

    return self.power()

  def power(self):
    return self.bin_op(self.call, (TT_POW, ), self.factor)

  def call(self):
    res = ParseResult()
    index = res.register(self.atom())
    if res.error: return res

    if self.current_tok.type == TT_LPAREN:
      self.advance(res)
      arg_nodes = []

      if self.current_tok.type == TT_RPAREN:
        self.advance(res)
      else:
        arg_nodes.append(res.register(self.expr()))
        if res.error:
          return res.failure(InvalidSyntaxError(
            self.current_tok.pos_start, self.current_tok.pos_end,
            "Expected ')', 'IF', 'FOR', 'WHILE', 'FUN', int, float, identifier, '+', '-', '(', '[', '{' or 'NOT'"
          ))

        while self.current_tok.type == TT_COMMA:
          self.advance(res)

          arg_nodes.append(res.register(self.expr()))
          if res.error: return res

        if self.current_tok.type != TT_RPAREN:
          return res.failure(InvalidSyntaxError(
            self.current_tok.pos_start, self.current_tok.pos_end,
            f"Expected ',' or ')'"
          ))

        self.advance(res)
      return res.success(CallNode(index, arg_nodes))
    return res.success(index)

  def atom(self):
    res = ParseResult()
    tok = self.current_tok
    node = None

    if tok.type in (TT_INT, TT_FLOAT):
      self.advance(res)
      node = NumberNode(tok)

    elif tok.type == TT_STRING:
      self.advance(res)
      node = StringNode(tok)

    elif tok.type == TT_IDENTIFIER:
      self.advance(res)
      node = VarAccessNode(tok)

    elif tok.type == TT_LPAREN:
      self.advance(res)
      expr = res.register(self.expr())
      if res.error: return res
      if self.current_tok.type == TT_RPAREN:
        self.advance(res)
        node = expr
      else:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          "Expected ')'"
        ))

    elif tok.type == TT_LSQUARE:
      list_expr = res.register(self.list_expr())
      if res.error: return res
      node = list_expr
    
    elif tok.matches(TT_KEYWORD, 'IF'):
      if_expr = res.register(self.if_expr())
      if res.error: return res
      node = if_expr

    elif tok.matches(TT_KEYWORD, 'FOR'):
      for_expr = res.register(self.for_expr())
      if res.error: return res
      node = for_expr

    elif tok.matches(TT_KEYWORD, 'WHILE'):
      while_expr = res.register(self.while_expr())
      if res.error: return res
      node = while_expr

    elif tok.matches(TT_KEYWORD, 'FUN'):
      func_def = res.register(self.func_def())
      if res.error: return res
      node = func_def

    elif tok.matches(TT_KEYWORD, 'DO'):
      do_expr = res.register(self.do_expr())
      if res.error: return res
      node = do_expr
    
    elif tok.type == TT_LCURLY:
      dict_expr = res.register(self.dict_expr())
      if res.error: return res
      node = dict_expr

    if node is None:
      return res.failure(InvalidSyntaxError(
        tok.pos_start, tok.pos_end,
        "Expected int, float, identifier, '+', '-', '(', '[', IF', 'FOR', 'WHILE', 'FUN'"
      ))
    
    if self.current_tok.type == TT_LSQUARE:
      self.advance(res)
      index = res.register(self.expr())
      if res.error: return res
      
      if self.current_tok.type != TT_RSQUARE:
        return res.failure(InvalidSyntaxError(
          tok.pos_start, self.current_tok.pos_end,
          "Expected ']'"
        ))

      self.advance(res)

      if self.current_tok.type == TT_EQ:
        self.advance(res)

        value = res.register(self.expr())
        if res.error: return error

        return res.success(IndexSetNode(node, index, value, tok.pos_start, self.current_tok.pos_end))
      
      return res.success(IndexGetNode(node, index, tok.pos_start, self.current_tok.pos_end))
    
    return res.success(node)

  def list_expr(self):
    res = ParseResult()
    element_nodes = []
    pos_start = self.current_tok.pos_start.copy()

    if self.current_tok.type != TT_LSQUARE:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected '['"
      ))

    self.advance(res)

    if self.current_tok.type == TT_RSQUARE:
      self.advance(res)
    else:
      element_nodes.append(res.register(self.expr()))
      if res.error:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          "Expected ']', 'IF', 'FOR', 'WHILE', 'FUN', int, float, identifier, '+', '-', '(', '[', '{' or 'NOT'"
        ))

      while self.current_tok.type == TT_COMMA:
        self.advance(res)

        element_nodes.append(res.register(self.expr()))
        if res.error: return res

      if self.current_tok.type != TT_RSQUARE:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          f"Expected ',' or ']'"
        ))

      self.advance(res)

    return res.success(ListNode(
      element_nodes,
      pos_start,
      self.current_tok.pos_end.copy()
    ))
  
  def dict_expr(self):
    res = ParseResult()
    pairs = []
    pos_start = self.current_tok.pos_start.copy()

    if self.current_tok.type != TT_LCURLY:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected '{'"
      ))

    self.advance(res)

    if self.current_tok.type == TT_RCURLY:
      self.advance(res)
    else:
      key = res.register(self.expr())
      if res.error: return res

      if self.current_tok.type != TT_COLON:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          "Expected ':'"
        ))
      
      self.advance(res)
        
      value = res.register(self.expr())
      if res.error: return res

      pairs.append((key, value))

      while self.current_tok.type == TT_COMMA:
        self.advance(res)

        key = res.register(self.expr())
        if res.error: return res

        if self.current_tok.type != TT_COLON:
          return res.failure(InvalidSyntaxError(
            self.current_tok.pos_start, self.current_tok.pos_end,
            "Expected ':'"
          ))
        
        self.advance(res)

        value = res.register(self.expr())
        if res.error: return res

        pairs.append((key, value))

      if self.current_tok.type != TT_RCURLY:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          "Expected ',' or '}'"
        ))

      self.advance(res)

    return res.success(DictNode(
      pairs,
      pos_start,
      self.current_tok.pos_end.copy()
    ))

  def if_expr(self):
    res = ParseResult()
    all_cases = res.register(self.if_expr_cases('IF'))
    if res.error: return res
    cases, else_case = all_cases
    return res.success(IfNode(cases, else_case))

  def if_expr_b(self):
    return self.if_expr_cases('ELIF')
    
  def if_expr_c(self):
    res = ParseResult()
    else_case = None

    if self.current_tok.matches(TT_KEYWORD, 'ELSE'):
      self.advance(res)

      if self.current_tok.type == TT_NEWLINE:
        self.advance(res)

        statements = res.register(self.statements())
        if res.error: return res
        else_case = (statements, True)

        if self.current_tok.matches(TT_KEYWORD, 'END'):
          self.advance(res)
        else:
          return res.failure(InvalidSyntaxError(
            self.current_tok.pos_start, self.current_tok.pos_end,
            "Expected 'END'"
          ))
      else:
        expr = res.register(self.statement())
        if res.error: return res
        else_case = (expr, False)

    return res.success(else_case)

  def if_expr_b_or_c(self):
    res = ParseResult()
    cases, else_case = [], None

    if self.current_tok.matches(TT_KEYWORD, 'ELIF'):
      all_cases = res.register(self.if_expr_b())
      if res.error: return res
      cases, else_case = all_cases
    else:
      else_case = res.register(self.if_expr_c())
      if res.error: return res
    
    return res.success((cases, else_case))

  def if_expr_cases(self, case_keyword):
    res = ParseResult()
    cases = []
    else_case = None

    if not self.current_tok.matches(TT_KEYWORD, case_keyword):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected '{case_keyword}'"
      ))

    self.advance(res)

    condition = res.register(self.expr())
    if res.error: return res

    if not self.current_tok.matches(TT_KEYWORD, 'THEN'):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected 'THEN'"
      ))

    self.advance(res)

    if self.current_tok.type == TT_NEWLINE:
      self.advance(res)

      statements = res.register(self.statements())
      if res.error: return res
      cases.append((condition, statements, True))

      if self.current_tok.matches(TT_KEYWORD, 'END'):
        self.advance(res)
      else:
        all_cases = res.register(self.if_expr_b_or_c())
        if res.error: return res
        new_cases, else_case = all_cases
        cases.extend(new_cases)
    else:
      expr = res.register(self.statement())
      if res.error: return res
      cases.append((condition, expr, False))

      all_cases = res.register(self.if_expr_b_or_c())
      if res.error: return res
      new_cases, else_case = all_cases
      cases.extend(new_cases)

    return res.success((cases, else_case))

  def for_expr(self):
    res = ParseResult()
    pos_start = self.current_tok.pos_start.copy()

    if not self.current_tok.matches(TT_KEYWORD, 'FOR'):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected 'FOR'"
      ))

    self.advance(res)

    if self.current_tok.type != TT_IDENTIFIER:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected identifier"
      ))

    var_name = self.current_tok
    self.advance(res)

    is_for_in = False

    if self.current_tok.type != TT_EQ and not self.current_tok.matches(TT_KEYWORD, "IN"):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected '=' or 'IN'"
      ))
    elif self.current_tok.matches(TT_KEYWORD, "IN"):
      self.advance(res)
      is_for_in = True

      iterable_node = res.register(self.expr())
      if res.error: return res
      
    else:
      self.advance(res)

      start_value = res.register(self.expr())
      if res.error: return res

      if not self.current_tok.matches(TT_KEYWORD, 'TO'):
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          f"Expected 'TO'"
        ))
    
      self.advance(res)

      end_value = res.register(self.expr())
      if res.error: return res

      if self.current_tok.matches(TT_KEYWORD, 'STEP'):
        self.advance(res)

        step_value = res.register(self.expr())
        if res.error: return res
      else:
        step_value = None

    if not self.current_tok.matches(TT_KEYWORD, 'THEN'):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected 'THEN'"
      ))

    self.advance(res)

    if self.current_tok.type == TT_NEWLINE:
      self.advance(res)

      body = res.register(self.statements())
      if res.error: return res

      if not self.current_tok.matches(TT_KEYWORD, 'END'):
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          f"Expected 'END'"
        ))

      pos_end = self.current_tok.pos_end.copy()
      self.advance(res)

      if is_for_in:
        return res.success(ForInNode(var_name, iterable_node, body, pos_start, pos_end, True))
      return res.success(ForNode(var_name, start_value, end_value, step_value, body, True))
    
    body = res.register(self.statement())
    if res.error: return res

    pos_end = self.current_tok.pos_end.copy()

    if is_for_in:
      return res.success(ForInNode(var_name, iterable_node, body, pos_start, pos_end, False))
    return res.success(ForNode(var_name, start_value, end_value, step_value, body, False))

  def while_expr(self):
    res = ParseResult()

    if not self.current_tok.matches(TT_KEYWORD, 'WHILE'):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected 'WHILE'"
      ))

    self.advance(res)

    condition = res.register(self.expr())
    if res.error: return res

    if not self.current_tok.matches(TT_KEYWORD, 'THEN'):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected 'THEN'"
      ))

    self.advance(res)

    if self.current_tok.type == TT_NEWLINE:
      self.advance(res)

      body = res.register(self.statements())
      if res.error: return res

      if not self.current_tok.matches(TT_KEYWORD, 'END'):
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          f"Expected 'END'"
        ))

      self.advance(res)

      return res.success(WhileNode(condition, body, True))
    
    body = res.register(self.statement())
    if res.error: return res

    return res.success(WhileNode(condition, body, False))

  def func_def(self):
    res = ParseResult()

    if not self.current_tok.matches(TT_KEYWORD, 'FUN'):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected 'FUN'"
      ))

    self.advance(res)

    if self.current_tok.type == TT_IDENTIFIER:
      var_name_tok = self.current_tok
      self.advance(res)
      if self.current_tok.type != TT_LPAREN:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          f"Expected '('"
        ))
    else:
      var_name_tok = None
      if self.current_tok.type != TT_LPAREN:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          f"Expected identifier or '('"
        ))
    
    self.advance(res)
    arg_name_toks = []
    defaults = []
    dynamics = []
    hasOptionals = False

    if self.current_tok.type == TT_IDENTIFIER:
      pos_start = self.current_tok.pos_start.copy()
      pos_end = self.current_tok.pos_end.copy()
      arg_name_toks.append(self.current_tok)
      self.advance(res)

      if self.current_tok.type == TT_EQ:
        self.advance(res)
        default = res.register(self.expr())
        if res.error: return res
        defaults.append(default)
        hasOptionals = True
      elif hasOptionals:
        return res.failure(InvalidSyntaxError(
          pos_start, pos_end,
          "Expected optional parameter."
        ))
      else:
        defaults.append(None)
      
      if self.current_tok.matches(TT_KEYWORD, 'FROM'):
        self.advance(res)
        dynamics.append(res.register(self.expr()))
        if res.error: return res
      else:
        dynamics.append(None)

      
      while self.current_tok.type == TT_COMMA:
        self.advance(res)

        if self.current_tok.type != TT_IDENTIFIER:
          return res.failure(InvalidSyntaxError(
            self.current_tok.pos_start, self.current_tok.pos_end,
            f"Expected identifier"
          ))

        pos_start = self.current_tok.pos_start.copy()
        pos_end = self.current_tok.pos_end.copy()
        arg_name_toks.append(self.current_tok)
        self.advance(res)

        if self.current_tok.type == TT_EQ:
          self.advance(res)
          default = res.register(self.expr())
          if res.error: return res
          defaults.append(default)
          hasOptionals = True
        elif hasOptionals:
          return res.failure(InvalidSyntaxError(
            pos_start, pos_end,
            "Expected optional parameter."
          ))
        else:
          defaults.append(None)
        
        if self.current_tok.matches(TT_KEYWORD, 'FROM'):
          self.advance(res)
          dynamics.append(res.register(self.expr()))
          if res.error: return res
        else:
          dynamics.append(None)
      
      if self.current_tok.type != TT_RPAREN:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          f"Expected ',', ')' or '='"
        ))
    else:
      if self.current_tok.type != TT_RPAREN:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          f"Expected identifier or ')'"
        ))

    self.advance(res)

    if self.current_tok.type == TT_ARROW:
      self.advance(res)

      body = res.register(self.expr())
      if res.error: return res

      return res.success(FuncDefNode(
        var_name_tok,
        arg_name_toks,
        defaults,
        dynamics,
        body,
        True
      ))
    
    if self.current_tok.type != TT_NEWLINE:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected '->' or NEWLINE"
      ))

    self.advance(res)

    body = res.register(self.statements())
    if res.error: return res

    if not self.current_tok.matches(TT_KEYWORD, 'END'):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        f"Expected 'END'"
      ))

    self.advance(res)
    
    return res.success(FuncDefNode(
      var_name_tok,
      arg_name_toks,
      defaults,
      dynamics,
      body,
      False
    ))

  def do_expr(self):
    res = ParseResult()
    pos_start = self.current_tok.pos_start.copy()

    self.advance(res)
    
    statements = res.register(self.statements())

    if not self.current_tok.matches(TT_KEYWORD, 'END'):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected 'END', 'RETURN', 'CONTINUE', 'BREAK', 'IF', 'FOR', 'WHILE', 'FUN', int, float, identifier, '+', '-', '(', '[', '{' or 'NOT'"
      ))
    
    pos_end = self.current_tok.pos_end.copy()
    self.advance(res)
    return res.success(DoNode(statements, pos_start, pos_end))

  def try_statement(self):
    res = ParseResult()
    pos_start = self.current_tok.pos_start.copy()

    try_block = res.register(self.statements())
    if res.error: return res

    if not self.current_tok.matches(TT_KEYWORD, 'CATCH'):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected 'CATCH', 'RETURN', 'CONTINUE', 'BREAK', 'IF', 'FOR', 'WHILE', 'FUN', int, float, identifier, '+', '-', '(', '[', '{' or 'NOT'"
      ))
    
    self.advance(res)

    if not self.current_tok.matches(TT_KEYWORD, 'AS'):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected 'AS'"
      ))

    self.advance(res)

    if self.current_tok.type != TT_IDENTIFIER:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected identifier"
      ))
    
    exc_iden = self.current_tok.copy()
    self.advance(res)

    if self.current_tok.type != TT_NEWLINE:
      if not self.current_tok.matches(TT_KEYWORD, 'THEN'):
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          "Expected 'THEN' or newline"
        ))
      
      self.advance(res)
      catch_block = res.register(self.statement())
    else:
      self.advance(res)
      catch_block = res.register(self.statements())
      if res.error: return res

      if not self.current_tok.matches(TT_KEYWORD, 'END'):
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          "Expected 'END', 'RETURN', 'CONTINUE', 'BREAK', 'IF', 'FOR', 'WHILE', 'FUN', int, float, identifier, '+', '-', '(', '[', '{' or 'NOT'"
        ))
      
      self.advance(res)
    
    return res.success(TryNode(try_block, exc_iden, catch_block, pos_start, self.current_tok.pos_end.copy()))

  def switch_statement(self):
    res = ParseResult()
    ("in switch_statement()")
    pos_start = self.current_tok.pos_start

    ("before condition")
    condition = res.register(self.expr())
    if res.error: 
      (res.error)
      return res
    ("after condition")

    if self.current_tok.type != TT_NEWLINE:
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected newline"
      ))
    self.advance(res)

    cases = []
    while self.current_tok.matches(TT_KEYWORD, "CASE"):
      self.advance(res)
      case = res.register(self.expr())
      if res.error: return res

      if self.current_tok.type != TT_NEWLINE:
        return res.failure(InvalidSyntaxError(
          self.current_tok.pos_start, self.current_tok.pos_end,
          "Expected newline"
        ))
      self.advance(res)

      ("before case")
      body = res.register(self.statements())
      ("after case")
      if res.error: return res

      cases.append((case, body))
    
    else_case = None
    if self.current_tok.matches(TT_KEYWORD, "ELSE"):
      self.advance(res)
      else_case = res.register(self.statements())
      if res.error: return res
    
    if not self.current_tok.matches(TT_KEYWORD, "END"):
      return res.failure(InvalidSyntaxError(
        self.current_tok.pos_start, self.current_tok.pos_end,
        "Expected 'END'"
      ))
    
    pos_end = self.current_tok.pos_end
    self.advance(res)

    node = SwitchNode(condition, cases, else_case, pos_start, pos_end)
    (cases)
    (node)
    return res.success(node)

  ###################################

  def bin_op(self, func_a, ops, func_b=None):
    if func_b == None:
      func_b = func_a
    
    res = ParseResult()
    left = res.register(func_a())
    if res.error: return res

    while self.current_tok.type in ops or (self.current_tok.type, self.current_tok.value) in ops:
      op_tok = self.current_tok
      self.advance(res)
      right = res.register(func_b())
      if res.error: return res
      left = BinOpNode(left, op_tok, right)

    return res.success(left)

#######################################
# RUNTIME RESULT
#######################################

class RTResult:
  def __init__(self):
    self.reset()

  def reset(self):
    self.value = None
    self.error = None
    self.func_return_value = None
    self.loop_should_continue = False
    self.loop_should_break = False

  def register(self, res):
    self.error = res.error
    self.func_return_value = res.func_return_value
    self.loop_should_continue = res.loop_should_continue
    self.loop_should_break = res.loop_should_break
    return res.value

  def success(self, value):
    self.reset()
    self.value = value
    return self

  def success_return(self, value):
    self.reset()
    self.func_return_value = value
    return self
  
  def success_continue(self):
    self.reset()
    self.loop_should_continue = True
    return self

  def success_break(self):
    self.reset()
    self.loop_should_break = True
    return self

  def failure(self, error):
    self.reset()
    self.error = error
    return self

  def should_return(self):
    # Note: this will allow you to continue and break outside the current function
    return (
      self.error or
      self.func_return_value or
      self.loop_should_continue or
      self.loop_should_break
    )

#######################################
# VALUES
#######################################

class Number(Value):
  def __init__(self, value):
    super().__init__()
    self.value = value

  def added_to(self, other):
    if isinstance(other, Number):
      return Number(self.value + other.value).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def subbed_by(self, other):
    if isinstance(other, Number):
      return Number(self.value - other.value).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def multed_by(self, other):
    if isinstance(other, Number):
      return Number(self.value * other.value).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def dived_by(self, other):
    if isinstance(other, Number):
      if other.value == 0:
        return None, RTError(
          other.pos_start, other.pos_end,
          'Division by zero',
          self.context
        )

      return Number(self.value / other.value).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def powed_by(self, other):
    if isinstance(other, Number):
      return Number(self.value ** other.value).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def get_comparison_eq(self, other):
    if isinstance(other, Number):
      return Number(int(self.value == other.value)).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def get_comparison_ne(self, other):
    if isinstance(other, Number):
      return Number(int(self.value != other.value)).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def get_comparison_lt(self, other):
    if isinstance(other, Number):
      return Number(int(self.value < other.value)).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def get_comparison_gt(self, other):
    if isinstance(other, Number):
      return Number(int(self.value > other.value)).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def get_comparison_lte(self, other):
    if isinstance(other, Number):
      return Number(int(self.value <= other.value)).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def get_comparison_gte(self, other):
    if isinstance(other, Number):
      return Number(int(self.value >= other.value)).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def anded_by(self, other):
    if isinstance(other, Number):
      return Number(int(self.value and other.value)).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def ored_by(self, other):
    if isinstance(other, Number):
      return Number(int(self.value or other.value)).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def notted(self):
    return Number(1 if self.value == 0 else 0).set_context(self.context), None

  def copy(self):
    copy = Number(self.value)
    copy.set_pos(self.pos_start, self.pos_end)
    copy.set_context(self.context)
    return copy

  def is_true(self):
    return self.value != 0

  def __str__(self):
    return str(self.value)
  
  def __repr__(self):
    return str(self.value)

Number.null = Number(0)
Number.false = Number(0)
Number.true = Number(1)
Number.math_PI = Number(math.pi)

class String(Value):
  def __init__(self, value):
    super().__init__()
    self.value = value

  def added_to(self, other):
    if isinstance(other, String):
      return String(self.value + other.value).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def multed_by(self, other):
    if isinstance(other, Number):
      return String(self.value * other.value).set_context(self.context), None
    else:
      return None, Value.illegal_operation(self, other)

  def gen(self):
    for char in self.value:
      yield RTResult().success(String(char))

  def get_index(self, index):
    if not isinstance(index, Number):
      return None, self.illegal_operation(index)
    try:
      return self.value[index.value], None
    except IndexError:
      return None, RTError(
        index.pos_start, index.pos_end,
        f"Cannot retrieve character {index} from string {self!r} because it is out of bounds.",
        self.context
      )

  def is_true(self):
    return len(self.value) > 0

  def copy(self):
    copy = String(self.value)
    copy.set_pos(self.pos_start, self.pos_end)
    copy.set_context(self.context)
    return copy

  def __str__(self):
    return self.value

  def __repr__(self):
    return f'"{self.value}"'

class List(Value):
  def __init__(self, elements):
    super().__init__()
    self.elements = elements
    self.value = elements

  def added_to(self, other):
    new_list = self.copy()
    new_list.elements.append(other)
    return new_list, None

  def subbed_by(self, other):
    if isinstance(other, Number):
      new_list = self.copy()
      try:
        new_list.elements.pop(other.value)
        return new_list, None
      except:
        return None, RTError(
          other.pos_start, other.pos_end,
          'Element at this index could not be removed from list because index is out of bounds',
          self.context
        )
    else:
      return None, Value.illegal_operation(self, other)

  def multed_by(self, other):
    if isinstance(other, List):
      new_list = self.copy()
      new_list.elements.extend(other.elements)
      return new_list, None
    else:
      return None, Value.illegal_operation(self, other)

  def dived_by(self, other):
    if isinstance(other, Number):
      try:
        return self.elements[other.value], None
      except:
        return None, RTError(
          other.pos_start, other.pos_end,
          'Element at this index could not be retrieved from list because index is out of bounds',
          self.context
        )
    else:
      return None, Value.illegal_operation(self, other)
  
  def gen(self):
    for elt in self.elements:
      yield RTResult().success(elt)

  def get_index(self, index):
    if not isinstance(index, Number):
      return None, self.illegal_operation(index)
    try:
      return self.elements[index.value], None
    except IndexError:
      return None, RTError(
        index.pos_start, index.pos_end,
        f"Cannot retrieve element {index} from list {self!r} because it is out of bounds.",
        self.context
      )
  
  def set_index(self, index, value):
    if not isinstance(index, Number):
      return None, self.illegal_operation(index)
    try:
      self.elements[index.value] = value
    except IndexError:
      return None, RTError(
        index.pos_start, index.pos_end,
        f"Cannot set element {index} from list {self!r} to {value!r} because it is out of bounds.",
        self.context
      )
    
    return self, None

  def copy(self):
    copy = List(self.elements)
    copy.set_pos(self.pos_start, self.pos_end)
    copy.set_context(self.context)
    return copy

  def __str__(self):
    return ", ".join([str(x) for x in self.elements])

  def __repr__(self):
    return f'[{", ".join([repr(x) for x in self.elements])}]'

class BaseFunction(Value):
  def __init__(self, name):
    super().__init__()
    self.name = name or "<anonymous>"

  def set_context(self, context=None):
    if hasattr(self, "context") and self.context: return self
    return super().set_context(context)

  def generate_new_context(self):
    new_context = Context(self.name, self.context, self.pos_start)
    new_context.symbol_table = SymbolTable(new_context.parent.symbol_table)
    return new_context

  def check_args(self, arg_names, args, defaults):
    res = RTResult()

    if len(args) > len(arg_names):
      return res.failure(RTError(
        self.pos_start, self.pos_end,
        f"{len(args) - len(arg_names)} too many args passed into {self}",
        self.context
      ))
    
    if len(args) < len(arg_names) - len(list(filter(lambda default: default is not None, defaults))):
      return res.failure(RTError(
        self.pos_start, self.pos_end,
        f"{(len(arg_names) - len(list(filter(lambda default: default is not None, defaults)))) - len(args)} too few args passed into {self}",
        self.context
      ))

    return res.success(None)

  def populate_args(self, arg_names, args, defaults, dynamics, exec_ctx):
    res = RTResult()
    for i in range(len(arg_names)):
      arg_name = arg_names[i]
      dynamic = dynamics[i]
      arg_value = defaults[i] if i >= len(args) else args[i]
      if dynamic is not None:
        dynamic_context = Context(f"{self.name} (dynamic argument '{arg_name}')", exec_ctx, dynamic.pos_start.copy())
        dynamic_context.symbol_table = SymbolTable(exec_ctx.symbol_table)
        dynamic_context.symbol_table.set("$", arg_value)
        arg_value = res.register(Interpreter().visit(dynamic, dynamic_context))
        if res.should_return(): return res
      arg_value.set_context(exec_ctx)
      exec_ctx.symbol_table.set(arg_name, arg_value)
    return res.success(None)

  def check_and_populate_args(self, arg_names, args, defaults, dynamics, exec_ctx):
    res = RTResult()
    res.register(self.check_args(arg_names, args, defaults))
    if res.should_return(): return res
    res.register(self.populate_args(arg_names, args, defaults, dynamics, exec_ctx))
    if res.should_return(): return res
    return res.success(None)

class Function(BaseFunction):
  def __init__(self, name, body_node, arg_names, defaults, dynamics, should_auto_return):
    super().__init__(name)
    self.body_node = body_node
    self.arg_names = arg_names
    self.defaults = defaults
    self.dynamics = dynamics
    self.should_auto_return = should_auto_return

  def execute(self, args):
    res = RTResult()
    interpreter = Interpreter()
    exec_ctx = self.generate_new_context()

    res.register(self.check_and_populate_args(self.arg_names, args, self.defaults, self.dynamics, exec_ctx))
    if res.should_return(): return res

    value = res.register(interpreter.visit(self.body_node, exec_ctx))
    if res.should_return() and res.func_return_value == None: return res

    ret_value = (value if self.should_auto_return else None) or res.func_return_value or Number.null
    return res.success(ret_value)

  def copy(self):
    copy = Function(self.name, self.body_node, self.arg_names, self.defaults, self.dynamics, self.should_auto_return)
    copy.set_context(self.context)
    copy.set_pos(self.pos_start, self.pos_end)
    return copy

  def __repr__(self):
    return f"<function {self.name}>"

class BuiltInFunction(BaseFunction):
  def __init__(self, name):
    super().__init__(name)

  def execute(self, args):
    res = RTResult()
    exec_ctx = self.generate_new_context()

    method_name = f'execute_{self.name}'
    method = getattr(self, method_name, self.no_execute_method)

    res.register(self.check_and_populate_args(method.arg_names, args, method.defaults, method.dynamics, exec_ctx))
    if res.should_return(): return res

    return_value = res.register(method(exec_ctx))
    if res.should_return(): return res
    return res.success(return_value)
  
  def no_execute_method(self, node, context):
    raise Exception(f'No execute_{self.name} method defined')

  def copy(self):
    copy = BuiltInFunction(self.name)
    copy.set_context(self.context)
    copy.set_pos(self.pos_start, self.pos_end)
    return copy

  def __repr__(self):
    return f"<built-in function {self.name}>"

  #####################################

  # Decorator for built-in functions
  @staticmethod
  def args(arg_names, defaults=None, dynamics=None):
    if defaults is None:
      defaults = [None] * len(arg_names)
    if dynamics is None:
      dynamics = [None] * len(arg_names)
    def _args(f):
      f.arg_names = arg_names
      f.defaults = defaults
      f.dynamics = dynamics
      return f
    return _args

  #####################################

  @args(['value'])
  def execute_print(self, exec_ctx):
    print(str(exec_ctx.symbol_table.get('value')))
    return RTResult().success(Number.null)
  
  @args(['value'])
  def execute_print_ret(self, exec_ctx):
    return RTResult().success(String(str(exec_ctx.symbol_table.get('value'))))
  
  @args([])
  def execute_input(self, exec_ctx):
    text = input()
    return RTResult().success(String(text))
  
  @args([])
  def execute_input_int(self, exec_ctx):
    while True:
      text = input()
      try:
        number = int(text)
        break
      except ValueError:
        print(f"'{text}' must be an integer. Try again!")
    return RTResult().success(Number(number))
  
  @args([])
  def execute_clear(self, exec_ctx):
    os.system('cls' if os.name == 'nt' else 'cls') 
    return RTResult().success(Number.null)

  @args(["value"])
  def execute_is_number(self, exec_ctx):
    is_number = isinstance(exec_ctx.symbol_table.get("value"), Number)
    return RTResult().success(Number.true if is_number else Number.false)
  
  @args(["value"])
  def execute_is_string(self, exec_ctx):
    is_number = isinstance(exec_ctx.symbol_table.get("value"), String)
    return RTResult().success(Number.true if is_number else Number.false)
  
  @args(["value"])
  def execute_is_list(self, exec_ctx):
    is_number = isinstance(exec_ctx.symbol_table.get("value"), List)
    return RTResult().success(Number.true if is_number else Number.false)
  
  @args(["value"])
  def execute_is_function(self, exec_ctx):
    is_number = isinstance(exec_ctx.symbol_table.get("value"), BaseFunction)
    return RTResult().success(Number.true if is_number else Number.false)
  
  @args(["list", "value"])
  def execute_append(self, exec_ctx):
    list_ = exec_ctx.symbol_table.get("list")
    value = exec_ctx.symbol_table.get("value")

    if not isinstance(list_, List):
      return RTResult().failure(RTError(
        self.pos_start, self.pos_end,
        "First argument must be list",
        exec_ctx
      ))

    list_.elements.append(value)
    return RTResult().success(Number.null)
  
  @args(["list", "index"])
  def execute_pop(self, exec_ctx):
    list_ = exec_ctx.symbol_table.get("list")
    index = exec_ctx.symbol_table.get("index")

    if not isinstance(list_, List):
      return RTResult().failure(RTError(
        self.pos_start, self.pos_end,
        "First argument must be list",
        exec_ctx
      ))

    if not isinstance(index, Number):
      return RTResult().failure(RTError(
        self.pos_start, self.pos_end,
        "Second argument must be number",
        exec_ctx
      ))

    try:
      element = list_.elements.pop(index.value)
    except:
      return RTResult().failure(RTError(
        self.pos_start, self.pos_end,
        'Element at this index could not be removed from list because index is out of bounds',
        exec_ctx
      ))
    return RTResult().success(element)
  
  @args(["listA", "listB"])
  def execute_extend(self, exec_ctx):
    listA = exec_ctx.symbol_table.get("listA")
    listB = exec_ctx.symbol_table.get("listB")

    if not isinstance(listA, List):
      return RTResult().failure(RTError(
        self.pos_start, self.pos_end,
        "First argument must be list",
        exec_ctx
      ))

    if not isinstance(listB, List):
      return RTResult().failure(RTError(
        self.pos_start, self.pos_end,
        "Second argument must be list",
        exec_ctx
      ))

    listA.elements.extend(listB.elements)
    return RTResult().success(Number.null)
  
  @args(["list"])
  def execute_len(self, exec_ctx):
    list_ = exec_ctx.symbol_table.get("list")

    if not isinstance(list_, List):
      return RTResult().failure(RTError(
        self.pos_start, self.pos_end,
        "Argument must be list",
        exec_ctx
      ))

    return RTResult().success(Number(len(list_.elements)))
  
  @args(["fn"])
  def execute_run(self, exec_ctx):
    fn = exec_ctx.symbol_table.get("fn")

    if not isinstance(fn, String):
      return RTResult().failure(RTError(
        self.pos_start, self.pos_end,
        "Second argument must be string",
        exec_ctx
      ))

    print("WARNING: run() is deprecated. Use 'IMPORT' instead")
    fn = fn.value

    try:
      with open(fn, "r") as f:
        script = f.read()
    except Exception as e:
      return RTResult().failure(RTError(
        self.pos_start, self.pos_end,
        f"Failed to load script \"{fn}\"\n" + str(e),
        exec_ctx
      ))

    _, error = run(fn, script)
    
    if error:
      return RTResult().failure(RTError(
        self.pos_start, self.pos_end,
        f"Failed to finish executing script \"{fn}\"\n" +
        error.as_string(),
        exec_ctx
      ))

    return RTResult().success(Number.null)

  @args(["fn", "mode"], [None, String("r")])
  def execute_open(self, exec_ctx):
    sym = exec_ctx.symbol_table
    fake_pos = create_fake_pos("<built-in function open>")
    res = RTResult()

    fn = sym.get("fn")
    if not isinstance(fn, String):
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"1st argument of function 'open' ('fn') must be String",
        exec_ctx
      ))
    fn = fn.value

    mode = sym.get("mode")
    if not isinstance(mode, String):
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"2nd argument of function 'open' ('mode') must be String",
        exec_ctx
      ))
    mode = mode.value

    try:
      f = open(fn, mode)
    except (TypeError, OSError) as err:
      if isinstance(err, TypeError):
        return res.failure(RTError(
          fake_pos, fake_pos,
          f"Invalid file open mode: '{mode}'",
          exec_ctx
        ))
      elif isinstance(err, FileNotFoundError):
        return res.failure(RTError(
          fake_pos, fake_pos,
          f"Cannot find file '{fn}'",
          exec_ctx
        ))
      else:
        return res.failure(RTError(
          fake_pos, fake_pos,
          f"{err.args[-1]}",
          exec_ctx
        ))
    
    fd = f.fileno()
    files[fd] = f

    return res.success(Number(fd).set_pos(fake_pos, fake_pos).set_context(exec_ctx))
  
  @args(["fd", "bytes"])
  def execute_read(self, exec_ctx):
    sym = exec_ctx.symbol_table
    fake_pos = create_fake_pos("<built-in function read>")
    res = RTResult()

    fd = sym.get("fd")
    if not isinstance(fd, Number):
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"1st argument of function 'read' ('fd') must be Number",
        exec_ctx
      ))
    fd = fd.value

    bts = sym.get("bytes")
    if not isinstance(bts, Number):
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"2nd argument of function 'read' ('bytes') must be Number",
        exec_ctx
      ))
    bts = bts.value

    try:
      result = os.read(fd, bts).decode("utf-8")
    except OSError:
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"Invalid file descriptor: {fd}",
        exec_ctx
      ))
    
    return res.success(String(result).set_pos(fake_pos, fake_pos).set_context(exec_ctx))

  @args(["fd", "bytes"])
  def execute_write(self, exec_ctx):
    sym = exec_ctx.symbol_table
    fake_pos = create_fake_pos("<built-in function write>")
    res = RTResult()

    fd = sym.get("fd")
    if not isinstance(fd, Number):
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"1st argument of function 'write' ('fd') must be Number",
        exec_ctx
      ))
    fd = fd.value

    bts = sym.get("bytes")
    if not isinstance(bts, String):
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"2nd argument of function 'write' ('bytes') must be String",
        exec_ctx
      ))
    bts = bts.value

    try:
      num = os.write(fd, bytes(bts, "utf-8"))
    except OSError:
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"Invalid file descriptor: {fd}",
        exec_ctx
      ))
    
    return res.success(Number(num).set_pos(fake_pos, fake_pos).set_context(exec_ctx))

  @args(["fd"])
  def execute_close(self, exec_ctx):
    sym = exec_ctx.symbol_table
    fake_pos = create_fake_pos("<built-in function close>")
    res = RTResult()

    fd = sym.get("fd")
    if not isinstance(fd, Number):
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"1st argument of function 'close' ('fd') must be Number",
        exec_ctx
      ))
    fd = fd.value
    std_desc = ["stdin", "stdout", "stderr"]

    if fd < 3:
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"Cannot close {std_desc[fd]}",
        exec_ctx
      ))

    try:
      os.close(fd)
    except OSError:
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"Invalid file descriptor '{fd}'",
        exec_ctx
      ))
    
    del files[fd]

    return res.success(Number.null)

  @args(["secs"])
  def execute_wait(self, exec_ctx):
    sym = exec_ctx.symbol_table
    fake_pos = create_fake_pos("<built-in function wait>")
    res = RTResult()

    secs = sym.get("secs")
    if not isinstance(secs, Number):
      return res.failure(RTError(
        fake_pos, fake_pos,
        f"1st argument of function 'wait' ('secs') must be Number",
        exec_ctx
      ))
    secs = secs.value

    time.sleep(secs)

    return RTResult().success(Number.null)

BuiltInFunction.print       = BuiltInFunction("print")
BuiltInFunction.print_ret   = BuiltInFunction("print_ret")
BuiltInFunction.input       = BuiltInFunction("input")
BuiltInFunction.input_int   = BuiltInFunction("input_int")
BuiltInFunction.clear       = BuiltInFunction("clear")
BuiltInFunction.is_number   = BuiltInFunction("is_number")
BuiltInFunction.is_string   = BuiltInFunction("is_string")
BuiltInFunction.is_list     = BuiltInFunction("is_list")
BuiltInFunction.is_function = BuiltInFunction("is_function")
BuiltInFunction.append      = BuiltInFunction("append")
BuiltInFunction.pop         = BuiltInFunction("pop")
BuiltInFunction.extend      = BuiltInFunction("extend")
BuiltInFunction.len					= BuiltInFunction("len")
BuiltInFunction.run					= BuiltInFunction("run")
BuiltInFunction.open        = BuiltInFunction("open")
BuiltInFunction.read        = BuiltInFunction("read")
BuiltInFunction.write       = BuiltInFunction("write")
BuiltInFunction.close       = BuiltInFunction("close")
BuiltInFunction.wait        = BuiltInFunction("wait")

class Iterator(Value):
  def __init__(self, generator):
    super().__init__()
    self.it = generator()
  
  def iter(self):
    return self
  
  def __iter__(self):
    return self

  def __next__(self):
    return next(self.it)
  
  def __str__(self):
    return '<iterator>'

  def __repr__(self):
    return str(self)
  
  def __getattr__(self, attr):
    if attr.startswith("get_comparison_"):
      return lambda self, other: Number(self is other), None

  def copy(self):
    return Iterator(self.it)

class Dict(Value):
  def __init__(self, values):
    super().__init__()
    self.values = values
    self.value = values

  def added_to(self, other):
    if not isinstance(other, Dict):
      return None, self.illegal_operation(other)
    
    new_dict = self.copy()
    for key, value in other.values.items():
      new_dict.values[key] = value
    
    return new_dict, None
  
  def gen(self):
    fake_pos = create_fake_pos("<dict key>")
    for key in self.values.keys():
      key_as_value = String(key).set_pos(fake_pos, fake_pos).set_context(self.context)
      yield RTResult().success(key_as_value)
  
  def get_index(self, index):
    if not isinstance(index, String):
      return None, self.illegal_operation(index)
    
    try:
      return self.values[index.value], None
    except KeyError:
      return None, RTError(
        self.pos_start, self.pos_end,
        f"Could not find key {index!r} in dict {self!r}",
        self.context
      )
  
  def set_index(self, index, value):
    if not isinstance(index, String):
      return None, self.illegal_operation(index)
    
    self.values[index.value] = value

    return self, None
  
  def __str__(self):
    result = ""
    for key, value in self.values.items():
      result += f"{key}: {value}\n"
    
    return result[:-1]
  
  def __repr__(self):
    result = "{"
    for key, value in self.values.items():
      result += f"{key!r}: {value!r}, "
    
    return result[:-2] + "}"

  def copy(self):
    return Dict(self.values).set_pos(self.pos_start, self.pos_end).set_context(self.context)

#######################################
# CONTEXT
#######################################

class Context:
  def __init__(self, display_name, parent=None, parent_entry_pos=None):
    self.display_name = display_name
    self.parent = parent
    self.parent_entry_pos = parent_entry_pos
    self.symbol_table = None

#######################################
# SYMBOL TABLE
#######################################

class SymbolTable:
  def __init__(self, parent=None):
    self.symbols = {}
    self.parent = parent

  def get(self, name):
    value = self.symbols.get(name, None)
    if value == None and self.parent:
      return self.parent.get(name)
    return value

  def set(self, name, value):
    self.symbols[name] = value

  def remove(self, name):
    del self.symbols[name]

#######################################
# INTERPRETER
#######################################

class Interpreter:
  def visit(self, node, context):
    method_name = f'visit_{type(node).__name__}'
    method = getattr(self, method_name, self.no_visit_method)
    return method(node, context)

  def no_visit_method(self, node, context):
    raise Exception(f'No visit_{type(node).__name__} method defined')

  ###################################

  def visit_NumberNode(self, node, context):
    return RTResult().success(
      Number(node.tok.value).set_context(context).set_pos(node.pos_start, node.pos_end)
    )

  def visit_StringNode(self, node, context):
    return RTResult().success(
      String(node.tok.value).set_context(context).set_pos(node.pos_start, node.pos_end)
    )

  def visit_ListNode(self, node, context):
    res = RTResult()
    elements = []

    for element_node in node.element_nodes:
      elements.append(res.register(self.visit(element_node, context)))
      if res.should_return(): return res

    return res.success(
      List(elements).set_context(context).set_pos(node.pos_start, node.pos_end)
    )

  def visit_VarAccessNode(self, node, context):
    res = RTResult()
    var_name = node.var_name_tok.value
    value = context.symbol_table.get(var_name)

    if not value:
      return res.failure(RTError(
        node.pos_start, node.pos_end,
        f"'{var_name}' is not defined",
        context
      ))

    value = value.copy().set_pos(node.pos_start, node.pos_end).set_context(context)
    return res.success(value)

  def visit_VarAssignNode(self, node, context):
    res = RTResult()
    var_name = node.var_name_tok.value
    value = res.register(self.visit(node.value_node, context))
    if res.should_return(): return res

    context.symbol_table.set(var_name, value)
    return res.success(value)

  def visit_BinOpNode(self, node, context):
    res = RTResult()
    left = res.register(self.visit(node.left_node, context))
    if res.should_return(): return res
    right = res.register(self.visit(node.right_node, context))
    if res.should_return(): return res

    if node.op_tok.type == TT_PLUS:
      result, error = left.added_to(right)
    elif node.op_tok.type == TT_MINUS:
      result, error = left.subbed_by(right)
    elif node.op_tok.type == TT_MUL:
      result, error = left.multed_by(right)
    elif node.op_tok.type == TT_DIV:
      result, error = left.dived_by(right)
    elif node.op_tok.type == TT_POW:
      result, error = left.powed_by(right)
    elif node.op_tok.type == TT_EE:
      result, error = left.get_comparison_eq(right)
    elif node.op_tok.type == TT_NE:
      result, error = left.get_comparison_ne(right)
    elif node.op_tok.type == TT_LT:
      result, error = left.get_comparison_lt(right)
    elif node.op_tok.type == TT_GT:
      result, error = left.get_comparison_gt(right)
    elif node.op_tok.type == TT_LTE:
      result, error = left.get_comparison_lte(right)
    elif node.op_tok.type == TT_GTE:
      result, error = left.get_comparison_gte(right)
    elif node.op_tok.matches(TT_KEYWORD, 'AND'):
      result, error = left.anded_by(right)
    elif node.op_tok.matches(TT_KEYWORD, 'OR'):
      result, error = left.ored_by(right)

    if error:
      return res.failure(error)
    else:
      return res.success(result.set_pos(node.pos_start, node.pos_end))

  def visit_UnaryOpNode(self, node, context):
    res = RTResult()
    number = res.register(self.visit(node.node, context))
    if res.should_return(): return res

    error = None

    if node.op_tok.type == TT_MINUS:
      number, error = number.multed_by(Number(-1))
    elif node.op_tok.matches(TT_KEYWORD, 'NOT'):
      number, error = number.notted()

    if error:
      return res.failure(error)
    else:
      return res.success(number.set_pos(node.pos_start, node.pos_end))

  def visit_IfNode(self, node, context):
    res = RTResult()

    for condition, expr, should_return_null in node.cases:
      condition_value = res.register(self.visit(condition, context))
      if res.should_return(): return res

      if condition_value.is_true():
        expr_value = res.register(self.visit(expr, context))
        if res.should_return(): return res
        return res.success(Number.null if should_return_null else expr_value)

    if node.else_case:
      expr, should_return_null = node.else_case
      expr_value = res.register(self.visit(expr, context))
      if res.should_return(): return res
      return res.success(Number.null if should_return_null else expr_value)

    return res.success(Number.null)

  def visit_ForNode(self, node, context):
    res = RTResult()
    elements = []

    start_value = res.register(self.visit(node.start_value_node, context))
    if res.should_return(): return res

    end_value = res.register(self.visit(node.end_value_node, context))
    if res.should_return(): return res

    if node.step_value_node:
      step_value = res.register(self.visit(node.step_value_node, context))
      if res.should_return(): return res
    else:
      step_value = Number(1)

    i = start_value.value

    if step_value.value >= 0:
      condition = lambda: i < end_value.value
    else:
      condition = lambda: i > end_value.value
    
    while condition():
      context.symbol_table.set(node.var_name_tok.value, Number(i))
      i += step_value.value

      value = res.register(self.visit(node.body_node, context))
      if res.should_return() and res.loop_should_continue == False and res.loop_should_break == False: return res
      
      if res.loop_should_continue:
        continue
      
      if res.loop_should_break:
        break

      elements.append(value)

    return res.success(
      Number.null if node.should_return_null else
      List(elements).set_context(context).set_pos(node.pos_start, node.pos_end)
    )

  def visit_WhileNode(self, node, context):
    res = RTResult()
    elements = []

    while True:
      condition = res.register(self.visit(node.condition_node, context))
      if res.should_return(): return res

      if not condition.is_true():
        break

      value = res.register(self.visit(node.body_node, context))
      if res.should_return() and res.loop_should_continue == False and res.loop_should_break == False: return res

      if res.loop_should_continue:
        continue
      
      if res.loop_should_break:
        break

      elements.append(value)

    return res.success(
      Number.null if node.should_return_null else
      List(elements).set_context(context).set_pos(node.pos_start, node.pos_end)
    )

  def visit_FuncDefNode(self, node, context):
    res = RTResult()

    func_name = node.var_name_tok.value if node.var_name_tok else None
    body_node = node.body_node
    arg_names = [arg_name.value for arg_name in node.arg_name_toks]
    defaults = []
    for default in node.defaults:
      if default is None:
        defaults.append(None)
        continue
      default_value = res.register(self.visit(default, context))
      if res.should_return(): return res
      defaults.append(default_value)
    
    func_value = Function(func_name, body_node, arg_names, defaults, node.dynamics, node.should_auto_return).set_context(context).set_pos(node.pos_start, node.pos_end)
    
    if node.var_name_tok:
      context.symbol_table.set(func_name, func_value)

    return res.success(func_value)

  def visit_CallNode(self, node, context):
    res = RTResult()
    args = []

    value_to_call = res.register(self.visit(node.node_to_call, context))
    if res.should_return(): return res
    value_to_call = value_to_call.copy().set_pos(node.pos_start, node.pos_end)

    for arg_node in node.arg_nodes:
      args.append(res.register(self.visit(arg_node, context)))
      if res.should_return(): return res

    return_value = res.register(value_to_call.execute(args))
    if res.should_return(): return res
    return_value = return_value.copy().set_pos(node.pos_start, node.pos_end).set_context(context)
    return res.success(return_value)

  def visit_ReturnNode(self, node, context):
    res = RTResult()

    if node.node_to_return:
      value = res.register(self.visit(node.node_to_return, context))
      if res.should_return(): return res
    else:
      value = Number.null
    
    return res.success_return(value)

  def visit_ContinueNode(self, node, context):
    return RTResult().success_continue()

  def visit_BreakNode(self, node, context):
    return RTResult().success_break()
  
  def visit_ImportNode(self, node, context):
    res = RTResult()
    filename = res.register(self.visit(node.string_node, context))
    code = None

    for path in IMPORT_PATHS:
      try:
        filepath = os.path.join(path, filename.value)
        with open(filepath, "r") as f:
          code = f.read()
          beginning = "/" if filepath.startswith("/") else ""
          split = filepath.split("/")
          split = beginning + "/".join(split[:-1]), split[-1]
          os.chdir(split[0])
          filename = split[1]
          break
      except FileNotFoundError:
        continue
    
    if code is None:
      return res.failure(RTError(
        node.string_node.pos_start.copy(), node.string_node.pos_end.copy(),
        f"Can't find file '{filepath}' in '{IMPORT_PATH_NAME}'. Please add the directory your file is into that file",
        context
      ))
    
    _, error = run(filename, code, context, node.pos_start.copy())
    if error: return res.failure(error)

    return res.success(Number.null)
  
  def visit_DoNode(self, node, context):
    res = RTResult()
    new_context = Context("<DO statement>", context, node.pos_start.copy())
    new_context.symbol_table = SymbolTable(context.symbol_table)
    res.register(self.visit(node.statements, new_context))

    return_value = res.func_return_value
    if res.should_return() and return_value is None: return res

    return_value = return_value or Number.null

    return res.success(return_value)
  
  def visit_TryNode(self, node: TryNode, context):
    res = RTResult()
    res.register(self.visit(node.try_block, context))
    handled_error = res.error
    if res.should_return() and res.error is None: return res

    elif handled_error is not None:
      var_name = node.exc_iden.value
      context.symbol_table.set(var_name, res.error)
      res.error = None

      res.register(self.visit(node.catch_block, context))
      if res.error: 
        return res.failure(TryError(
          res.error.pos_start, res.error.pos_end, res.error.details, res.error.context, handled_error
        ))
      return res.success(Number.null)
    else:
      return res.success(Number.null)
  
  def visit_ForInNode(self, node, context):
    res = RTResult()
    var_name = node.var_name_tok.value
    body = node.body_node
    should_return_null = node.should_return_null

    iterable = res.register(self.visit(node.iterable_node, context))
    it = iterable.iter()

    elements = []

    for it_res in it:
      elt = res.register(it_res)
      if res.should_return(): return res

      context.symbol_table.set(var_name, elt)

      elements.append(res.register(self.visit(body, context)))
      if res.should_return(): return res
    
    if should_return_null: return res.success(Number.null)
    return res.success(elements)

  def visit_IndexGetNode(self, node, context):
    res = RTResult()
    indexee = res.register(self.visit(node.indexee, context))
    if res.should_return(): return res

    index = res.register(self.visit(node.index, context))
    if res.should_return(): return res

    result, error = indexee.get_index(index)
    if error: return res.failure(error)
    return res.success(result)

  def visit_IndexSetNode(self, node, context):
    res = RTResult()
    indexee = res.register(self.visit(node.indexee, context))
    if res.should_return(): return res

    index = res.register(self.visit(node.index, context))
    if res.should_return(): return res

    value = res.register(self.visit(node.value, context))
    if res.should_return(): return res

    result, error = indexee.set_index(index, value)
    if error: return res.failure(error)

    return res.success(result)

  def visit_DictNode(self, node, context):
    res = RTResult()
    values = {}

    for key_node, value_node in node.pairs:
      key = res.register(self.visit(key_node, context))
      if res.should_return(): return res

      if not isinstance(key, String):
        return res.failure(RTError(
          key_node.pos_start, key_node.pos_end,
          f"Non-string key for dict: '{key!r}'",
          context
        ))

      value = res.register(self.visit(value_node, context))
      if res.should_return(): return res

      values[key.value] = value
    
    return res.success(Dict(values))

  def visit_SwitchNode(self, node, context):
    res = RTResult()
    condition = res.register(self.visit(node.condition, context))
    if res.should_return(): return res

    for case, body in node.cases:
      case = res.register(self.visit(case, context))
      if res.should_return(): return res

      eq, error = condition.get_comparison_eq(case)
      if error: return res.failure(error)

      if eq.value:
        res.register(self.visit(body, context))
        if res.should_return(): return res
        break
    else: # no break
      else_case = node.else_case
      if else_case:
        res.register(self.visit(else_case, context))
        if res.should_return(): return res
    
    return res.success(Number.null)

#######################################
# CREATE FAKE POS
#######################################

def create_fake_pos(desc: str) -> Position:
  return Position(0, 0, 0, desc, "<native code>")

#######################################
# RUN
#######################################

def make_argv():
  argv = []
  fake_pos = create_fake_pos("<argv>")
  for arg in sys.argv[1:]:
    argv.append(String(arg).set_pos(fake_pos, fake_pos))
  return List(argv).set_pos(fake_pos, fake_pos)

global_symbol_table = SymbolTable()
global_symbol_table.set("NULL", Number.null)
global_symbol_table.set("FALSE", Number.false)
global_symbol_table.set("TRUE", Number.true)
global_symbol_table.set("ARGV", make_argv())
global_symbol_table.set("MATH_PI", Number.math_PI)
global_symbol_table.set("PRINT", BuiltInFunction.print)
global_symbol_table.set("PRINT_RET", BuiltInFunction.print_ret)
global_symbol_table.set("INPUT", BuiltInFunction.input)
global_symbol_table.set("INPUT_INT", BuiltInFunction.input_int)
global_symbol_table.set("CLEAR", BuiltInFunction.clear)
global_symbol_table.set("CLS", BuiltInFunction.clear)
global_symbol_table.set("IS_NUM", BuiltInFunction.is_number)
global_symbol_table.set("IS_STR", BuiltInFunction.is_string)
global_symbol_table.set("IS_LIST", BuiltInFunction.is_list)
global_symbol_table.set("IS_FUN", BuiltInFunction.is_function)
global_symbol_table.set("APPEND", BuiltInFunction.append)
global_symbol_table.set("POP", BuiltInFunction.pop)
global_symbol_table.set("EXTEND", BuiltInFunction.extend)
global_symbol_table.set("LEN", BuiltInFunction.len)
global_symbol_table.set("RUN", BuiltInFunction.run)
global_symbol_table.set("OPEN", BuiltInFunction.open)
global_symbol_table.set("READ", BuiltInFunction.read)
global_symbol_table.set("WRITE", BuiltInFunction.write)
global_symbol_table.set("CLOSE", BuiltInFunction.close)
global_symbol_table.set("WAIT", BuiltInFunction.wait)


def run(fn, text, context=None, entry_pos=None):
  # Generate tokens
  lexer = Lexer(fn, text)
  tokens, error = lexer.make_tokens()
  if error: return None, error
  
  # Generate AST
  parser = Parser(tokens)
  ast = parser.parse()
  if ast.error: return None, ast.error

  # Run program
  interpreter = Interpreter()
  context_was_none = context is None
  context = Context('<program>', context, entry_pos)
  if context_was_none:
    context.symbol_table = global_symbol_table
  else:
    context.symbol_table = context.parent.symbol_table
  result = interpreter.visit(ast.node, context)
  ret = result.func_return_value
  if context_was_none and ret:
    if not isinstance(ret, Number):
      return None, RTError(
        ret.pos_start, ret.pos_end,
        "Exit code must be Number",
        context
      )
    exit(ret.value)

  return result.value, result.error
