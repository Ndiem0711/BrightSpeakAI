"""Optional reproducible CNN training on licensed public Google mini Speech Commands.

Not a phoneme-scoring or child-speech model. Data is NOT bundled. Download
explicitly via: python ml/train_keyword_spotter.py --download
Then: python ml/train_cnn_keyword_spotter.py --epochs 5 --max-per-class 250
This code is intentionally separate from rule-based pronunciation scores.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'ml/data/mini_speech_commands'


def spectrogram(path):
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import stft, resample_poly
    sr,s=wavfile.read(path)
    if s.ndim>1:s=s.mean(axis=1)
    s=s.astype('float32')
    if sr!=16000:s=resample_poly(s,16000,sr)
    if s.size==0:raise ValueError('empty audio')
    if len(s)>16000:s=s[:16000]
    if len(s)<16000:s=np.pad(s,(0,16000-len(s)))
    if np.max(np.abs(s))>1:s/=max(1,np.max(np.abs(s)))
    _,_,z=stft(s,16000,nperseg=400,noverlap=240)
    arr=np.log1p(np.abs(z[:64])).astype('float32')
    # 101 spectrogram frames when 1 second is analyzed at 10ms hop.
    arr=arr[:,:101]
    if arr.shape[1]<101:arr=np.pad(arr,((0,0),(0,101-arr.shape[1])))
    return (arr/(arr.std()+1e-5)).astype('float32')


def train(epochs=5,max_per_class=250,seed=42):
    if not DATA.exists():
        raise SystemExit('Dataset absent. First run: python ml/train_keyword_spotter.py --download')
    import numpy as np
    import torch
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
    from torch import nn
    torch.manual_seed(seed);np.random.seed(seed)
    labels=sorted(p.name for p in DATA.iterdir() if p.is_dir())
    X=[];Y=[];G=[]
    for cls,label in enumerate(labels):
        for file in sorted((DATA/label).glob('*.wav'))[:max_per_class]:
            try:
                X.append(spectrogram(str(file)));Y.append(cls)
                G.append(file.stem.split('_nohash_')[0] if '_nohash_' in file.stem else file.stem)
            except (ValueError, OSError):continue
    if len(X)<100:raise SystemExit('Need >=100 valid recordings.')
    X=np.stack(X).astype('float32')[:,None,:,:];Y=np.array(Y)
    tr,te=next(GroupShuffleSplit(n_splits=1,test_size=.20,random_state=seed).split(X,Y,G))
    model=nn.Sequential(
        nn.Conv2d(1,16,3,padding=1),nn.BatchNorm2d(16),nn.ReLU(),nn.MaxPool2d(2),
        nn.Conv2d(16,32,3,padding=1),nn.BatchNorm2d(32),nn.ReLU(),nn.MaxPool2d(2),
        nn.Conv2d(32,64,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d(1),nn.Flatten(),
        nn.Linear(64,len(labels)))
    optim=torch.optim.AdamW(model.parameters(),lr=.001)
    loss=nn.CrossEntropyLoss()
    train_X=torch.from_numpy(X[tr]);train_Y=torch.from_numpy(Y[tr]).long()
    model.train();history=[]
    for epoch in range(epochs):
        indices=torch.randperm(len(tr));costs=[]
        for start in range(0,len(tr),64):
            idx=indices[start:start+64];pred=model(train_X[idx]);cost=loss(pred,train_Y[idx]);
            optim.zero_grad();cost.backward();optim.step();costs.append(float(cost.item()))
        history.append(round(float(np.mean(costs)),5))
        print(f'CNN epoch {epoch+1}/{epochs}: loss={history[-1]}',flush=True)
    model.eval()
    with torch.no_grad():pred=model(torch.from_numpy(X[te])).argmax(dim=1).cpu().numpy()
    metrics={'task':'8-class keyword recognition NOT phoneme pronunciation grading',
             'dataset':'Google mini Speech Commands','license':'CC BY 4.0',
             'train_samples':int(len(tr)),'test_samples':int(len(te)),'epochs':epochs,
             'group_disjoint_speakers':True,'test_accuracy':float(accuracy_score(Y[te],pred)),
             'test_macro_f1':float(f1_score(Y[te],pred,average='macro',zero_division=0)),
             'labels':labels,'confusion_matrix':confusion_matrix(Y[te],pred,labels=list(range(len(labels)))).tolist(),
             'train_loss':history,'seed':seed,'child_speech_validation':'not performed'}
    out=ROOT/'ml/models';out.mkdir(parents=True,exist_ok=True)
    torch.save({'state_dict':model.state_dict(),'labels':labels,'seed':seed},out/'cnn_keyword_spotter.pt')
    (out/'cnn_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epochs',type=int,default=5)
    p.add_argument('--max-per-class',type=int,default=250)
    p.add_argument('--seed',type=int,default=42)
    a=p.parse_args();train(a.epochs,a.max_per_class,a.seed)
