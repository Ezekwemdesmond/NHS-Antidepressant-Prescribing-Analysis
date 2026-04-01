import subprocess
import sys
import time

scripts = ['scraper.py', 'processor.py', 'forecast.py', 'loader.py']
start  = time.time()

for script in scripts:
    print(f"\nRunning {script}...")
    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        print(f"{script} failed. Pipeline halted.")
        sys.exit(1)

elapsed = time.time() - start
print(f"\nPipeline complete in {int(elapsed // 60)}m {int(elapsed % 60)}s.")