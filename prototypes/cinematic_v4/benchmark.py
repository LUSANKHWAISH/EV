"""Sequential visible render measurements, without capture or live voice startup."""
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
import psutil

ROOT=Path(__file__).resolve().parent
EVIDENCE=ROOT/'evidence'

def gpu_sample():
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=timestamp,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,creationflags=subprocess.CREATE_NO_WINDOW)
        values=[v.strip() for v in result.stdout.strip().split(',')]
        return {'timestamp':values[0],'adapter':values[1],'total_gpu_utilization_percent':float(values[2]),
                'total_vram_used_mb':float(values[3]),'vram_total_mb':float(values[4]),'temperature_c':float(values[5]),'total_power_watts':float(values[6])}
    except Exception as exc:return {'error':str(exc)}

def main():
    output={'utc':datetime.now(timezone.utc).isoformat(),'method':'Sequential 25-second standalone runs; no screenshots, encoder, microphone, ASR or TTS. NVIDIA readings cover the whole adapter, including other desktop apps. Process CPU is divided by logical CPU count.','baseline_gpu':gpu_sample(),'runs':[]}
    for name,args in [('standard_60',[]),('expanded_60',['--expanded']),('standard_30',['--quality']),('expanded_30',['--expanded','--quality'])]:
        command=[sys.executable,'-B',str(ROOT/'run_preview.py'),'--reference-dpi','--duration','25','--report',name+'.json',*args]
        with (EVIDENCE/(name+'_console.txt')).open('w') as log:
            child=subprocess.Popen(command,cwd=ROOT.parents[1],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            process=psutil.Process(child.pid);process.cpu_percent(None);processes={child.pid:process}
            samples=[];start=time.perf_counter()
            while child.poll() is None:
                stamp=time.perf_counter()-start
                try:
                    # Windows venv python.exe is a redirector; measure its
                    # actual interpreter descendants as well as that launcher.
                    current=[process,*process.children(recursive=True)]
                    cpu=0.;rss=0;active=[]
                    for candidate in current:
                        if candidate.pid not in processes:
                            processes[candidate.pid]=candidate;candidate.cpu_percent(None)
                        proc=processes[candidate.pid]
                        try:
                            cpu+=proc.cpu_percent(None);rss+=proc.memory_info().rss;active.append(proc.pid)
                        except psutil.NoSuchProcess:pass
                    sample={'seconds':stamp,'process_cpu_percent_normalized':cpu/psutil.cpu_count(),
                            'process_rss_mb':rss/1024**2,'process_ids':active,**gpu_sample()}
                    samples.append(sample)
                except psutil.NoSuchProcess:break
                time.sleep(1)
            code=child.wait()
        report=json.loads((EVIDENCE/(name+'.json')).read_text()) if code==0 else {}
        stable=[s for s in samples if s['seconds']>3]
        row={'profile':name,'exit_code':code,'samples':samples,'render':report}
        for field in ['process_cpu_percent_normalized','process_rss_mb','total_gpu_utilization_percent','total_vram_used_mb','total_power_watts']:
            values=[s[field] for s in stable if field in s]
            row[field+'_median']=statistics.median(values) if values else None
        output['runs'].append(row)
        (EVIDENCE/'benchmark_metrics.json').write_text(json.dumps(output,indent=2))
        print(json.dumps({'profile':name,'exit_code':code,'fps':report.get('mean_presented_fps_after_warmup'),'cpu_percent':row.get('process_cpu_percent_normalized_median'),'rss_mb':row.get('process_rss_mb_median')}),flush=True)
    return 0 if all(r['exit_code']==0 for r in output['runs']) else 1

if __name__=='__main__':raise SystemExit(main())
