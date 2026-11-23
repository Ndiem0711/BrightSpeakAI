const assert=require('assert'),fs=require('fs'),vm=require('vm');
const js=fs.readFileSync(__dirname+'/../app/static/app.js','utf8');
const snippet=js.slice(js.indexOf('class WavRecorder{'),js.indexOf('async function toggleRecording()'));
const context={Float32Array,ArrayBuffer,DataView,Blob,Math};
const convert=vm.runInNewContext(snippet+'\n({downsampleSpeech,encodeWav})',context);
(async()=>{
  const nativeRate=48000, seconds=1.2;
  const samples=new Float32Array(nativeRate*seconds);
  for(let i=0;i<samples.length;i++)samples[i]=.25*Math.sin(i*.022);
  const down=convert.downsampleSpeech(samples,nativeRate,16000);
  const wav=convert.encodeWav(down,16000);
  const bytes=await wav.arrayBuffer(),view=new DataView(bytes);
  assert.strictEqual(view.getUint32(24,true),16000);
  assert(Math.abs((wav.size-44)/2/16000-seconds)<0.002);
  assert(wav.size < samples.length*2/2.5);
  console.log('WAV downsample 48kHz -> 16kHz, duration and header: PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
