import sys,time
t0=time.time()
for ln in sys.stdin:
    sys.stdout.write(f"{time.time()-t0:9.3f} {ln}")
    sys.stdout.flush()
