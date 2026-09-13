#!/usr/bin/env python3
"""Run the preregistered D21 sequential restart portfolio."""
from __future__ import annotations
import argparse,hashlib,json,math,pathlib,statistics,sys

HERE=pathlib.Path(__file__).resolve().parent;W6=HERE.parent;W5=W6.parent/'eta2_wave5'
sys.path.insert(0,str(W5));import native_light as N  # noqa:E402
N.HERE=W6
PROTOCOL=W6/'D21_RESTART_PORTFOLIO_PROTOCOL.md';BINARY=W5/'build/prism-b6v7'
OPT=json.loads((W5/'optimized_candidate.json').read_text());BASE=json.loads((W5/'b6v7-registration.json').read_text())
CELL=BASE['tails']['final-3068'];FLAGS=OPT['flags_overlay'];MAX_EPISODES=60
P0=.85;P1=.95;ALPHA=BETA=.05
LOWER=math.log(BETA/(1-ALPHA));UPPER=math.log((1-BETA)/ALPHA)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def registration():
 assert sha(BINARY)==OPT['derived_binary_sha256']==BASE['binary_sha256']
 reg={'protocol_sha256':sha(PROTOCOL),'runner_sha256':sha(HERE/'run.py'),
      'development_sha256':sha(W6/'d21-development.json'),'binary':str(BINARY),'binary_sha256':sha(BINARY),
      'optimized_candidate_sha256':sha(W5/'optimized_candidate.json'),'flags':FLAGS,
      'cell':CELL,'attempt_cap':3,'max_episodes':MAX_EPISODES,
      'sprt':{'p0':P0,'p1':P1,'alpha':ALPHA,'beta':BETA,'lower':LOWER,'upper':UPPER},
      'promotion':{'median_native_ratio_ceiling':1.20,'single_conditional_median':3.26935,
                   'mean_native_ceiling':6.59,'p90_native_ceiling':18.1}}
 N.write(W6/'d21-registration.json',reg);return reg

def summarize(episodes,reg):
 llr=0.;decision='continue'
 for episode in episodes:
  success=episode['hit'];llr+=math.log(P1/P0) if success else math.log((1-P1)/(1-P0))
  if llr>=UPPER:decision='high_reliability';break
  if llr<=LOWER:decision='moderate_reliability';break
 times=[e['native_time_to_decision'] for e in episodes]
 first_hits=sum(e['attempts'][0]['hit'] for e in episodes)
 second_eligible=[e for e in episodes if len(e['attempts'])>=2]
 third_eligible=[e for e in episodes if len(e['attempts'])>=3]
 report={'episodes':len(episodes),'hits':sum(e['hit'] for e in episodes),
         'hit_rate':sum(e['hit'] for e in episodes)/len(episodes) if episodes else None,
         'first_attempt_hits':first_hits,
         'second_attempt_conditional_hits':sum(e['attempts'][1]['hit'] for e in second_eligible),
         'second_attempts':len(second_eligible),
         'third_attempt_conditional_hits':sum(e['attempts'][2]['hit'] for e in third_eligible),
         'third_attempts':len(third_eligible),'log_likelihood_ratio':llr,
         'lower_boundary':LOWER,'upper_boundary':UPPER,'decision':decision}
 if times:
  report.update({'native_time_median':statistics.median(times),'native_time_mean':statistics.fmean(times),
                 'native_time_p90':sorted(times)[math.ceil(.9*len(times))-1],
                 'process_time_median':statistics.median(e['process_time_to_decision'] for e in episodes),
                 'attempt_count_median':statistics.median(len(e['attempts']) for e in episodes),
                 'attempt_count_mean':statistics.fmean(len(e['attempts']) for e in episodes)})
  p=reg['promotion'];report['speed_gates']={
   'median':report['native_time_median']<=p['median_native_ratio_ceiling']*p['single_conditional_median'],
   'mean':report['native_time_mean']<p['mean_native_ceiling'],
   'p90':report['native_time_p90']<p['p90_native_ceiling']}
  report['promote']=decision=='high_reliability' and all(report['speed_gates'].values())
 else:report['promote']=False
 return report

def execute(reg):
 result_path=W6/'d21-results.json';episodes=json.loads(result_path.read_text()) if result_path.exists() else []
 while len(episodes)<MAX_EPISODES and summarize(episodes,reg)['decision']=='continue':
  index=len(episodes);attempts=[];native=process=0.;best=None;hit=False
  for attempt in range(3):
   folder=W6/'evidence/d21-restart-portfolio'/f'episode-{index:03d}-attempt-{attempt+1}'
   row=N.run(folder,CELL,'b6v7-restart',index*3+attempt,BINARY,FLAGS,PROTOCOL,reg)
   attempts.append(row);native+=row['target_seconds'] if row['hit'] else row['native_seconds'];process+=row['process_seconds']
   if best is None or row['cost']<best['cost']:best=row
   if row['hit']:hit=True;break
  episode={'episode':index,'hit':hit,'attempts':attempts,
           'native_time_to_decision':native,'process_time_to_decision':process,
           'selected_cost':best['cost'],'selected_state_sha256':best['state_sha256']}
  episodes.append(episode);N.write(result_path,episodes)
  report=summarize(episodes,reg);N.write(W6/'d21-summary.json',report)
  print('EPISODE',index+1,'hit',int(hit),'attempts',len(attempts),'native',round(native,4),
        'llr',round(report['log_likelihood_ratio'],4),'decision',report['decision'],flush=True)
 return summarize(episodes,reg)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['register','run','summarize']);args=parser.parse_args();reg=registration()
 if args.stage=='register':result=reg
 elif args.stage=='run':result=execute(reg)
 else:
  result=summarize(json.loads((W6/'d21-results.json').read_text()),reg);N.write(W6/'d21-summary.json',result)
 print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()

