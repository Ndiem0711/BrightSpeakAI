// Fake-clock regression tests for the exact 5-second silence timer (no microphone or API).
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const source=readFileSync(__dirname+'/../app/static/live-hints.js','utf8');
let now=0,nextId=1;const tasks=new Map();const hints=[];
function schedule(fn,delay){const id=nextId++;tasks.set(id,{at:now+delay,fn});return id;}
function cancel(id){tasks.delete(id);}
function advance(ms){
  const limit=now+ms;
  while(true){
    const due=[...tasks.entries()].filter(([,t])=>t.at<=limit).sort((a,b)=>a[1].at-b[1].at)[0];
    if(!due)break;
    tasks.delete(due[0]);now=due[1].at;due[1].fn();
  }
  now=limit;
}
const sandbox={window:{}};vm.runInNewContext(source,sandbox);
const Hints=sandbox.window.BrightSpeakLiveHints;
const h=new Hints(reason=>hints.push({reason,at:now}),5000,schedule,cancel);
h.reset();advance(10000);assert.equal(hints.length,0,'timer must not start while Bibi is talking');
h.assistantFinished();advance(4999);assert.equal(hints.length,0);
advance(1);assert.deepEqual(hints,[{reason:'timeout',at:15000}]);
advance(8000);assert.equal(hints.length,1,'no duplicate hint for same question');
h.reset();h.assistantFinished();advance(3000);h.speechDetected();advance(6000);assert.equal(hints.length,1,'speech onset must cancel timer');
h.reset();h.assistantFinished();advance(1000);assert.equal(h.manual(),true);assert.equal(hints.at(-1).reason,'manual');advance(10000);assert.equal(hints.length,2,'manual must cancel the scheduled automatic hint');
h.reset();h.assistantFinished();advance(1000);h.stop();advance(8000);assert.equal(hints.length,2,'session termination must cancel timer');
h.reset();h.assistantFinished();advance(1000);h.reset();h.assistantFinished();advance(5000);assert.equal(hints.length,3,'switching questions invalidates old timer');
console.log('Face-to-face hint clock: 5s exact, no early hint, cancel on voice, manual, stop, question change – PASS');
