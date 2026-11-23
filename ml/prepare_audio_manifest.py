"""Create inspectable metadata for downloaded Google mini Speech Commands audio.

Usage (after python ml/train_keyword_spotter.py --download):
   python ml/prepare_audio_manifest.py

No recordings or personally identifiable data are uploaded. The dataset must be
downloaded explicitly and license verified by the project owner.
"""
from __future__ import annotations
import csv
import hashlib
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WAV_DIR = ROOT / 'ml' / 'data' / 'mini_speech_commands'
OUT = ROOT / 'ml' / 'data' / 'audio_manifest.csv'

def run():
    if not WAV_DIR.exists():
        raise SystemExit('Chua co audio. Chay: python ml/train_keyword_spotter.py --download')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    count=0
    with OUT.open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.writer(f)
        wr.writerow(['path','label','speaker_pseudonym','split','sample_rate','duration_sec','sha256','license','source'])
        for folder in sorted(p for p in WAV_DIR.iterdir() if p.is_dir()):
            for wav in sorted(folder.glob('*.wav')):
                try:
                    with wave.open(str(wav),'rb') as x:
                        dur=x.getnframes()/float(x.getframerate())
                        sr=x.getframerate()
                except Exception:
                    continue
                speaker=wav.stem.split('_nohash_')[0] if '_nohash_' in wav.stem else wav.stem
                speaker_hash=hashlib.sha256(speaker.encode()).hexdigest()[:16]
                split='test' if int(speaker_hash[:6],16)%10<2 else 'train'
                wr.writerow([str(wav.relative_to(ROOT)).replace('\\','/'),folder.name,speaker_hash,split,sr,round(dur,3),hashlib.sha256(wav.read_bytes()).hexdigest(),'CC BY 4.0','Google mini Speech Commands'])
                count+=1
    print(f'Wrote {count} rows into {OUT}')

if __name__=='__main__':run()
