from run_study import *
base.ARMS['menu_feedback']['OCA_PHASE_OPEN_LIMIT']='600'
base.ARMS['champion']['OCA_PHASE_OPEN_LIMIT']='600'
binary=P/'build_collapse/prism-hybrid';targets=json.loads((P/'small-targets.json').read_text())['targets'];rows=[]
for s in SMALL:
    for rep in range(3):
        arms=['champion','menu_feedback'];order=arms[rep%2:]+arms[:rep%2]
        for a in order:rows.append(run(s,a,rep,'collapse-diagnostic',targets[s],binary=binary))
write(P/'collapse-results.json',rows)
