def is_palindrome(s: str) -> bool:
    clean = ''.join(c.lower() for c in s if c.isalnum())
    return clean == clean[::-1]

if __name__ == '__main__':
    test_cases = ['radar', 'level', 'rotor', 'sanctum', 'A man, a plan, a canal: Panama']
    for word in test_cases:
        print(f'{word!r} -> is_palindrome: {is_palindrome(word)}')
