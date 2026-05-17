import math
import re
from typing import Dict, Union, Optional

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
            
            # Match numbers (integers or floats)
            match = re.match(r'\d+(?:\.\d+)?', self.expression[pos:])
            if match:
                value = float(match.group(0))
                self.tokens.append(Token('NUMBER', value))
                pos += match.end()
                continue
            
            # Match variables: Start with capital letter, then can contain capital letters, digits, /, -, ,
            # Variable pattern: [A-Z][A-Z0-9/-,]*
            match = re.match(r'[A-Z][A-Z0-9/\-,]*', self.expression[pos:])
            if match:
                value = match.group(0)
                # Check if it's a function name (currently only atan2)
                if value == 'ATAN2':
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
            else:
                raise MathExpressionError(f"Unknown function: {func_name}")
        
        else:
            raise MathExpressionError(f"Unknown AST node type: {node_type}")

class MathExpression:
    """Main interface for parsing and evaluating math expressions"""
    
    def __init__(self):
        self.evaluator = Evaluator()
    
    def set_variable(self, name: str, value: float):
        """Set variable value"""
        self.evaluator.set_variable(name, value)
    
    def set_variables(self, variables: Dict[str, float]):
        """Set multiple variables at once"""
        for name, value in variables.items():
            self.evaluator.set_variable(name, value)
    
    def evaluate(self, expression: str) -> float:
        """Parse and evaluate a math expression"""
        try:
            # Tokenize
            lexer = Lexer(expression)
            tokens = lexer.tokenize()
            
            # Parse
            parser = Parser(tokens)
            ast = parser.parse()
            
            # Evaluate
            result = self.evaluator.evaluate(ast)
            return result
        
        except MathExpressionError as e:
            raise MathExpressionError(f"Error evaluating '{expression}': {e}")
    
    def get_variables(self) -> Dict[str, float]:
        """Get current variable bindings"""
        return self.evaluator.variables.copy()

# Example usage and testing
if __name__ == "__main__":


    lexer = Lexer("2 * SC/1/DISPLACEMENTS/1-3/TX + 1")
    tokens = lexer.tokenize()
    for token in tokens:
        if token.type == "VARIABLE":
            print(token.value)
        

    exit()
    


    math_exp = MathExpression()
    
    # Set variables with the new format (capital letters, can contain /, -, ,)
    math_exp.set_variable("X", 10)
    math_exp.set_variable("Y", 5)
    math_exp.set_variable("PI", math.pi)
    math_exp.set_variable("VAR1", 2)
    math_exp.set_variable("COORD-X", 3)
    math_exp.set_variable("RATIO/X", 4)
    math_exp.set_variable("A,B", 6)  # Variable containing comma
    math_exp.set_variable("TEST-VAR/1,2", 7)  # Complex variable name
    
    # Test expressions
    test_expressions = [
        "2 + 3 * 4",
        "(2 + 3) * 4",
        "10 / 2",
        "2 ** 3",
        "2 ** 3 ** 2",  # Right-associative: 2 ** (3 ** 2) = 2 ** 9 = 512
        "2**3",  # Without spaces
        "2 ** 3 * 4",  # Exponentiation has higher precedence
        "X + Y",
        "X * Y - 10",
        "ATAN2(Y, X)",  # Function name must be uppercase ATAN2
        "ATAN2(1, 0)",
        "X ** 2 + Y ** 2",
        "-5 + 3",
        "-(2 + 3)",
        "ATAN2(3, 4) * 2",
        "2 * ATAN2(3, 4)",
        "2 ** -2",  # Negative exponent
        "VAR1 * 5",
        "COORD-X + 10",
        "RATIO/X / 2",
        "A,B * 3",
        "TEST-VAR/1,2 + 5",
        "ATAN2(Y, X) + VAR1",
    ]
    
    print("Math Expression Evaluator")
    print("=" * 40)
    print(f"Variables: {math_exp.get_variables()}")
    print()
    
    for expr in test_expressions:
        try:
            result = math_exp.evaluate(expr)
            print(f"{expr:35} = {result}")
        except MathExpressionError as e:
            print(f"{expr:35} Error: {e}")
    
    print("\n" + "=" * 40)
    
    # Demonstrate invalid variable names
    print("\nInvalid variable name examples:")
    try:
        math_exp.set_variable("lowercase", 10)  # Should fail - doesn't start with capital
    except MathExpressionError as e:
        print(f"  'lowercase' -> {e}")
    
    try:
        math_exp.set_variable("123VAR", 10)  # Should fail - doesn't start with letter
    except MathExpressionError as e:
        print(f"  '123VAR' -> {e}")
    
    try:
        math_exp.set_variable("VAR@NAME", 10)  # Should fail - contains invalid character
    except MathExpressionError as e:
        print(f"  'VAR@NAME' -> {e}")
    
    print("\n" + "=" * 40)
    
    # Interactive mode
    print("\nInteractive mode (type 'quit' to exit)")
    print("Variable rules: Start with capital letter, can contain A-Z, 0-9, /, -, ,")
    print("Set variables with: VAR = expression")
    print("Function: ATAN2(y,x)")
    print("Evaluate expressions: 2 + 3 * VAR")
    
    while True:
        try:
            user_input = input("\n> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                break
            
            # Check for variable assignment
            if '=' in user_input and 'set' not in user_input.lower():
                # Handle simple assignment: var = expression
                parts = user_input.split('=', 1)
                var_name = parts[0].strip()
                expr = parts[1].strip()
                
                # Validate variable name format
                if re.match(r'^[A-Z][A-Z0-9/\-,]*$', var_name):
                    try:
                        value = math_exp.evaluate(expr)
                        math_exp.set_variable(var_name, value)
                        print(f"Set {var_name} = {value}")
                    except MathExpressionError as e:
                        print(f"Error evaluating expression: {e}")
                else:
                    print(f"Invalid variable name: '{var_name}'. Variables must start with a capital letter and can only contain capital letters, numbers, /, -, and ,")
            else:
                # Evaluate expression
                try:
                    result = math_exp.evaluate(user_input)
                    print(f"= {result}")
                except MathExpressionError as e:
                    print(f"Error: {e}")
        
        except KeyboardInterrupt:
            break
        except EOFError:
            break