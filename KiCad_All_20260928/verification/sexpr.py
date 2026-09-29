import json
import re

def parse(text):
    stack = [[]]
    for token in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text):
        if token == '(':
            child = []
            stack[-1].append(child)
            stack.append(child)
        elif token == ')':
            stack.pop()
        else:
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    assert len(stack) == 1
    return stack[0][0]

def children(node, name):
    return [x for x in node if isinstance(x, list) and x and x[0] == name]

def child(node, name):
    return next((x for x in children(node, name)), None)

def blocks(text, key):
    pattern = re.compile(r'\n\t\(' + re.escape(key) + r'(?=\s|\))')
    found = []
    for m in pattern.finditer(text):
        start = m.start() + 2
        depth = 0
        quoted = escaped = False
        for i in range(start, len(text)):
            c = text[i]
            if quoted:
                if escaped: escaped = False
                elif c == '\\': escaped = True
                elif c == '"': quoted = False
            elif c == '"': quoted = True
            elif c == '(': depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    found.append((start, i + 1, text[start:i + 1]))
                    break
    return found
