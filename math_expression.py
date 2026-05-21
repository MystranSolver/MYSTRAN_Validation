import math
import re
from typing import Dict

class MathExpressionError(Exception):
    """Custom exception for math expression errors"""
    pass

class Token:
    """Token types for the lexer"""
    def __init__(self, type_, value=None):
        self.type = type_
        self.value = value
    
    def __repr__(self):
        return f"Token({self.type}, {self.value})"

class Lexer:
    """Converts expression string into tokens"""
    
    def __init__(self, expression: str):
        self.expression = expression
        self.position = 0
        self.tokens = []
    
    def tokenize(self):
        """Convert expression string to list of tokens"""
        pos = 0
        length = len(self.expression)
        
        while pos < length:
            # Skip whitespace
            if self.expression[pos].isspace():
                pos += 1
                continue

            # Match numbers with exponential notation
            # Pattern for: integer, float, scientific notation (e.g., 1.23e-4, 2E+5, .5e3, 1e10)
            # Matches: 123, 123.456, 0.123, .123, 123e10, 123E-5, 123.456e+7, etc.
            match = re.match(r'(\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', self.expression[pos:])
            if match:
                value_str = match.group(0)
                try:
                    value = float(value_str)
                    self.tokens.append(Token('NUMBER', value))
                    pos += match.end()
                    continue
                except ValueError:
                    pass  # If conversion fails, continue to other patterns

            if self.expression[pos:pos+3] == 'nan':
                self.tokens.append(Token('NUMBER', float('nan')))
                pos += 3
                continue

            if self.expression[pos:pos+2] == 'pi':
                self.tokens.append(Token('NUMBER', math.pi))
                pos += 2
                continue
            
            # Match variables: Start with capital letter, then can contain capital letters, digits, /, -, ,
            # Variable pattern: [A-Z][A-Z0-9/-,]*
            match = re.match(r'[A-Z][A-Z0-9/\-,]*', self.expression[pos:])
            if match:
                value = match.group(0)
                self.tokens.append(Token('VARIABLE', value))
                pos += match.end()
                continue

            # Match functions: Start with lower case letter
            match = re.match(r'[a-z][a-z0-9]*', self.expression[pos:])
            if match:
                value = match.group(0)
                # Check if it's a function name
                if value == 'atan2':
                    self.tokens.append(Token('FUNCTION', value.lower()))
                elif value == 'sqrt':
                    self.tokens.append(Token('FUNCTION', value.lower()))
                else:
                    self.tokens.append(Token('VARIABLE', value))
                pos += match.end()
                continue
            
            # Match ** operator (must come before single *)
            if self.expression[pos:pos+2] == '**':
                self.tokens.append(Token('OPERATOR', '**'))
                pos += 2
                continue
            
            # Match single character operators
            if self.expression[pos] in '+-*/':
                self.tokens.append(Token('OPERATOR', self.expression[pos]))
                pos += 1
                continue
            
            # Match parentheses and comma
            if self.expression[pos] == '(':
                self.tokens.append(Token('LPAREN', '('))
                pos += 1
                continue
            
            if self.expression[pos] == ')':
                self.tokens.append(Token('RPAREN', ')'))
                pos += 1
                continue
            
            if self.expression[pos] == ',':
                self.tokens.append(Token('COMMA', ','))
                pos += 1
                continue
            
            # If we get here, we have an invalid character
            raise MathExpressionError(f"Invalid character at position {pos}: '{self.expression[pos]}'")
        
        return self.tokens

