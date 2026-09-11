#!/usr/bin/env python3
from run_study import *

targets = json.loads((P / 'small-targets.json').read_text())['targets']
selected = json.loads((P / 'selection.json').read_text())['selected']
rows = []
for scene in ['dubrovnik-88', 'venice-52']:
    for rep in range(10):
        arms = ['champion', selected]
        for arm in arms[rep % 2:] + arms[:rep % 2]:
            rows.append(run(scene, arm, rep, 'small', targets[scene]))
write(P / 'small-repeat-results.json', rows)
