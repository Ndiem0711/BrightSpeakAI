"""Train an actual supervised speech-keyword model on Google Speech Commands.

Data: mini_speech_commands, a subset of Google's Speech Commands dataset (CC BY 4.0).
Task: keyword recognition of 8 short English commands, NOT grading pronunciation.
The first run downloads the dataset (~180 MB) explicitly, not silently on app launch.
Run after installing requirements-train.txt:
    python ml/train_keyword_spotter.py --download
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from urllib.request import urlretrieve
import zipfile

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://storage.googleapis.com/download.tensorflow.org/data/mini_speech_commands.zip'
DEST = ROOT / 'ml' / 'data' / 'mini_speech_commands'


def load_features(path):
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import resample_poly, stft
    rate, array = wavfile.read(str(path))
    samples = array.astype('float32')
    if samples.ndim > 1: samples = samples.mean(axis=1)
    if samples.size == 0: raise ValueError('Empty WAV')
    if rate != 16000: samples = resample_poly(samples, 16000, rate)
    samples = samples[:16000]
    if len(samples) < 16000: samples = np.pad(samples, (0, 16000-len(samples)))
    if np.max(np.abs(samples)) > 1: samples /= max(1.0, np.max(np.abs(samples)))
    _, _, z = stft(samples, 16000, nperseg=400, noverlap=240)
    spectrum = np.log1p(np.abs(z))
    # 64 fixed log-spectral bins, 4 distribution statistics per bin.
    bins = spectrum[:64]
    return np.concatenate([bins.mean(1),bins.std(1),np.max(bins,axis=1),np.quantile(bins,.75,axis=1)]).astype('float32')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--download',action='store_true',help='Explicitly fetch the CC BY 4.0 training archive (~180 MB).')
    ap.add_argument('--max-per-class',type=int,default=800)
    args=ap.parse_args()
    if args.download and not DEST.exists():
        work=ROOT/'ml'/'data';work.mkdir(parents=True,exist_ok=True)
        archive=work/'mini_speech_commands.zip'
        print('Downloading openly licensed Speech Commands mini dataset from Google...')
        urlretrieve(URL,archive)
        with zipfile.ZipFile(archive) as z:
            # No arbitrary paths from archives.
            for info in z.infolist():
                target=(work/info.filename).resolve()
                if not target.is_relative_to(work.resolve()):raise ValueError('Unsafe ZIP member')
            z.extractall(work)
    if not DEST.exists():
        raise SystemExit('Dataset missing. Run with --download or place the mini_speech_commands folder in ml/data/.')
    import numpy as np
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    X=[]; y=[]; speakers=[]
    for category in sorted(x for x in DEST.iterdir() if x.is_dir()):
        for wav in sorted(category.glob('*.wav'))[:args.max_per_class]:
            try:
                X.append(load_features(wav)); y.append(category.name)
                speakers.append(wav.stem.split('_nohash_')[0] if '_nohash_' in wav.stem else wav.stem)
            except Exception: continue
    X=np.asarray(X,dtype='float32'); y=np.asarray(y)
    if len(X)<100:raise SystemExit('Too few valid recordings to train; at least 100 are required.')
    split=GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42)
    train,test=next(split.split(X,y,groups=speakers))
    clf=RandomForestClassifier(n_estimators=120,min_samples_leaf=2,n_jobs=-1,random_state=42,class_weight='balanced_subsample')
    assert not (set(np.asarray(speakers)[train]) & set(np.asarray(speakers)[test]))
    clf.fit(X[train],y[train]);pred=clf.predict(X[test])
    labels=sorted(set(y));report=classification_report(y[test],pred,zero_division=0,output_dict=True)
    metrics={'dataset':'Google mini Speech Commands','license':'CC BY 4.0','training_n':len(train),
             'test_n':len(test),'speaker_disjoint':True,'seed':42,'max_per_class':args.max_per_class,'model_type':'RandomForest','accuracy':float(accuracy_score(y[test],pred)),
             'macro_f1':float(report['macro avg']['f1-score']), 'classes':labels,
             'confusion_matrix':confusion_matrix(y[test],pred,labels=labels).tolist(),
             'note':'Keyword spotter, not a pronunciation grade or child-speech benchmark.'}
    out=ROOT/'ml'/'models';out.mkdir(parents=True,exist_ok=True)
    joblib.dump({'model':clf,'labels':labels},out/'keyword_spotter.joblib')
    (out/'keyword_spotter_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    import csv
    with (out/'keyword_split_manifest.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.writer(handle);writer.writerow(['sample_index','label','speaker_id','split'])
        train_ids=set(train.tolist())
        for i in range(len(y)):writer.writerow([i,y[i],speakers[i],'train' if i in train_ids else 'test'])
    (out/'keyword_classification_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(metrics,indent=2))

if __name__=='__main__':main()
