from run_native import *
ARMS['polish_gate']={'OCA_FOLLOW_POINT':'1','OCA_FOLLOW_GATE':'1'}
cb=P/'build_conditional/prism-followup';target=json.loads((P/'calibrate-targets.json').read_text())['targets']['venice-52']
for rep in range(3,10):
    arms=['champion','polish_gate'];arms=arms[rep%2:]+arms[:rep%2]
    for arm in arms:run('venice-52',arm,rep,'conditional',target,binary=cb)
