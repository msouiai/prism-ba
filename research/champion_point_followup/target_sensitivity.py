from run_native import *
ARMS['polish_gate']={'OCA_FOLLOW_POINT':'1','OCA_FOLLOW_GATE':'1'}
ref=json.loads((P/'calibrate-targets.json').read_text())['targets']['venice-52']/1.001
cb=P/'build_conditional/prism-followup'
for ratio in [1.005,1.01]:
    for rep in range(3):
        arms=['champion','polish_gate'];arms=arms[rep%2:]+arms[:rep%2]
        for a in arms:run('venice-52',a,rep,f'tolerance-{ratio}',ref*ratio,binary=cb)
