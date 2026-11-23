// Simulated browser audio graph checks: repeated recording, stream release and silence detection.
// Does not claim real microphone tests.
const fs=require('fs');const vm=require('vm');const assert=require('assert');
const text=fs.readFileSync(__dirname+'/../app/static/app.js','utf8');
const snippet=text.substring(text.indexOf('class WavRecorder{'),text.indexOf('async function toggleRecording()'));
let streams=[];let contexts=[];
class FakeContext{
  constructor(){this.sampleRate=8000;this.state='suspended';this.destination={};contexts.push(this);}
  createMediaStreamSource(stream){return {connect(){},disconnect(){}};}
  createScriptProcessor(){this.processor={connect(){},disconnect(){},onaudioprocess:null};return this.processor;}
  createGain(){return {gain:{value:1},connect(){},disconnect(){}};}
  async resume(){this.state='running';}
  async close(){this.state='closed';}
}
const sandbox={
  window:{AudioContext:FakeContext},
  navigator:{mediaDevices:{getUserMedia:async()=>{const t={stopped:false,stop(){this.stopped=true}};const s={getTracks(){return [t]},track:t};streams.push(s);return s}}},
  Blob, Float32Array, ArrayBuffer,DataView,Math,performance:{now:()=>0},
};
const Recorder=vm.runInNewContext(snippet+'\nWavRecorder;',sandbox);
const feed=(recorder,quiet=false)=>{
  const wave=new Float32Array(4096);
  for(let i=0;i<wave.length;i++)wave[i]=quiet?0:0.08*Math.sin(i*0.05);
  for(let n=0;n<2;n++)recorder.processor.onaudioprocess({inputBuffer:{getChannelData(){return wave}}});
};
(async()=>{
  let r=new Recorder();await r.start();feed(r);let wav=await r.stop();
  assert(wav.size>44);assert(streams.at(-1).track.stopped);assert.strictEqual(contexts.at(-1).state,'closed');
  r=new Recorder();await r.start();feed(r);wav=await r.stop();
  assert(wav.size>44);assert(streams.at(-1).track.stopped);assert.strictEqual(contexts.at(-1).state,'closed');
  r=new Recorder();await r.start();feed(r,true);
  await assert.rejects(()=>r.stop(),/Microphone chưa thu/);
  assert(streams.at(-1).track.stopped);assert.strictEqual(contexts.at(-1).state,'closed');
  console.log('Recorder simulated sequential sessions: PASS; silence: REJECTED; microphone tracks: RELEASED');
})().catch(e=>{console.error(e);process.exitCode=1});
