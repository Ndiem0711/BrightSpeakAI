// V9: capture downsampled PCM 16kHz off the UI main thread.
class BrightSpeakVoiceWorklet extends AudioWorkletProcessor {
  constructor(){super();this.batch=new Int16Array(640);this.pos=0;this.phase=0;this.acc=0;this.n=0;}
  process(inputs){
    const v=inputs[0]&&inputs[0][0];if(!v)return true;
    const ratio=sampleRate/16000;
    for(let i=0;i<v.length;i++){
      this.phase+=1;this.acc+=v[i];this.n+=1;
      if(this.phase>=ratio){
        const x=Math.max(-1,Math.min(1,this.acc/Math.max(1,this.n)));
        this.batch[this.pos++]=x<0?Math.round(x*32768):Math.round(x*32767);
        this.phase-=ratio;this.acc=0;this.n=0;
        if(this.pos===this.batch.length){
          const output=this.batch.buffer;
          this.port.postMessage({pcm:output},[output]);
          this.batch=new Int16Array(640);this.pos=0;
        }
      }
    }
    return true;
  }
}
registerProcessor('brightspeak-voice-worklet',BrightSpeakVoiceWorklet);
