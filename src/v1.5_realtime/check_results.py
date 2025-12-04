#!/usr/bin/env python3

# Read and check composition results
with open('test_composition_result.txt', 'r', encoding='cp949') as f:
    lines = f.readlines()

capture = False
for i, line in enumerate(lines):
    if 'GATE 2' in line or '구도' in line:
        capture = True

    if capture:
        print(line.rstrip())

    if capture and ('GATE 3' in line or '압축' in line):
        break