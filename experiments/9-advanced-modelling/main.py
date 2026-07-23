#!/usr/bin/env sage

import sys
import tty
import termios

from conflicts import Conflicts
from relationships import Relationships
from schema import parse_schema

SCHEMA = """
    CREATE TABLE users (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        first_name VARCHAR(255) NOT NULL,
        last_name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL
    );

    CREATE TABLE posts (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        body TEXT NOT NULL
    );

    CREATE TABLE comments (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        body TEXT NOT NULL
    );
"""

def getch():
    fd = sys.stdin.fileno()
    prev_attr = termios.tcgetattr(fd)

    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, prev_attr)
    return ch

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

        if key == "\x1b[A": # Up
            current = max(0, current - 1)
        elif key == "\x1b[B": # Down
            current = min(len(options) - 1, current + 1)
        elif key == "\r" or key == "\n":
            return options[current]
        elif key == "\x03": # Ctrl+C
            raise KeyboardInterrupt()

def pause():
    input("Press Enter to continue...")

def main():
    schema = parse_schema(SCHEMA)
    conflicts = Conflicts(schema)

    first_field = True

    while True:
        print(f"\n{conflicts}\n")
        
        namespaces = list(conflicts.scopes.scopes.keys())
        
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
            
        options = sorted(conflicts.get_fields(namespace))

        if not options:
            print(f"\nNo available fields on namespace!")
            pause()

            continue
        
        field = select_option(f"\nSELECT", options)
        
        try:
            conflicts.use_field(namespace, field)
        except Exception as e:
            print(f"\nError: {e}")
            pause()
                
        first_field = False

    relationships = Relationships(conflicts, schema)

    while True:
        print(f"\n{relationships}\n")
        
        if conflicts.is_satisfied():
            break
        
        options = sorted(relationships.get_required_tables())
        choice = select_option("FROM", options)
        
        try:
            relationships.use_table(choice)
        except Exception as e:
            print(f"\nError: {e}")
            pause()

            continue

        while True:
            print(f"\n{relationships}\n")
            
            joinable = relationships.get_joinable_neighbors()

            if not joinable:
                print("No joinable tables available.")

                break
            
            options = ["[Done]"] + sorted(joinable, key=lambda n: n.table)
            choice = select_option("JOIN", options)
            
            if choice == "[Done]":
                break
                
            try:
                relationships.join_table(choice)
            except Exception as e:
                print(f"\nError: {e}")
                pause()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")