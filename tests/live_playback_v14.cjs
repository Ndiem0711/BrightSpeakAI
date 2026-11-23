// Exercise the shipped player with deterministic PCM and a simulated audio clock.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(__dirname + '/../app/static/features.js', 'utf8');
const from = code.indexOf('function b64ToBuffer');
const to = code.indexOf('// V11 turn-aware subtitles', from);
const scheduled = [];
class AudioClock {
  currentTime = 0;
  state = 'running';
  createBuffer(channels, length, rate) {
    return {duration: length / rate, getChannelData: () => new Float32Array(length)};
  }
  createBufferSource() {
    const node = {connect() {}, start(time) {this.time = time;}, stop() {this.stopped = true;}};
    scheduled.push(node);
    return node;
  }
}
const Player = vm.runInNewContext(code.slice(from,to) + '\nLiveAudioPlayer', {
  window: {AudioContext: AudioClock}, atob, Uint8Array, DataView, $: () => null,
});
(async () => {
  const player = new Player();
  const chunk = Buffer.alloc(4800, 12).toString('base64');
  for (let n = 0; n < 40; n++) await player.play(chunk);
  assert.equal(scheduled.length, 40);
  assert.ok(scheduled.every(s => !s.stopped));
  for (let n = 1; n < 40; n++) {
    assert.ok(Math.abs(scheduled[n].time - scheduled[n-1].time - 0.1) < 1e-9);
  }
  player.interrupt();
  assert.ok(scheduled.every(s => s.stopped));
  assert.equal(player.isAudible(), false);
  console.log('PASS: 4 seconds of burst PCM preserved, ordered, and explicitly interruptible');
})().catch(e => {console.error(e); process.exitCode = 1;});
