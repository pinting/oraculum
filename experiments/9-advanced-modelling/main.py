#!/usr/bin/env sage

import sys
import tty
import termios

from fields import Fields
from tables import Tables

def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def clear():
    sys.stdout.write('\033[H\033[J')
    sys.stdout.flush()

def select_option(prompt, options):
    if not options:
        return None
    
    current = 0

    print(prompt)

    for _ in options:
        print()
    
    while True:
        sys.stdout.write(f"\033[{len(options)}A")
        
        for idx, opt in enumerate(options):
            if idx == current:
                sys.stdout.write(f"\r\033[K> {opt}\n")
            else:
                sys.stdout.write(f"\r\033[K  {opt}\n")
                
        sys.stdout.flush()
        
        key = getch()
        if key == '\x1b[A': # Up
            current = max(0, current - 1)
        elif key == '\x1b[B': # Down
            current = min(len(options) - 1, current + 1)
        elif key == '\r' or key == '\n':
            return options[current]
        elif key == '\x03': # Ctrl+C
            raise KeyboardInterrupt()

def pause():
    input("Press Enter to continue...")

def main():
    tables = {
        "i": ["ki", "q", "kie", "fi"],
        "j": ["kj", "q", "fj"],
        "k": ["kk", "q", "fk"],
        "a": ["kab", "q", "fa"],
        "b": ["kab", "kbc", "fb"],
        "c": ["kbc", "kcd", "fc"],
        "d": ["kcd", "kde", "fd"],
        "e": ["kde", "kie", "fe"],
    }

    fields = Fields(tables)

    first_field = True

    while True:
        clear()
        print(f"\n{fields}\n")
        
        namespaces = list(fields.scopes.scopes.keys())
        
        options = []

        if not first_field:
            options.append("[Done]")
            
        options.extend(["."] + namespaces + ["[New]"])
        
        choice = select_option("NAMESPACE", options)

        if choice == "[Done]":
            break
        elif choice == ".":
            namespace = ""
        elif choice == "[New]":
            namespace = input("Define: ").strip()
        else:
            namespace = choice
            
        options = sorted(fields.get_fields(namespace))

        if not options:
            print(f"\nNo available fields on namespace!")
            pause()

            continue
        
        field = select_option(f"\nSELECT", options)
        
        try:
            fields.use_field(namespace, field)
        except Exception as e:
            print(f"\nError: {e}")
            pause()
                
        first_field = False

    tables = Tables(fields)

    while True:
        clear()
        print(f"\n{tables}\n")
        
        if fields.is_satisfied():
            break
        
        options = sorted(tables.get_required_tables())
        choice = select_option("FROM", options)
        
        try:
            tables.use_table(choice)
        except Exception as e:
            print(f"\nError: {e}")
            pause()

            continue

        while True:
            clear()
            print(f"\n{tables}\n")
            
            joinable = tables.get_joinable_neighbors()

            if not joinable:
                print("No joinable tables available.")

                break
            
            options = ["[Done]"] + sorted(joinable)
            choice = select_option("JOIN", options)
            
            if choice == "[Done]":
                break
                
            try:
                tables.join_table(choice)
            except Exception as e:
                print(f"\nError: {e}")
                pause()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")