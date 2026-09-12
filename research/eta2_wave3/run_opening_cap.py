"""Pre-registered cap/opening interaction, separate fresh cohorts."""
import argparse,json
import run_native as N
P=N.P
def main():
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['venice','practical']);a=ap.parse_args()
 reg=N.register();combos={key+'-cap30':dict(v,OCA_E2_CAP='30') for key,v in N.ARMS.items() if key.startswith('open-')}
 N.ARMS.update(combos)
 registration=dict(parent=reg,arms=combos,addendum_sha256=N.G.sha(P/'OPENING_CAP_ADDENDUM.md'))
 p=P/'opening-cap-registration.json'
 if p.exists():assert json.loads(p.read_text())==registration
 else:N.G.write(p,registration)
 rows=[]
 if a.stage=='venice':
  arms=['off','opening']+list(combos)
  for rep in range(5):
   for arm in (arms if rep%2==0 else list(reversed(arms))):
    rows.append(N.run(reg,'opening-cap',reg['cells']['venice-52'],arm,rep));N.G.write(P/'opening-cap-results.json',rows)
 else:
  prior=json.loads((P/'opening-cap-results.json').read_text());arms=['off']+[key for key in combos if sum(r['hit'] for r in prior if r['arm']==key)>=4]
  N.G.write(P/'opening-cap-practical-selection.json',dict(arms=arms,rule='at least 4/5 registered Venice hits'))
  for rep in range(3):
   for cell in reg['practical']:
    for arm in (arms if rep%2==0 else list(reversed(arms))):
     rows.append(N.run(reg,'opening-cap-practical',cell,arm,rep));N.G.write(P/'opening-cap-practical-results.json',rows)
 print('COMPLETE opening-cap',a.stage,len(rows),flush=True)
if __name__=='__main__':main()