class Parser:
    """Parses tokens into an Abstract Syntax Tree (AST)"""
    
    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0
    
    def peek(self):
        """Look at current token without consuming it"""
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None
    
    def consume(self, expected_type=None, expected_value=None):
        """Consume current token and move to next"""
        token = self.peek()
        if not token:
            raise MathExpressionError("Unexpected end of expression")
        
        if expected_type and token.type != expected_type:
            raise MathExpressionError(f"Expected {expected_type}, got {token.type}")
        
        if expected_value and token.value != expected_value:
            raise MathExpressionError(f"Expected '{expected_value}', got '{token.value}'")
        
        self.position += 1
        return token
    
    def parse(self):
        """Parse tokens into AST"""
        if not self.tokens:
            return None
        return self.parse_expression()
    
    def parse_expression(self):
        """Parse addition and subtraction"""
        node = self.parse_term()
        
        while self.peek() and self.peek().type == 'OPERATOR' and self.peek().value in ('+', '-'):
            op = self.consume().value
            right = self.parse_term()
            node = ('binary_op', op, node, right)
        
        return node
    
    def parse_term(self):
        """Parse multiplication and division"""
        node = self.parse_power()
        
        while self.peek() and self.peek().type == 'OPERATOR' and self.peek().value in ('*', '/'):
            op = self.consume().value
            right = self.parse_power()
            node = ('binary_op', op, node, right)
        
        return node
    
    def parse_power(self):
        """Parse exponentiation (right-associative)"""
        node = self.parse_factor()
        
        if self.peek() and self.peek().type == 'OPERATOR' and self.peek().value == '**':
            self.consume()
            right = self.parse_power()  # Right-associative
            node = ('binary_op', '**', node, right)
        
        return node
    
    def parse_factor(self):
        """Parse numbers, variables, functions, and parenthesized expressions"""
        token = self.peek()
        
        if not token:
            raise MathExpressionError("Unexpected end of expression")
        
        # Handle unary plus/minus
        if token.type == 'OPERATOR' and token.value in ('+', '-'):
            self.consume()
            node = self.parse_factor()
            return ('unary_op', token.value, node)
        
        # Number literal
        if token.type == 'NUMBER':
            self.consume()
            return ('number', token.value)
        
        # Variable
        if token.type == 'VARIABLE':
            self.consume()
            return ('variable', token.value)
        
        # Function call
        if token.type == 'FUNCTION':
            func_name = token.value
            self.consume()
            self.consume('LPAREN', '(')
            
            # Parse arguments
            args = []
            if self.peek().type != 'RPAREN':
                args.append(self.parse_expression())
                while self.peek() and self.peek().type == 'COMMA':
                    self.consume('COMMA', ',')
                    args.append(self.parse_expression())
            
            self.consume('RPAREN', ')')
            
            return ('function', func_name, args)
        
        # Parenthesized expression
        if token.type == 'LPAREN':
            self.consume('LPAREN', '(')
            node = self.parse_expression()
            self.consume('RPAREN', ')')
            return node
        
        raise MathExpressionError(f"Unexpected token: {token}")

class Evaluator:
    """Evaluates the AST with given variable bindings"""
    
    def __init__(self):
        self.variables: Dict[str, float] = {}
    
    def set_variable(self, name: str, value: float):
        """Set or update a variable value"""
        # Validate variable name: must start with capital letter, then can contain capitals, digits, /, -,
        if not re.match(r'^[A-Z][A-Z0-9/\-,]*$', name):
            raise MathExpressionError(f"Invalid variable name: {name}. Variables must start with a capital letter and can only contain capital letters, numbers, /, -, and ,")
        self.variables[name] = value
    
    def get_variable(self, name: str) -> float:
        """Get variable value, raise error if not defined"""
        if name not in self.variables:
            raise MathExpressionError(f"Undefined variable: {name}")
        return self.variables[name]
    
    def evaluate(self, ast) -> float:
        """Evaluate the AST and return result"""
        if not ast:
            return 0.0
        
        node_type = ast[0]
        
        if node_type == 'number':
            return ast[1]
        
        elif node_type == 'variable':
            return self.get_variable(ast[1])
        
        elif node_type == 'binary_op':
            op = ast[1]
            left = self.evaluate(ast[2])
            right = self.evaluate(ast[3])
            
            if op == '+':
                return left + right
            elif op == '-':
                return left - right
            elif op == '*':
                return left * right
            elif op == '/':
                if right == 0:
                    raise MathExpressionError("Division by zero")
                return left / right
            elif op == '**':
                return left ** right
            else:
                raise MathExpressionError(f"Unknown operator: {op}")
        
        elif node_type == 'unary_op':
            op = ast[1]
            operand = self.evaluate(ast[2])
            
            if op == '+':
                return +operand
            elif op == '-':
                return -operand
            else:
                raise MathExpressionError(f"Unknown unary operator: {op}")
        
        elif node_type == 'function':
            func_name = ast[1]
            args = [self.evaluate(arg) for arg in ast[2]]
            
            if func_name == 'atan2':
                if len(args) != 2:
                    raise MathExpressionError(f"atan2 requires exactly 2 arguments, got {len(args)}")
                return math.atan2(args[0], args[1])
            elif func_name == 'sqrt':
                if len(args) != 1:
                    raise MathExpressionError(f"sqrt requires exactly 1 argument, got {len(args)}")
                return math.sqrt(args[0])
            else:
                raise MathExpressionError(f"Unknown function: {func_name}")
        
        else:
            raise MathExpressionError(f"Unknown AST node type: {node_type}")
