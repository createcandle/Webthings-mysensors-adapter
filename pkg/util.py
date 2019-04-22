"""Utility functions."""

def pretty(d, indent=0):
    for key, value in d.items():
        print('\t' * indent + str(key))
        if isinstance(value, dict):
            pretty(value, indent+1)
        else:
            print('\t' * (indent+1) + str(value))
            
def is_a_number(s):
    """ Returns True is string is a number. """
    try:
        float(s)
        return True
    except ValueError:
        return False
    
def make_safe_name(s):
    keepcharacters = (' ','.','_')
    return "".join(c for c in s if c.isalpha() or c.isalnum() or c in keepcharacters).rstrip()
