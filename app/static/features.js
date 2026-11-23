/* BrightSpeak extra modules. Existing visual design is preserved. */
let featureRecorder = null;
let featureAudio = null;
let liveWS = null;
let liveMic = null;
let liveCamera = null;
let liveFrameTimer = null;
let livePlayback = null;
let liveActive = false;
let liveCameraRequestId = 0;
let liveConnecting = false;
let liveLastError = '';


function speechOutput(text){
  if(!text || liveActive || liveConnecting || liveWS) return;
  if(!('speechSynthesis' in window)){toast('Trình duyệt chưa hỗ trợ đọc câu trả lời.',true);return;}
  speechSynthesis.cancel();
  const utterance=new SpeechSynthesisUtterance(text);utterance.lang='en-US';utterance.rate=.86;
  speechSynthesis.speak(utterance);
}
function micError(err){
  if(!window.isSecureContext) return 'Microphone chỉ hoạt động trên HTTPS hoặc localhost (127.0.0.1).';
  if(err?.name==='NotAllowedError') return 'Microphone đang bị chặn. Nhấn biểu tượng ổ khóa và cho phép Microphone.';
  if(err?.name==='NotFoundError') return 'Thiết bị không tìm thấy microphone. Kiểm tra tai nghe hoặc mic.';
  return 'Không thể mở microphone: '+String(err?.message||err);
}
async function stopFeatureRecording(){
  const active=featureRecorder;featureRecorder=null;featureAudio=null;
  if(active){try{await active.stop();}catch{}}
}
async function recordFeature(target){
  const status=$(target.status),button=$(target.button);if(!button||button.disabled)return;
  button.disabled=true;
  try{
    if(!featureRecorder){
      featureAudio=null;const next=new WavRecorder();featureRecorder=next;
      await next.start();
      if(featureRecorder!==next || next.closed || !document.contains(button))return;
      button.classList.add('recording');button.textContent='⏹ Dừng ghi';
      status.textContent='🔴 Đang ghi âm… Hãy nói tiếng Anh, sau đó nhấn Dừng.';
    }else{
      const active=featureRecorder;featureRecorder=null;
      const recorded=await active.stop();if(!document.contains(button))return;
      if(!recorded||recorded.size<100)throw Error('Bản ghi quá ngắn. Em hãy thử lại.');
      featureAudio=recorded;
      status.textContent=`✅ Ghi âm thành công (${(recorded.size/1024).toFixed(0)} KB). Nhấn gửi để phân tích.`;
      button.classList.remove('recording');button.textContent='🎤 Ghi lại';
    }
  }catch(err){
    if(featureRecorder){const r=featureRecorder;featureRecorder=null;await r.stop().catch(()=>{});}
    featureAudio=null;
    if(document.contains(button)){button.classList.remove('recording');button.textContent='🎤 Ghi âm lại';status.textContent='Chưa ghi được âm thanh.';}
    toast(err?.message?.includes('Bản ghi')||err?.message?.includes('Microphone chưa thu') ? err.message : micError(err),true);
  }finally{if(document.contains(button))button.disabled=false;}
}
function selectedTopic(){
  const chooser=$('#topicSelect');
  return chooser?.value==='__custom__' ? ($('#customTopic').value.trim()||'Free conversation') : (chooser?.value||'Daily life');
}
async function renderConversationEnhanced(){
  $('#content').innerHTML=`<div class="grid"><section class="card span-8"><h3>💬 Talk with Bibi – Nói với AI</h3>
    <p>Chọn chủ đề hoặc tự nhập chủ đề. <b>Mic ghi âm WAV thật</b>, không phụ thuộc tính năng SpeechRecognition của trình duyệt.</p>
    <div id="chat" class="chat"><div class="bubble ai">Hi! What shall we talk about today?</div></div>
    <div class="chat-compose"><input id="chatInput" placeholder="Nhập câu tiếng Anh hoặc nhấn mic…"/>
    <button id="sendBtn" class="primary">Gửi</button></div>
    <div class="toolbar" style="margin-top:13px"><button id="chatRecord" class="secondary">🎤 Bắt đầu ghi âm</button>
    <span id="chatVoiceStatus">Microphone sẵn sàng</span></div>
    <button class="primary" id="chatVoiceSend" style="margin-top:12px" disabled>📤 Gửi bản ghi âm cho AI</button>
    <div class="hintnote">Chế độ hội thoại cần key Gemini thật. Ứng dụng không tự tạo câu trả lời giả khi API lỗi.</div>
    </section><aside class="card span-4"><h3>🎯 Chủ đề giao tiếp</h3><label>Chủ đề bài học
    <select id="topicSelect"><option>Đang tải chủ đề…</option></select></label>
    <label class="hidden" id="customTopicWrap" style="margin-top:12px">Chủ đề em tự chọn<input id="customTopic" maxlength="80" placeholder="Ví dụ: My favourite food"/></label>
    <div class="lesson-box"><b>Gợi ý trò chuyện</b><p>Who / What / Where / How? Mỗi lượt nói 1–2 câu, nhận phản hồi ngắn.</p></div>
    <button class="secondary wide" onclick="navigate('live')">📹 Mở trò chuyện trực tiếp</button></aside></div>`;
  $('#sendBtn').onclick=sendChatEnhanced;
  $('#chatInput').onkeydown=e=>{if(e.key==='Enter')sendChatEnhanced();};
  $('#chatRecord').onclick=async()=>{await recordFeature({status:'#chatVoiceStatus',button:'#chatRecord'});$('#chatVoiceSend').disabled=!featureAudio;};
  $('#chatVoiceSend').onclick=sendChatVoice;
  try{
    const d=await api('/api/v1/conversation/topics');const sel=$('#topicSelect');
    sel.innerHTML=[...d.topics.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`),'<option value="__custom__">✏️ Chủ đề tự chọn</option>'].join('');
    sel.onchange=()=>$('#customTopicWrap').classList.toggle('hidden',sel.value!=='__custom__');
  }catch(e){toast(e.message,true);}
}
async function sendChatEnhanced(){
  const input=$('#chatInput'); const text=input?.value.trim();if(!text)return;
  addBubble(text,'user');input.value='';$('#sendBtn').disabled=true;
  try{const d=await api('/api/v1/conversation/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:selectedTopic(),text})});
    addBubble(d.reply,'ai');speechOutput(d.reply);
  }catch(e){addBubble('⚠️ '+e.message,'ai');toast(e.message,true)}finally{$('#sendBtn').disabled=false;}
}
async function sendChatVoice(){
  if(!featureAudio)return;
  const btn=$('#chatVoiceSend');btn.disabled=true;btn.textContent='⏳ Đang nhận dạng giọng nói…';
  try{const fd=new FormData();fd.append('topic',selectedTopic());fd.append('audio',featureAudio,'speaking.wav');
    const d=await api('/api/v1/conversation/voice',{method:'POST',body:fd});
    addBubble('🎤 '+d.transcript,'user');addBubble(d.reply,'ai');speechOutput(d.reply);featureAudio=null;
    $('#chatVoiceStatus').textContent='✅ Đã nhận dạng giọng nói bằng '+d.asr_mode;
  }catch(e){toast(e.message,true);$('#chatVoiceStatus').textContent='⚠️ '+e.message}
  finally{btn.textContent='📤 Gửi bản ghi âm cho AI';btn.disabled=!featureAudio;}
}

function renderLookSpeakEnhanced(){
  featureAudio=null;
  $('#content').innerHTML=`<div class="grid"><section class="card span-7"><h3>🖼️ Look & Speak – Nhìn tranh và nói</h3>
    <p>Tải một bức ảnh, <b>ghi âm câu tiếng Anh</b> về điều em nhìn thấy rồi gửi cho AI. Có thể dùng ô văn bản để dự phòng.</p>
    <label>Hình ảnh (JPG, PNG hoặc WebP)<input id="imageInput" type="file" accept="image/jpeg,image/png,image/webp" /></label>
    <div style="margin-top:12px"><img id="imagePreview" class="preview hidden" alt="Ảnh luyện nói" /></div>
    <div class="toolbar" style="margin-top:15px"><button id="lookRecord" class="secondary">🎤 Ghi âm tiếng Anh</button><span id="lookVoiceStatus">Chưa ghi âm</span></div>
    <label style="margin-top:14px">Hoặc nhập câu mô tả (không bắt buộc nếu đã ghi âm)
    <textarea id="lookAnswer" rows="3" placeholder="I can see a dog in the picture."></textarea></label>
    <button id="lookBtn" class="primary wide">✨ Phân tích ảnh + lời nói</button>
    <div class="hintnote">Với ghi âm, Gemini nghe lời nói và xem tranh trong cùng một lượt xử lí để phản hồi nhanh hơn.</div>
    </section><aside id="lookResult" class="card span-5"><div class="empty">Chọn ảnh và thu âm để bắt đầu.</div></aside></div>`;
  $('#imageInput').onchange=e=>{const f=e.target.files[0],p=$('#imagePreview');if(p.dataset.objectUrl)URL.revokeObjectURL(p.dataset.objectUrl);p.removeAttribute('data-object-url');if(f){const url=URL.createObjectURL(f);p.src=url;p.dataset.objectUrl=url;p.classList.remove('hidden');}else{p.removeAttribute('src');p.classList.add('hidden');}};
  $('#lookRecord').onclick=()=>recordFeature({status:'#lookVoiceStatus',button:'#lookRecord'});
  $('#lookBtn').onclick=submitLookEnhanced;
}
async function compactPictureForAI(file){
  if(!file||file.size<250000)return file;
  try{
    const bitmap=await createImageBitmap(file);const scale=Math.min(1,1024/Math.max(bitmap.width,bitmap.height));
    const canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
    const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
    const compressed=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',0.78));
    return compressed && compressed.size<file.size?new File([compressed],'look-speak.jpg',{type:'image/jpeg'}):file;
  }catch{return file;}
}
async function submitLookEnhanced(){
  const photo=$('#imageInput').files[0],typed=$('#lookAnswer').value.trim();
  if(!photo){toast('Hãy chọn ảnh để luyện nói.',true);return;}
  if(!featureAudio&&!typed){toast('Hãy ghi âm tiếng Anh hoặc nhập câu mô tả.',true);return;}
  const btn=$('#lookBtn');btn.disabled=true;btn.textContent='⏳ AI đang nghe và xem tranh…';
  const fd=new FormData();fd.append('image',await compactPictureForAI(photo));if(featureAudio)fd.append('audio',featureAudio,'look-speak.wav');else fd.append('answer',typed);
  try{const d=await api('/api/v1/multimodal/look-speak',{method:'POST',body:fd});
    $('#lookResult').innerHTML=`<p class="eyebrow">LOOK & SPEAK · ${esc(d.ai_mode)}</p>
    <p><b>🎤 Lời em nói:</b> ${esc(d.transcript)}</p>
    <div class="score-ring" style="--score:${d.score}"><strong>${Math.round(d.score)}</strong></div>
    <h3 style="margin-top:16px">${esc(d.feedback)}</h3>
    <div class="lesson-box"><b>Câu mẫu</b><p>${esc(d.model_sentence)}</p><b>Câu hỏi tiếp theo</b><p>${esc(d.next_question)}</p></div>
    <p class="hintnote">${esc(d.note)}${d.latency_ms?' · Thời gian xử lí: '+(d.latency_ms/1000).toFixed(1)+'s':''}</p>`;
    featureAudio=null;$('#lookVoiceStatus').textContent='✅ Đã phân tích. Có thể luyện tiếp.';
  }catch(e){toast(e.message,true);$('#lookResult').innerHTML=`<p class="errorline">⚠️ ${esc(e.message)}</p>`}
  finally{btn.disabled=false;btn.textContent='✨ Phân tích ảnh + lời nói';}
}

async function renderProfile(){
  const u=state.user;
  $('#content').innerHTML=`<div class="grid"><article class="card span-6"><h3>👤 Thông tin cá nhân</h3><p>Có thể sửa tên hiển thị và lớp học.</p>
    <form id="profileForm" class="formstack">
      <label>Họ và tên<input id="profileName" maxlength="80" minlength="2" required value="${esc(u.full_name)}"></label>
      <label>Email (không sửa trực tiếp)<input disabled value="${esc(u.email)}"></label>
      ${u.role==='student'?`<label>Khối lớp<select id="profileGrade">${[1,2,3,4,5].map(x=>`<option value="${x}" ${u.grade===x?'selected':''}>Lớp ${x}</option>`).join('')}</select></label>`:''}
      <button class="primary" type="submit">💾 Lưu thông tin</button></form></article>
    <article class="card span-6"><h3>🔐 Đổi mật khẩu</h3>
      <form id="passwordForm" class="formstack"><label>Mật khẩu hiện tại<input id="currentPass" type="password" required></label>
      <label>Mật khẩu mới (từ 8 ký tự)<input id="newPass" type="password" minlength="8" autocomplete="new-password" required></label>
      <label>Xác nhận mật khẩu mới<input id="confirmPass" type="password" minlength="8" autocomplete="new-password" required></label>
      <p class="hintnote" id="newPassHint" aria-live="polite">Nhập cùng một mật khẩu mới vào cả hai ô.</p>
      <button class="secondary" type="submit">Cập nhật mật khẩu</button></form>
      <p class="hintnote">Không chia sẻ tài khoản hoặc Gemini API key cho người khác.</p></article></div>`;
  $('#profileForm').onsubmit=async e=>{e.preventDefault();try{const payload={full_name:$('#profileName').value.trim()};
    if(u.role==='student')payload.grade=Number($('#profileGrade').value);
    const d=await api('/api/v1/profile',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    state.user=d;$('#sideUser').innerHTML=`<strong>${esc(d.full_name)}</strong>${esc(d.role)}${d.grade?` · Lớp ${d.grade}`:''}`;toast('Đã lưu hồ sơ.');
  }catch(err){toast(err.message,true)}};
  const checkPw=()=>{const a=$('#newPass').value,b=$('#confirmPass').value;
    $('#newPassHint').textContent=!b?'Nhập cùng một mật khẩu mới vào cả hai ô.':a===b?'✓ Hai mật khẩu mới trùng khớp.':'⚠ Hai mật khẩu mới không giống nhau.';
    $('#newPassHint').classList.toggle('v11-bad',!!b&&a!==b);
  };
  $('#newPass').addEventListener('input',checkPw);
  $('#confirmPass').addEventListener('input',checkPw);
  $('#passwordForm').onsubmit=async e=>{e.preventDefault();if($('#newPass').value!==$('#confirmPass').value){toast('Xác nhận mật khẩu không trùng khớp.',true);return;}
  try{await api('/api/v1/profile/password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:$('#currentPass').value,new_password:$('#newPass').value,confirm_password:$('#confirmPass').value})});
    e.target.reset();checkPw();toast('Đổi mật khẩu thành công.');}catch(err){toast(err.message,true)}};
}

// V9 audio/video: no facial emotion/attention inference; Bibi uses Gemini Live audio.
let liveMirrorPreview = true;
let liveFacing = 'user';
let liveVideoConsent = false;
let liveSessionVideoEnabled = false;
let liveCameraStarting = false;
let liveOutputTimer = null;
let liveSessionId = 0;
let liveHintPlayerWait=null;
let liveHintAudioFallback=null;
let liveHintTurn=false;
let liveHintAudioReceived=false;
let liveHintModelTurnPending=false;
let liveMicSpeechFrames=0;
const liveHints=new BrightSpeakLiveHints(reason=>triggerLiveHint(reason));
function clearLiveHintTimers(){
  liveHints.stop();clearTimeout(liveHintPlayerWait);liveHintPlayerWait=null;
  clearTimeout(liveHintAudioFallback);liveHintAudioFallback=null;
}
function markLiveStudentSpeech(){
  liveHints.speechDetected();
  clearTimeout(liveHintAudioFallback);liveHintAudioFallback=null;
}
function detectLiveVoice(data){
  // Conservative speech onset: ~120ms of non-trivial PCM energy in 3 x 40ms frames.
  if(!liveHints.eligible||liveHints.heardSpeech||liveHints.used)return;
  const samples=new DataView(data.buffer,data.byteOffset,data.byteLength);
  let sum=0,n=0;
  for(let i=0;i+1<samples.byteLength;i+=48){sum+=Math.abs(samples.getInt16(i,true));n++;}
  const level=n?sum/n/32768:0;
  liveMicSpeechFrames=level>0.018?liveMicSpeechFrames+1:0;
  if(liveMicSpeechFrames>=3)markLiveStudentSpeech();
}
function revealLiveSample(){
  const answer=$('#liveSampleAnswer');if(!answer)return;
  answer.parentElement.hidden=false;
  setLiveStatus('💡 Em có thể nói theo câu trả lời mẫu rồi thử lại nhé.');
}
function triggerLiveHint(reason){
  const exercise=currentLivePrompt();if(!exercise||!liveActive)return;
  revealLiveSample();
  if(liveWS?.readyState!==WebSocket.OPEN)return;
  liveHintTurn=true;liveHintAudioReceived=false;liveHintModelTurnPending=true;
  liveWS.send(JSON.stringify({type:'request_hint',prompt_id:exercise.id,reason}));
  setLiveStatus('💡 Bibi đang gợi ý câu trả lời mẫu…');
  // Fallback for Gemini Live service not producing any audio for the hint.
  clearTimeout(liveHintAudioFallback);
  liveHintAudioFallback=setTimeout(()=>{
    if(!liveActive||!liveHintModelTurnPending||liveHintAudioReceived)return;
    liveHintModelTurnPending=false;
    speakLiveFallback('You can say: '+exercise.sample_answer,true);
  },7500);
}
function waitUntilBibiFinishes(sid){
  clearTimeout(liveHintPlayerWait);
  function tick(){
    if(sid!==liveSessionId||!liveActive||liveHints.used||liveHints.heardSpeech)return;
    if(livePlayback?.isAudible()||liveBrowserTTSActive){liveHintPlayerWait=setTimeout(tick,120);return;}
    liveHints.assistantFinished();
  }
  liveHintPlayerWait=setTimeout(tick,150);
}
class LiveMicStreamer {
  constructor(socket){this.socket=socket;this.context=null;this.processor=null;this.stream=null;this.source=null;this.sink=null;this.dropped=0;}
  sendFrame(data){
    if(this.socket.readyState!==WebSocket.OPEN)return;
    // Avoid capturing Bibi voice through the speakers on a child device.
    if(livePlayback?.isAudible()||liveBrowserTTSActive)return;
    // Live websocket backpressure: audio is real-time, never buffer unlimited old chunks.
    if(this.socket.bufferedAmount > 256*1024){this.dropped++;return;}
    detectLiveVoice(data);
    this.socket.send(JSON.stringify({type:'audio',data:bufferToB64(data)}));
  }
  async start(){
    this.stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    this.context=new (window.AudioContext||window.webkitAudioContext)();
    await this.context.resume();
    this.source=this.context.createMediaStreamSource(this.stream);
    if(this.context.audioWorklet && typeof AudioWorkletNode!=='undefined'){
      try{
        await this.context.audioWorklet.addModule('/static/live-audio-worklet.js');
        this.processor=new AudioWorkletNode(this.context,'brightspeak-voice-worklet');
        this.processor.port.onmessage=(e)=>{if(e.data&&e.data.pcm)this.sendFrame(new Uint8Array(e.data.pcm));};
        this.sink=this.context.createGain();this.sink.gain.value=0;
        this.source.connect(this.processor);this.processor.connect(this.sink);this.sink.connect(this.context.destination);
        return;
      }catch(err){console.warn('AudioWorklet unavailable; using ScriptProcessor fallback',err?.name||'error');}
    }
    this.processor=this.context.createScriptProcessor(2048,1,1);
    this.processor.onaudioprocess=e=>{
      const input=e.inputBuffer.getChannelData(0),ratio=this.context.sampleRate/16000;
      const count=Math.floor(input.length/ratio),pcm=new Int16Array(count);
      for(let i=0;i<count;i++){
        const src=Math.min(input.length-1,Math.round(i*ratio));
        const val=Math.max(-1,Math.min(1,input[src]));pcm[i]=val<0?val*0x8000:val*0x7fff;
      }
      this.sendFrame(new Uint8Array(pcm.buffer));
    };
    this.sink=this.context.createGain();this.sink.gain.value=0;
    this.source.connect(this.processor);this.processor.connect(this.sink);this.sink.connect(this.context.destination);
  }
  async stop(){
    if(this.processor){if('onaudioprocess' in this.processor)this.processor.onaudioprocess=null;
      this.processor.disconnect();this.processor.port?.close?.();}
    this.source?.disconnect();this.sink?.disconnect();
    this.stream?.getTracks().forEach(track=>track.stop());
    if(this.context && this.context.state!=='closed')await this.context.close();
    this.context=null;this.stream=null;this.processor=null;this.source=null;this.sink=null;
  }
}
function bufferToB64(data){let binary='';for(let i=0;i<data.length;i++)binary+=String.fromCharCode(data[i]);return btoa(binary);}
function b64ToBuffer(data){const str=atob(data);const a=new Uint8Array(str.length);for(let i=0;i<str.length;i++)a[i]=str.charCodeAt(i);return a.buffer;}
class LiveAudioPlayer{
  constructor(){
    this.ctx=new (window.AudioContext||window.webkitAudioContext)();
    this.nextTime=0;
    this.sources=new Set();
    this.generation=0;
  }
  isAudible(){return this.sources.size>0 && this.nextTime>this.ctx.currentTime;}
  async play(base64){
    const generation=this.generation;
    if(this.ctx.state==='closed')return;
    if(this.ctx.state==='suspended')await this.ctx.resume();
    if(generation!==this.generation || this.ctx.state==='closed')return;
    const bytes=b64ToBuffer(base64);if(bytes.byteLength<2)return;
    const raw=new DataView(bytes),buffer=this.ctx.createBuffer(1,Math.floor(bytes.byteLength/2),24000);
    const out=buffer.getChannelData(0);
    for(let i=0;i<out.length;i++)out[i]=raw.getInt16(i*2,true)/32768;
    // Network delivery can outpace playback. Preserve scheduled speech until a real interruption.
    const source=this.ctx.createBufferSource();source.buffer=buffer;source.connect(this.ctx.destination);
    const start=Math.max(this.ctx.currentTime+.02,this.nextTime);
    source.onended=()=>{
      this.sources.delete(source);
      if(!this.sources.size)$('#liveBibi')?.classList.remove('bibi-speaking');
    };
    this.sources.add(source);
    source.start(start);
    this.nextTime=start+buffer.duration;
    $('#liveBibi')?.classList.add('bibi-speaking');
  }
  interrupt(){
    // Gemini interrupted the response: cancel every scheduled and playing segment.
    ++this.generation;
    for(const source of this.sources){try{source.stop()}catch{}}
    this.sources.clear();
    this.nextTime=this.ctx.currentTime;
    $('#liveBibi')?.classList.remove('bibi-speaking');
  }
  async stop(){this.interrupt();if(this.ctx?.state!=='closed')await this.ctx.close();}
}
// V11 turn-aware subtitles: one model utterance is ONE chat message, regardless
// of how many streaming output_text chunks the provider emits.
let liveTurnText={ai:'',student:''};
let liveTurnBubble={ai:null,student:null};
let liveTurnFrozen={ai:false,student:false};
function resetLiveTurnState(){
  liveTurnText={ai:'',student:''};liveTurnBubble={ai:null,student:null};
  liveTurnFrozen={ai:false,student:false};
}
function appendLiveText(text,who){
  const chat=$('#liveTranscript');if(!chat||!String(text||'').trim())return;
  const part=String(text).trim();
  if(liveTurnFrozen[who]){liveTurnText[who]='';liveTurnBubble[who]=null;liveTurnFrozen[who]=false;}
  const prev=liveTurnText[who];
  // Gemini can send either partial deltas or a cumulative transcription.
  const full=part===prev?prev:(prev&&part.startsWith(prev)?part:(prev&&prev.endsWith(part)?prev:(prev?prev+' '+part:part)));
  liveTurnText[who]=full.slice(0,3000);
  if(!liveTurnBubble[who]||!liveTurnBubble[who].isConnected){
    const bubble=document.createElement('div');
    bubble.className='bubble '+(who==='student'?'user':'ai');
    bubble.dataset.turnSpeaker=who;
    chat.appendChild(bubble);liveTurnBubble[who]=bubble;
  }
  liveTurnBubble[who].textContent=(who==='student'?'Em: ':'Bibi: ')+liveTurnText[who];
  chat.scrollTop=chat.scrollHeight;
  const caption=$(who==='student'?'#studentCaption':'#bibiCaption');
  if(caption)caption.textContent=liveTurnText[who];
}
function closeLiveTurn(){
  for(const who of ['ai','student']){
    if(liveTurnBubble[who]){
      liveTurnBubble[who].dataset.complete='true';
      liveTurnFrozen[who]=true;
    }
  }
}

function setLiveStatus(text){const s=$('#liveStatus');if(s)s.textContent=text;}
function applyLiveMirror(){const v=$('#liveVideo');if(v)v.style.transform=liveMirrorPreview?'scaleX(-1)':'none';
  const b=$('#liveMirror');if(b)b.textContent=liveMirrorPreview?'↔ Bỏ lật gương':'↔ Lật gương';}
// Original child-friendly prompts, NOT extracts from commercial textbooks.
// They are visual scaffolds only; the 3-sentence goal counts actual microphone transcripts.
// V12: one authoritative dataset fetched from backend, filtered by enrolled grade.
// Never substitute an unrestricted/fixed topic list for curriculum lesson content.
let liveCurriculumPrompts=[];
let livePromptIndex=0;
let liveLastAudioTurn=false;
let liveFallbackVoice=false;
function livePromptItems(){
  const topic=$('#liveTopic')?.value||'';
  const skill=$('#liveSkill')?.value||'';
  return liveLessonRows(topic).filter(x=>!skill || x.skill===skill);
}
function liveTopicRows(topic){
  if(topic.startsWith('review-block:')){
    const block=Number(topic.split(':')[1]),size=Number(state.user.grade)<3?4:5;
    return liveCurriculumPrompts.filter(p=>p.unit && Math.ceil(p.unit/size)===block && p.skill==='Hỏi đáp và mẫu câu');
  }
  return liveCurriculumPrompts.filter(p=>p.topic===topic);
}
function liveLessonRows(topic){
  const lesson=$('#liveLesson')?.value;
  return liveTopicRows(topic).filter(p=>!lesson || String(p.lesson_no||0)===lesson);
}
function refreshLiveChoices(resetSkills=true,resetLesson=false){
  const topic=$('#liveTopic').value;
  if(resetLesson){
    const numbers=[...new Set(liveTopicRows(topic).map(p=>p.lesson_no||0))].sort();
    $('#liveLesson').innerHTML='<option value="">Cả bài</option>'+numbers.filter(n=>n).map(n=>'<option value="'+n+'">Lesson '+n+'</option>').join('');
    $('#liveLesson').parentElement.hidden=!numbers.some(n=>n);
  }
  const rows=liveLessonRows(topic);
  if(resetSkills){
    $('#liveSkill').innerHTML='<option value="">Tất cả hoạt động</option>'+[...new Set(rows.map(p=>p.skill))].map(s=>'<option>'+esc(s)+'</option>').join('');
  }
  $('#liveSentence').innerHTML=livePromptItems().map((p,i)=>'<option value="'+i+'">'+esc(p.sample_answer+' · '+p.question)+'</option>').join('');
  livePromptIndex=0;
}
function currentLivePrompt(){
  const all=livePromptItems();return all.length?all[livePromptIndex%all.length]:null;
}
function sendLivePracticePrompt(){
  clearLiveHintTimers();liveHintTurn=false;liveMicSpeechFrames=0;
  const prompt=currentLivePrompt();
  if(!prompt)return;
  if(liveActive && liveWS?.readyState===WebSocket.OPEN){
    if('speechSynthesis' in window)speechSynthesis.cancel();
    livePlayback?.interrupt();
    resetLiveTurnState();
    liveWS.send(JSON.stringify({type:'practice_prompt',prompt_id:prompt.id}));
    setLiveStatus('🔊 Bibi đang hỏi câu em chọn. Nghe xong rồi hãy trả lời.');
  }else{
    if($('#liveActivity')?.value==='read'){
      readEnglish(prompt.sample_answer,prompt.id);
      setLiveStatus('Em nghe câu mẫu rồi đọc lại nhé.');
    }else{
      readEnglish(prompt.question);
      setLiveStatus('Bibi đọc câu hỏi. Em hãy thử trả lời rồi bấm Bắt đầu để hội thoại.');
    }
  }
}
function updateLivePrompt(ask=true){
  stopSample();
  const all=livePromptItems(),p=currentLivePrompt();
  const question=$('#liveSampleQuestion'),answer=$('#liveSampleAnswer');
  if($('#liveSentence') && all.length)$('#liveSentence').value=String(livePromptIndex%all.length);
  if(question)question.textContent=p?.question||'Chưa có câu luyện';
  if(answer){answer.textContent=p?.sample_answer||'Đang tải bài học';answer.parentElement.hidden=true;}
  clearLiveHintTimers();liveMicSpeechFrames=0;
  const n=$('#liveSampleNumber');if(n)n.textContent=p?`${livePromptIndex%all.length+1} / ${all.length}`:'0 / 0';
  const source=$('#liveLessonSource');if(source)source.textContent=p?(p.source==='teacher'?'✅ Bài GV giao · đúng khối lớp':(p.source_kind==='lesson_page'?`Câu trong SGK · trang PDF ${p.source_pdf}`:p.source_kind==='activity_adaptation'?`Luyện theo hoạt động · trang PDF ${p.source_pdf}`:`Mẫu theo Book Map · trang PDF ${p.book_map_pdf} · Unit bắt đầu ở trang in ${p.printed_page}`)):'Không tìm thấy bài luyện';
  if(p && $('#guidedReading'))mountReading($('#guidedReading'),p.id,p.sample_answer,p.topic);
  updateBookReference(p);
  if(ask&&liveActive)sendLivePracticePrompt();
}
async function loadLivePrompts(){
  try{
    const data=await api('/api/v1/live/prompts');
    if(state.page!=='live')return;
    liveCurriculumPrompts=data.prompts||[];
    const topics=[...new Set(liveCurriculumPrompts.map(p=>p.topic))];
    const sel=$('#liveTopic');if(!sel)return;
    sel.innerHTML=topics.map(t=>`<option value="${esc(t)}">${esc(t)}</option>`).join('');
    if(topics.length){
      for(let block=1;block<=4;block++){
        sel.add(new Option('Ôn nhóm Unit · Review '+block,'review-block:'+block));
      }
    }
    refreshLiveChoices(true,true);
    if(!topics.length){sel.innerHTML='<option>Chưa có bài phù hợp</option>';$('#liveStart').disabled=true;}
    livePromptIndex=0;updateLivePrompt(false);
  }catch(err){setLiveStatus('⚠️ Không tải được bài theo lớp: '+err.message);}
}
let liveBrowserTTSActive=false;
function speakLiveFallback(text, replay=false){
  // Only when the server explicitly confirms that the Gemini turn has NO audio.
  if(!text || !('speechSynthesis' in window)){
    setLiveStatus('⚠️ Gemini chỉ trả chữ, trình duyệt không hỗ trợ đọc câu.');return;
  }
  if(liveLastAudioTurn && !replay)return;
  speechSynthesis.cancel();
  const voice=new SpeechSynthesisUtterance(text);
  voice.lang='en-US';voice.rate=Number(state.user?.grade||3)<3?.73:.86;
  liveBrowserTTSActive=true;
  voice.onstart=()=>{liveBrowserTTSActive=true;$('#liveBibi')?.classList.add('bibi-speaking');setLiveStatus('🔉 Đang đọc câu bằng giọng của thiết bị.');};
  voice.onend=voice.onerror=()=>{liveBrowserTTSActive=false;$('#liveBibi')?.classList.remove('bibi-speaking');};
  speechSynthesis.speak(voice);
}
function renderLive(){
  resetLiveTurnState();
  $('#content').innerHTML=`<section class="v11-meet" aria-label="Phòng trò chuyện tiếng Anh">
    <header class="v11-meet-header"><div><span class="v11-live-dot">● BRIGHTSPEAKAI LIVE · LỚP ${state.user?.grade||3}</span><h2>Phòng luyện nói cùng Bibi</h2><p>Bibi đọc câu hỏi bằng tiếng Anh; em trả lời bằng giọng nói. Nếu cần, Bibi gợi ý sau 5 giây.</p></div><span class="v11-goal" id="liveGoal">🎯 3 câu/ngày</span></header>
    <section class="card" id="guidedReading"></section><div id="readingFeedback" aria-live="polite"></div>
    <div class="v11-meet-main">
      <div class="v11-meet-stage">
        <div class="v11-tiles">
          <div class="v11-tile"><div id="liveBibi" class="v11-tile-inner v11-bibi"><img src="/static/bibi-robot.png" alt="Robot Bibi"/><span class="v11-name">🤖 Bibi · Gemini Live</span></div><div class="v11-subtitle" id="bibiCaption">Hello! I am Bibi. Let's practise English together!</div></div>
          <div class="v11-tile"><div class="v11-tile-inner v11-student"><video id="liveVideo" autoplay playsinline muted></video><div id="livePlaceholder" class="v11-camera-off">📷 Camera đang tắt. Em vẫn có thể luyện nói bằng mic.</div><span class="v11-name">🎤 Em · Học sinh</span></div><div class="v11-subtitle" id="studentCaption">Em có thể trả lời khi Bibi nói xong.</div></div>
        </div>
        <div class="v11-meet-toolbar" role="toolbar" aria-label="Điều khiển phiên học">
           <label>Hoạt động<select id="liveActivity"><option value="talk">Hỏi – đáp cùng Bibi</option><option value="read">Đọc theo Bibi</option></select></label><button id="liveStart" class="primary">▶ Bắt đầu nói</button><button id="liveStop" class="danger" disabled>■ Kết thúc</button>
           <button id="liveReplay" class="secondary" disabled>🔊 Nghe lại câu vừa rồi</button><button id="liveCameraToggle" class="secondary" disabled>📷 Bật camera</button><button id="liveMirror" class="secondary" type="button">↔ Bỏ lật gương</button><button id="liveFlipCamera" class="secondary" disabled>🔄 Đổi camera</button>
        </div><div class="v11-meet-status" id="liveStatus" aria-live="polite">Bấm Bắt đầu để trò chuyện cùng Bibi. Camera tùy chọn.</div>
      </div>
      <aside class="v11-meet-aside"><div class="v11-panel"><h3>💬 Hội thoại</h3><p class="hintnote">Mỗi lượt nói của Bibi được gộp vào một khung chat duy nhất.</p><div id="liveTranscript" class="v11-chat" aria-live="polite"></div></div>
       <div class="v11-panel"><h3>💡 Gợi ý luyện nói</h3><div class="v11-form-line"><label>Chủ đề trong chương trình lớp ${state.user?.grade||3}<select id="liveTopic"><option value="">Đang tải học liệu theo lớp…</option></select></label></div><label>Bài trong Unit<select id="liveLesson"></select></label><label>Hoạt động<select id="liveSkill"></select></label><label>Chọn từ hoặc câu<select id="liveSentence"></select></label><p id="liveLessonSource" class="v12-source-note">Câu luyện tự biên soạn, gắn với chủ đề Global Success.</p>
          <details id="bookReference"><summary>Đối chiếu với sách của em</summary><p id="bookPageNote"></p><label>Chọn PDF Global Success trên máy<input id="sourceFile" type="file" accept="application/pdf"></label><a id="sourcePage" target="_blank" rel="noopener" hidden>Mở trang sách</a><p id="sourceStatus" role="status"></p></details><div class="v11-suggestion"><small>🤖 Bibi nói</small><strong id="liveSampleQuestion"></strong></div><div class="v11-suggestion answer"><small>🎤 Em có thể nói</small><strong id="liveSampleAnswer"></strong></div>
          <div class="v11-sample-actions"><span class="badge purple" id="liveSampleNumber">1 / 3</span><button id="liveNextSample" class="secondary">Câu tiếp</button><button id="liveAskSample" class="primary" type="button">🔊 Bibi đọc câu hỏi</button><button id="liveShowHint" class="secondary" type="button">💡 Gợi ý trả lời</button></div>
          <p class="hintnote">Nếu em chưa trả lời sau 5 giây kể từ khi Bibi nói xong, Bibi sẽ tự gợi ý. Em có thể xem đáp án mẫu bất kỳ lúc nào.</p>
          <label class="v11-camera-consent"><input type="checkbox" id="liveVideoConsent"/> Người giám hộ đồng ý sử dụng camera cho phiên học. Không dùng hình ảnh để suy đoán cảm xúc hay năng lực.</label></div>
      </aside>
    </div>
  </section>`;
  const replay=$('#liveReplay');
  replay.onclick=()=>{
    const sentence=replay.dataset.sentence;
    if(sentence && !livePlayback?.isAudible() && !liveBrowserTTSActive){
      speakLiveFallback(sentence, true);
    }else{
      setLiveStatus('Chờ Bibi nói xong rồi nghe lại nhé.');
    }
  };
  $('#liveStart').onclick=startLive;
  $('#liveStop').onclick=()=>stopLive({closeCamera:true});
  $('#liveCameraToggle').onclick=()=>liveCamera?stopLiveCamera():startLiveCamera();
  $('#liveMirror').onclick=()=>{liveMirrorPreview=!liveMirrorPreview;applyLiveMirror();};
  $('#liveFlipCamera').onclick=async()=>{liveFacing=liveFacing==='user'?'environment':'user';if(liveCamera)await startLiveCamera(true);else applyLiveMirror();};
  $('#liveVideoConsent').onchange=e=>{
    liveVideoConsent=!!e.target.checked;
    $('#liveCameraToggle').disabled=!liveVideoConsent;
    $('#liveFlipCamera').disabled=!liveVideoConsent;
    if(!liveVideoConsent)stopLiveCamera();
    if(liveActive && liveVideoConsent && !liveSessionVideoEnabled)setLiveStatus('Camera đang xem trước. Để gửi hình cho Gemini, cần tạo phiên Live mới.');
  };
  $('#liveLesson').onchange=()=>{refreshLiveChoices();updateLivePrompt(true);};
  $('#liveTopic').onchange=()=>{refreshLiveChoices(true,true);updateLivePrompt(true);};
  $('#liveSkill').onchange=()=>{refreshLiveChoices(false);updateLivePrompt(true);};
  $('#liveSentence').onchange=e=>{livePromptIndex=Number(e.target.value);updateLivePrompt(true);};
  $('#sourceFile').onchange=attachSourceBook;
  $('#liveNextSample').onclick=()=>{livePromptIndex++;updateLivePrompt(true);};
  $('#liveAskSample').onclick=sendLivePracticePrompt;
  $('#liveShowHint').onclick=()=>{
    revealLiveSample();
    if(liveActive){liveHints.manual();}
    else{const p=currentLivePrompt();if(p)readEnglish(p.sample_answer,p.id);}
  };
  applyLiveMirror();loadLivePrompts();
  api('/api/v1/speaking/today').then(g=>{const tag=$('#liveGoal');if(tag)tag.textContent=`🎯 ${g.count||0} / 3 câu hôm nay`}).catch(()=>{});
}

async function startLiveCamera(replace=false){
  if(liveCameraStarting)return;
  liveVideoConsent=!!$('#liveVideoConsent')?.checked;
  if(!liveVideoConsent){toast('Cần đồng ý bật camera trước.',true);return;}
  liveCameraStarting=true;
  const requestId=++liveCameraRequestId;
  try{
    // Switching between cameras on Windows often fails unless the old track is released first.
    if(replace && liveCamera){const old=liveCamera;liveCamera=null;old.getTracks().forEach(t=>t.stop());}
    if(liveCamera)return;
    const newStream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:360},facingMode:{ideal:liveFacing}},audio:false});
    if(requestId!==liveCameraRequestId||!$('#liveVideoConsent')?.checked||state.page!=='live'){
      newStream.getTracks().forEach(t=>t.stop());return;
    }
    const preview=$('#liveVideo');if(!preview){newStream.getTracks().forEach(t=>t.stop());return;}
    liveCamera=newStream;
    preview.srcObject=liveCamera;applyLiveMirror();
    // Video is muted and playsinline. A blocked play() must not stop the camera track.
    await preview.play().catch(()=>{});
    $('#livePlaceholder').style.display='none';
    $('#liveCameraToggle').textContent='📷 Tắt camera';
    const track=liveCamera.getVideoTracks()[0];
    if(track)track.onended=()=>{
      if(requestId===liveCameraRequestId){stopLiveCamera();setLiveStatus('Camera bị ngắt bởi Windows/trình duyệt. Em có thể bật lại; mic vẫn dùng được.');}
    };
    // Reuse ONE tiny canvas to reduce GC/CPU spikes.
    if(liveFrameTimer)clearInterval(liveFrameTimer);
    const canvas=document.createElement('canvas');canvas.width=320;canvas.height=180;
    const context=canvas.getContext('2d',{alpha:false});
    liveFrameTimer=setInterval(()=>{
      if(!liveCamera||!liveActive||!liveSessionVideoEnabled||liveWS?.readyState!==WebSocket.OPEN||liveWS.bufferedAmount>96*1024)return;
      const video=$('#liveVideo');if(!video||video.readyState<2||!video.videoWidth)return;
      try{context.drawImage(video,0,0,320,180);liveWS.send(JSON.stringify({type:'video',data:canvas.toDataURL('image/jpeg',0.42).split(',')[1]}))}catch(err){console.warn('Camera frame skipped:',err?.name||'error')}
    },4000);
    setLiveStatus(liveActive?'🟢 Camera bật · Bibi đang nghe':'📷 Camera xem trước đã bật. Bấm Bắt đầu để nói với Bibi.');
  }catch(e){
    toast('Camera chưa mở được ('+(e?.name||'unknown')+'). Mic vẫn có thể hoạt động.',true);
    setLiveStatus('⚠️ Không mở được camera. Kiểm tra quyền camera và thử lại.');
  }finally{liveCameraStarting=false;}
}
function stopLiveCamera(){
  ++liveCameraRequestId;
  if(liveFrameTimer)clearInterval(liveFrameTimer);liveFrameTimer=null;
  const old=liveCamera;liveCamera=null;
  if(old){old.getTracks().forEach(track=>{track.onended=null;track.stop()});}
  const preview=$('#liveVideo');if(preview)preview.srcObject=null;
  const placeholder=$('#livePlaceholder');if(placeholder)placeholder.style.display='flex';
  const b=$('#liveCameraToggle');if(b)b.textContent='📷 Bật camera';
}
async function startLive(){
  if(liveActive||liveWS||liveConnecting)return;
  if(readingBusy){toast('Em hãy hoàn thành lượt đọc đang ghi trước nhé.');return;}
  if(!window.isSecureContext){toast('Live cần HTTPS hoặc localhost.',true);return;}
  if(!state.health?.gemini_enabled){toast('Hãy nhập Gemini key trong GEMINI_KEY.txt rồi khởi động lại BrightSpeakAI.',true);return;}
  stopSample();clearLiveHintTimers();liveHintTurn=false;liveHintAudioReceived=false;
  liveConnecting=true;resetLiveTurnState();
  if('speechSynthesis' in window)speechSynthesis.cancel();
  $('#liveActivity').disabled=true;$('#liveStart').disabled=true;liveVideoConsent=$('#liveVideoConsent').checked;liveSessionVideoEnabled=liveVideoConsent;
  let sid=++liveSessionId;
  const proto=location.protocol==='https:'?'wss:':'ws:';
  try{
    // Resume audio in click handler to avoid autoplay gesture rejection.
    livePlayback=new LiveAudioPlayer();await livePlayback.ctx.resume();
    liveWS=new WebSocket(`${proto}//${location.host}/api/v1/live/ws`);
    await new Promise((resolve,reject)=>{let timeout=setTimeout(()=>reject(new Error('Kết nối Live quá hạn.')),14000);
      liveWS.addEventListener('open',()=>{clearTimeout(timeout);resolve()},{once:true});
      liveWS.addEventListener('error',()=>{clearTimeout(timeout);reject(new Error('WebSocket không thể mở'))},{once:true});});
    if(sid!==liveSessionId)return;
    if(!currentLivePrompt()){throw new Error('Chưa tải xong câu luyện đúng khối lớp.');}
    liveWS.send(JSON.stringify({type:'init',activity:$('#liveActivity').value,access_token:token(),prompt_id:currentLivePrompt().id,video_consent:liveVideoConsent}));
    setLiveStatus('Đang kết nối Gemini Live…');
    liveWS.onmessage=event=>{
      if(sid!==liveSessionId)return;
      let d;try{d=JSON.parse(event.data)}catch{return;}
      if(d.type==='error'){liveLastError=d.message;toast(d.message,true);stopLive({closeCamera:false,reason:'⚠️ '+d.message});return;}
      if(d.type==='ready'){
        liveActive=true;liveConnecting=false;$('#liveStop').disabled=false;
        liveHints.reset();liveMicSpeechFrames=0;
        setLiveStatus('🟢 Bibi đã kết nối. Hãy nói một câu tiếng Anh.');
        (async()=>{
          const microphone=new LiveMicStreamer(liveWS);liveMic=microphone;
          try{await microphone.start();
            if(sid!==liveSessionId){await microphone.stop();return;}
            setLiveStatus('🎙️ Mic đã mở. Em nghe Bibi, rồi nói khi Bibi dừng nhé.');
            // Camera may already be previewing; never reopen or reset its track here.
          }catch(err){if(sid!==liveSessionId)return;toast(micError(err),true);setLiveStatus('Không truy cập được microphone.');await stopLive({closeCamera:false})}
        })();
      }
      if(d.type==='reading_feedback')showReadingFeedback($('#readingFeedback'),d);
      if(d.type==='input_text'){
        markLiveStudentSpeech();
        if(liveTurnText.ai){liveTurnFrozen.ai=true;}
        appendLiveText(d.text,'student');
        setLiveStatus('🎤 Bibi đã nhận nội dung em nói và đang chuẩn bị phản hồi phù hợp.');
      }
      if(d.type==='output_text')appendLiveText(d.text,'ai');
      if(d.type==='audio'&&livePlayback){
        if(liveHintTurn){liveHintAudioReceived=true;liveHintModelTurnPending=false;
          clearTimeout(liveHintAudioFallback);liveHintAudioFallback=null;}
        liveLastAudioTurn=true;
        if(liveBrowserTTSActive&&'speechSynthesis' in window)speechSynthesis.cancel();
        liveBrowserTTSActive=false;
        livePlayback.play(d.data).catch(()=>setLiveStatus('Không phát được âm thanh. Kiểm tra loa và quyền phát âm thanh của trình duyệt.'));
        setLiveStatus('🔊 Bibi đang nói bằng giọng Gemini Live…');
      }
      if(d.type==='interrupted'){
        markLiveStudentSpeech();
        livePlayback?.interrupt();if('speechSynthesis' in window)speechSynthesis.cancel();liveBrowserTTSActive=false;
        closeLiveTurn();liveLastAudioTurn=false;
        setLiveStatus('Bibi đang lắng nghe câu của em…');
      }
      if(d.type==='error_notice')toast(d.message,true);
      if(d.type==='hint_ready'){
        revealLiveSample();
        if(d.sample_answer&&d.prompt_id===currentLivePrompt()?.id){
          $('#liveSampleAnswer').textContent=d.sample_answer;
        }
      }
      if(d.type==='prompt_active'){
        clearLiveHintTimers();liveMicSpeechFrames=0;liveHintTurn=false;
        setLiveStatus('🔊 Bibi đang đọc câu hỏi mới.');
      }
      if(d.type==='daily_goal'){$('#liveGoal').textContent=`🎯 ${d.goal?.count||0} / 3 câu hôm nay`;}
      if(d.type==='turn_complete'){
        const aiText=liveTurnFrozen.ai?'':liveTurnText.ai;
        const bibiHasSpoken=Boolean(d.had_audio||liveLastAudioTurn||aiText);
        const wasHintTurn=liveHintTurn;
        const replay=$('#liveReplay');
        if(aiText && replay && 'speechSynthesis' in window){
          replay.dataset.sentence=aiText;
          replay.disabled=false;
        }
        if(!d.had_audio&&!liveLastAudioTurn && aiText)speakLiveFallback(aiText);
        closeLiveTurn();liveLastAudioTurn=false;
        if(wasHintTurn){
          liveHintTurn=false;liveHintModelTurnPending=false;
          clearTimeout(liveHintAudioFallback);liveHintAudioFallback=null;
        }else if(bibiHasSpoken){
          liveHints.reset();liveMicSpeechFrames=0;
          waitUntilBibiFinishes(sid);
        }
        if(!liveBrowserTTSActive&&!livePlayback?.isAudible())$('#liveBibi')?.classList.remove('bibi-speaking');
      }
    };
    liveWS.onclose=()=>{if(sid===liveSessionId&&liveWS)stopLive({closeCamera:false,reason:'Mất kết nối Gemini Live. Camera xem trước vẫn bật nếu em đã cho phép; bấm Bắt đầu để kết nối lại.'});};
  }catch(err){toast(micError(err),true);await stopLive({closeCamera:false,reason:'Không kết nối được Gemini Live. Có thể kiểm tra Gemini key/mạng rồi thử lại.'});}
}
async function stopLive({closeCamera=true,reason=''}={}){
  clearLiveHintTimers();liveHintTurn=false;liveHintModelTurnPending=false;liveMicSpeechFrames=0;
  ++liveSessionId;liveActive=false;liveConnecting=false;liveSessionVideoEnabled=false;
  if('speechSynthesis' in window)speechSynthesis.cancel();liveBrowserTTSActive=false;liveLastAudioTurn=false;
  if(closeCamera)stopLiveCamera();clearTimeout(liveOutputTimer);
  if(liveMic){await liveMic.stop().catch(()=>{});liveMic=null;}
  const ws=liveWS;liveWS=null;
  if(ws){try{if(ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({type:'end'}));ws.close()}catch{}}
  const p=livePlayback;livePlayback=null;if(p)await p.stop().catch(()=>{});
  if($('#liveActivity'))$('#liveActivity').disabled=false;
  const start=$('#liveStart'),stop=$('#liveStop');if(start)start.disabled=false;if(stop)stop.disabled=true;
  const cam=$('#liveCameraToggle'),flip=$('#liveFlipCamera');if(cam)cam.disabled=!$('#liveVideoConsent')?.checked;if(flip)flip.disabled=!$('#liveVideoConsent')?.checked;
  $('#liveBibi')?.classList.remove('bibi-speaking');
  if(reason)setLiveStatus(reason);else setLiveStatus('Phiên Live đã kết thúc. Có thể bắt đầu lại.');
}
// Replace only the broken conversation and picture-speaking views; preserve the existing UI shell.
renderConversation=renderConversationEnhanced;
renderLookSpeak=renderLookSpeakEnhanced;

async function renderAdminEnhanced(){
  $('#content').innerHTML='<div class="card"><div class="empty">Đang tải quản trị tài khoản...</div></div>';
  try{
    const d=await api('/api/v1/admin/overview');
    const teachers=d.users.filter(u=>u.role==='teacher');
    const students=d.users.filter(u=>u.role==='student');
    $('#content').innerHTML=`<div class="grid"><article class="card span-4 metric"><div><small>Tài khoản</small><b>${d.users.length}</b></div><span>👥</span></article>
      <article class="card span-4 metric"><div><small>Bài học</small><b>${d.lesson_count}</b></div><span>📚</span></article>
      <article class="card span-4 metric"><div><small>Lượt luyện</small><b>${d.attempt_count}</b></div><span>🎤</span></article>
      <article class="card span-7"><h3>👥 Quản lý tài khoản</h3><p>Chỉ admin được bật/tắt tài khoản. Không thể tắt tài khoản của chính mình.</p>
        <div class="table-wrap"><table class="data-table"><thead><tr><th>Họ và tên</th><th>Vai trò</th><th>Email</th><th>Trạng thái</th></tr></thead>
        <tbody>${d.users.map(u=>`<tr><td>${esc(u.full_name)}</td><td>${esc(u.role)}</td><td>${esc(u.email)}</td><td>
          <button class="${u.active?'danger':'secondary'}" data-toggle-user="${esc(u.id)}" data-active="${u.active?'false':'true'}">${u.active?'Vô hiệu hóa':'Kích hoạt'}</button>
        </td></tr>`).join('')}</tbody></table></div></article>
      <article class="card span-5"><h3>🏫 Phân công HS cho GV</h3><p>GV chỉ xem báo cáo của HS đã được admin gán.</p>
        <form id="assignStudent" class="formstack"><label>Giáo viên<select id="assignTeacher">${teachers.map(u=>`<option value="${esc(u.id)}">${esc(u.full_name)} (${esc(u.email)})</option>`).join('')}</select></label>
        <label>Học sinh<select id="assignLearner">${students.map(u=>`<option value="${esc(u.id)}">${esc(u.full_name)} (${esc(u.email)})</option>`).join('')}</select></label>
        <button class="primary" type="submit" ${(!teachers.length||!students.length)?'disabled':''}>Phân công</button></form>
        <p class="hintnote">Đây là phân quyền theo danh sách HS được gán, không phải hệ thống đa trường/tenant đầy đủ.</p></article>
      <article class="card span-12"><h3>➕ Tạo tài khoản GV / HS (thử nghiệm có kiểm soát)</h3>
        <p>Admin tạo tài khoản để thử Cloud khi chưa cấu hình SMTP. Chỉ tạo tài khoản HS khi đã có sự đồng ý phù hợp của người giám hộ. Mật khẩu ban đầu cần đổi sau khi đăng nhập.</p>
        <form id="cloudNewUser" class="formstack">
          <label>Họ tên<input id="cloudUserName" required minlength="2" maxlength="80" placeholder="Họ tên người dùng"></label>
          <label>Email<input id="cloudUserEmail" type="email" required placeholder="example@school.edu.vn"></label>
          <label>Vai trò<select id="cloudUserRole"><option value="student">Học sinh</option><option value="teacher">Giáo viên</option></select></label>
          <label>Khối lớp (cho HS)<select id="cloudUserGrade">${[1,2,3,4,5].map(n=>`<option value="${n}">${n}</option>`).join('')}</select></label>
          <label>Mật khẩu ban đầu (ít nhất 12 ký tự)<input id="cloudUserPassword" type="password" required minlength="12" autocomplete="new-password"></label>
          <button class="primary" type="submit">Tạo tài khoản</button>
        </form></article>
      <article class="card span-12"><h3>📚 Thêm bài luyện</h3>
        <form id="newLessonForm" class="formstack"><label>Mã bài (duy nhất)<input id="newLessonId" placeholder="G3-ANIMALS-99" required></label>
        <label>Khối lớp<select id="newLessonGrade">${[1,2,3,4,5].map(x=>`<option value="${x}">${x}</option>`).join('')}</select></label>
        <label>Chủ đề<input id="newLessonTopic" placeholder="Animals" required></label>
        <label>Câu tiếng Anh<input id="newLessonText" placeholder="I can see a little dog." required></label>
        <button type="submit" class="primary">Thêm bài</button></form></article></div>`;
    document.querySelectorAll('[data-toggle-user]').forEach(btn=>btn.onclick=async()=>{
      try{await api(`/api/v1/admin/users/${encodeURIComponent(btn.dataset.toggleUser)}/active?active=${btn.dataset.active}`,{method:'PATCH'});toast('Đã cập nhật trạng thái tài khoản.');renderAdminEnhanced();}
      catch(err){toast(err.message,true)}});
    $('#assignStudent').onsubmit=async e=>{e.preventDefault();const fd=new FormData();fd.append('teacher_id',$('#assignTeacher').value);fd.append('student_id',$('#assignLearner').value);
      try{await api('/api/v1/admin/teacher-students',{method:'POST',body:fd});toast('Đã phân công HS cho GV.');}catch(err){toast(err.message,true)}};
    $('#cloudNewUser').onsubmit=async e=>{e.preventDefault();try{
      const role=$('#cloudUserRole').value;
      await api('/api/v1/admin/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        full_name:$('#cloudUserName').value,email:$('#cloudUserEmail').value,
        role,grade:role==='student'?Number($('#cloudUserGrade').value):null,password:$('#cloudUserPassword').value
      })});toast('Đã tạo tài khoản. Hãy gửi thông tin đăng nhập qua kênh an toàn.');renderAdminEnhanced();
    }catch(err){toast(err.message,true)}};
    $('#newLessonForm').onsubmit=async e=>{e.preventDefault();try{await api('/api/v1/admin/lessons',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({id:$('#newLessonId').value,grade:Number($('#newLessonGrade').value),topic:$('#newLessonTopic').value,target_text:$('#newLessonText').value,hint:'Listen and repeat.',focus_sound:''})});toast('Thêm bài thành công.');renderAdminEnhanced();}catch(err){toast(err.message,true)}};
  }catch(err){toast(err.message,true)}
}
renderAdmin=renderAdminEnhanced;
/* BrightSpeak V6: avatar-based face-to-face, independent camera controls,
   three real spoken turns per day, and a consistent teacher/admin design.
   Works without camera; never silently substitutes synthetic AI. */
let v6CameraFacing='user', v6Mirrored=true, v6CameraBusy=false, v6SpeakingTimer=null;
let v6LastStatus='Sẵn sàng luyện nói';
function v6R(n){return Math.max(0,Math.min(3,Number(n)||0));}
function v6GoalMarkup(goal){
  const count=Number(goal?.count||0),n=v6R(count);
  return `<div class="goal-panel"><div class="goal-head"><div><span class="eyebrow">MỤC TIÊU MỖI NGÀY</span><h3>🎯 Em nói ít nhất 3 câu tiếng Anh</h3></div><span class="goal-pill">${n}/3 câu</span></div>
   <div class="goal-dots">${[0,1,2].map(i=>`<span class="${i<n?'done':''}">${i<n?'✓':i+1}</span>`).join('')}</div>
   <p>${count>=3?'🌟 Hoàn thành mục tiêu! Em giỏi lắm!':'Em hãy nói thêm '+Math.max(0,3-count)+' câu với Bibi nhé!'} <small>Chỉ tính lượt nói qua microphone được AI nhận dạng, không tính gõ chữ.</small></p></div>`;
}
async function v6FetchGoal(){try{return await api('/api/v1/speaking/today');}catch{return {count:0,target:3}}}
function v6UpdateGoal(goal){for(const el of document.querySelectorAll('[data-daily-goal]'))el.innerHTML=v6GoalMarkup(goal);}
function v6AvatarTalking(talking){const el=document.querySelector('.bibi-avatar');if(!el)return;el.classList.toggle('talking',!!talking);}
let v6TurnText={bibi:'',student:''};
function v6DisplaySentence(t,who){
 if(!t)return;
 const fragment=String(t).trim();if(!fragment)return;
 const previous=v6TurnText[who]||'';
 const combined=fragment.startsWith(previous)&&previous ? fragment : (previous ? previous+' '+fragment : fragment);
 v6TurnText[who]=combined.slice(-2000);
 const caption=$('#'+(who==='bibi'?'bibiSubtitle':'learnerSubtitle'));
 if(caption)caption.textContent=v6TurnText[who];
 if(who==='bibi')v6AvatarTalking(true);
 const chat=$('#liveTranscript');if(!chat)return;
 let bubble=chat.querySelector('.bubble[data-stream="'+who+'"]');
 if(!bubble){bubble=document.createElement('div');bubble.dataset.stream=who;bubble.className='bubble '+(who==='bibi'?'ai':'user');chat.appendChild(bubble);}
 bubble.textContent=(who==='bibi'?'Bibi: ':'Em: ')+v6TurnText[who];chat.scrollTop=chat.scrollHeight;
}
const v6RenderOldDashboard=renderDashboard;
renderDashboard=async function(){await v6RenderOldDashboard();if(state.user?.role==='student'){
  const grid=$('#content .grid');if(grid){const el=document.createElement('section');el.className='span-12';el.setAttribute('data-daily-goal','');grid.prepend(el);v6UpdateGoal(await v6FetchGoal());}
}};
const v6RenderOldProgress=renderProgress;
renderProgress=async function(){await v6RenderOldProgress();if(state.user?.role==='student'){
 const grid=$('#content .grid');if(grid){const el=document.createElement('section');el.className='span-12';el.setAttribute('data-daily-goal','');grid.prepend(el);v6UpdateGoal(await v6FetchGoal());}
}};
// Count only microphone-based voice_chat and look/speak, never typed chat.
const v6OldVoiceSend=sendChatVoice;
sendChatVoice=async function(){await v6OldVoiceSend();v6UpdateGoal(await v6FetchGoal());};
const v6OldLookSubmit=submitLookEnhanced;
submitLookEnhanced=async function(){await v6OldLookSubmit();v6UpdateGoal(await v6FetchGoal());};
// V9 keeps V6's daily-goal / teacher / admin helpers, but replaces its Live implementation.
// Consent handling belongs to V10 renderLive() only.

async function renderTeacherV6(){
 $('#content').innerHTML='<div class="card"><div class="empty">Đang tải bảng giáo viên…</div></div>';
 try{const d=await api('/api/v1/teacher/overview');
 const done=d.students.filter(s=>Number(s.speaking_today)>=3).length;
 $('#content').innerHTML=`<section class="hero-banner dash-banner"><p class="eyebrow" style="color:#e9e2ff">BRIGHTSPEAK · TEACHER STUDIO</p><h1>Xin chào, thầy/cô! 👩‍🏫</h1><p>Theo dõi hoạt động tiếng Anh của học sinh đã được phân công và khuyến khích các em nói ít nhất 3 câu/ngày.</p></section>
 <div class="grid"><article class="card span-4 metric"><div><small>HS đang phụ trách</small><b>${d.total_students}</b></div><span>👩‍🎓</span></article>
 <article class="card span-4 metric"><div><small>Đạt mục tiêu hôm nay</small><b>${done}/${d.total_students}</b></div><span>🎯</span></article>
 <article class="card span-4 metric"><div><small>Mục tiêu</small><b>3 câu</b></div><span>🎤</span></article>
 <article class="card span-12"><h3>📊 Bảng theo dõi học sinh</h3><p>Chỉ hiển thị học sinh do admin phân công. Điểm phát âm mang tính hỗ trợ luyện tập, không thay thế đánh giá của GV.</p>
 <div class="table-wrap"><table class="data-table"><thead><tr><th>Học sinh</th><th>Lớp</th><th>Số lượt phát âm</th><th>TB</th><th>Hôm nay</th><th>Hoạt động cuối</th></tr></thead><tbody>
 ${d.students.map(s=>`<tr><td><b>${esc(s.full_name)}</b><br/><small>${esc(s.email)}</small></td><td>${s.grade??'—'}</td><td>${s.attempts}</td><td>${s.average_score??'—'}</td><td><span class="goal-mini ${s.speaking_today>=3?'done':''}">${s.speaking_today}/3 câu</span></td><td>${s.last_practice?new Date(s.last_practice).toLocaleDateString('vi-VN'):'—'}</td></tr>`).join('')||'<tr><td colspan="6">Chưa có học sinh được phân công.</td></tr>'}</tbody></table></div></article></div>`;
 }catch(err){toast(err.message,true)}
}
renderTeacher=renderTeacherV6;
const v6AdminOld=renderAdminEnhanced;
renderAdmin=async function(){await v6AdminOld();const root=$('#content');if(root && root.querySelector('.grid')){
 const hero=document.createElement('section');hero.className='hero-banner dash-banner';hero.innerHTML='<p class="eyebrow" style="color:#e9e2ff">BRIGHTSPEAK · ADMIN STUDIO</p><h1>Quản trị hệ thống ⚙️</h1><p>Quản lý tài khoản, phân công GV–HS và xây dựng ngân hàng bài học trong cùng giao diện BrightSpeak AI.</p>';
 root.prepend(hero);
}};

// V11 Admin Studio: role-aware filtering, invitation workflow and actionable
// dashboard. Old admin screens remain declared for backwards compatibility but
// only this final renderer is dispatched.
async function renderAdminV11(){
  $('#content').innerHTML='<section class="card"><div class="empty">Đang tải BrightSpeakAI Admin Studio…</div></section>';
  try{
    const [d,health]=await Promise.all([api('/api/v1/admin/overview'),fetch('/api/v1/system/health').then(r=>r.json())]);
    const users=d.users||[],teachers=users.filter(u=>u.role==='teacher'),students=users.filter(u=>u.role==='student');
    const active=users.filter(u=>u.active).length;
    const emailReady=!!health.email_enabled;
    $('#content').innerHTML=`<section class="hero-banner dash-banner v11-admin-hero"><span class="eyebrow">BRIGHTSPEAKAI · ADMIN STUDIO</span><h1>Quản trị học tập và tài khoản</h1><p>Quản lý người dùng, lời mời, phân công GV–HS và ngân hàng câu luyện trong một không gian.</p></section>
    <div class="grid v11-admin-stats"><article class="card span-3 metric"><div><small>👥 Tài khoản</small><b>${users.length}</b></div></article><article class="card span-3 metric"><div><small>✅ Đang hoạt động</small><b>${active}</b></div></article><article class="card span-3 metric"><div><small>📚 Bài luyện</small><b>${d.lesson_count}</b></div></article><article class="card span-3 metric"><div><small>🎤 Lượt luyện</small><b>${d.attempt_count}</b></div></article></div>
    <section class="v11-admin-shell"><nav class="v11-admin-tabs" aria-label="Các nhóm quản trị"><button class="active" type="button" data-admin-tab="users">👤 Người dùng</button><button type="button" data-admin-tab="create">✉️ Tạo tài khoản</button><button type="button" data-admin-tab="assign">👩‍🏫 Phân công lớp</button><button type="button" data-admin-tab="lessons">📖 Học liệu</button></nav>
    <div class="v11-admin-panel" data-admin-panel="users"><div class="v11-admin-section-title"><div><h3>Danh sách tài khoản</h3><p>Đã kích hoạt / đang hoạt động được thể hiện độc lập; không hiển thị mật khẩu.</p></div></div>
      <div class="v11-admin-filters"><input id="v11UserSearch" type="search" placeholder="🔍 Tìm theo tên hoặc email" aria-label="Tìm tài khoản"/><select id="v11RoleFilter" aria-label="Lọc vai trò"><option value="all">Tất cả vai trò</option><option value="student">Học sinh</option><option value="teacher">Giáo viên</option><option value="admin">Quản trị</option></select><select id="v11StatusFilter" aria-label="Lọc trạng thái"><option value="all">Mọi trạng thái</option><option value="active">Đang hoạt động</option><option value="inactive">Đã khóa</option><option value="unverified">Chờ kích hoạt</option></select></div>
      <div class="table-wrap"><table class="data-table v11-admin-table"><thead><tr><th>Người dùng</th><th>Vai trò</th><th>Lớp</th><th>Kích hoạt</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody id="v11UserRows"></tbody></table></div><p id="v11UserCount" class="hintnote" aria-live="polite"></p></div>
    <div class="v11-admin-panel hidden" data-admin-panel="create"><div class="v11-admin-section-title"><div><h3>✉️ Mời người dùng mới</h3><p>Người nhận tự đặt mật khẩu qua liên kết một lần. Không gửi mật khẩu qua email.</p></div><span class="v11-service ${emailReady?'ready':'offline'}">${emailReady?'● Email service đã cấu hình':'● Chưa cấu hình email service'}</span></div>
      ${emailReady?'':`<p class="v11-config-note">Để gửi lời mời qua Internet: thiết lập <code>RESEND_API_KEY</code>, <code>MAIL_FROM</code> và <code>PUBLIC_BASE_URL</code> ở môi trường máy chủ. Admin cũng có thể tạo tài khoản trực tiếp ở phần dưới, không cần email.</p>`}
      <form id="v11InviteForm" class="v11-admin-form"><label>Họ và tên<input id="inviteName" required minlength="2" maxlength="80" placeholder="Nguyễn Văn A"/></label><label>Email đăng nhập<input id="inviteEmail" required type="email" autocomplete="off" placeholder="person@example.com"/></label><label>Vai trò<select id="inviteRole"><option value="student">Học sinh</option><option value="teacher">Giáo viên</option></select></label><label id="inviteGradeGroup">Lớp<select id="inviteGrade">${[1,2,3,4,5].map(x=>`<option value="${x}">Lớp ${x}</option>`).join('')}</select></label><label class="v11-guardian v11-admin-full"><input type="checkbox" id="inviteGuardian"/> Đối với HS: đã có sự đồng ý phù hợp của người giám hộ trước khi tạo tài khoản.</label><div class="v11-admin-full"><button type="submit" class="primary" ${emailReady?'':'disabled'}>✉️ Gửi thư mời kích hoạt</button></div></form>
      ${`<details class="v11-local-only"><summary>🔐 Tạo tài khoản trực tiếp (không gửi email)</summary><p class="hintnote">Chỉ Admin tạo tài khoản. Cung cấp mật khẩu ban đầu riêng cho người nhận qua kênh an toàn. Không nhập dữ liệu HS thật vào bản demo công khai.</p><form id="v11LocalCreate" class="v11-admin-form"><label>Họ tên<input id="localName" required minlength="2"/></label><label>Email<input id="localEmail" type="email" required/></label><label>Vai trò<select id="localRole"><option value="student">Học sinh</option><option value="teacher">Giáo viên</option></select></label><label>Lớp<select id="localGrade">${[1,2,3,4,5].map(x=>`<option value="${x}">Lớp ${x}</option>`).join('')}</select></label><label class="v11-guardian v11-admin-full"><input type="checkbox" id="localGuardian" /> Đối với HS: đã có sự đồng ý phù hợp của người giám hộ.</label><label>Mật khẩu ban đầu (12+ ký tự)<input type="password" id="localPassword" required minlength="12"/></label><label>Xác nhận mật khẩu<input type="password" id="localConfirm" required minlength="12"/></label><button type="submit" class="secondary v11-admin-full">Tạo tài khoản</button></form></details>`}</div>
    <div class="v11-admin-panel hidden" data-admin-panel="assign"><div class="v11-admin-section-title"><div><h3>👩‍🏫 Phân công HS cho GV</h3><p>GV chỉ truy cập báo cáo các HS được phân công; giới hạn quyền được kiểm tra trên backend.</p></div></div><form id="v11AssignForm" class="v11-admin-form"><label>Giáo viên<select id="v11AssignTeacher">${teachers.map(u=>`<option value="${esc(u.id)}">${esc(u.full_name)}</option>`).join('')}</select></label><label>Học sinh<select id="v11AssignStudent">${students.map(u=>`<option value="${esc(u.id)}">${esc(u.full_name)} · lớp ${u.grade||'—'}</option>`).join('')}</select></label><button type="submit" class="primary v11-admin-full" ${teachers.length&&students.length?'':'disabled'}>Lưu phân công</button></form></div>
    <div class="v11-admin-panel hidden" data-admin-panel="lessons"><div class="v11-admin-section-title"><div><h3>📚 Thêm học liệu</h3><p>Bài luyện nguyên bản theo lớp và chủ đề, không sao chép nguyên văn SGK.</p></div></div><form id="v11LessonForm" class="v11-admin-form"><label>Mã bài (duy nhất)<input id="v11LessonId" required minlength="3" placeholder="G3-ANIMALS-99"/></label><label>Khối lớp<select id="v11LessonGrade">${[1,2,3,4,5].map(x=>`<option value="${x}">Lớp ${x}</option>`).join('')}</select></label><label>Chủ đề<input id="v11LessonTopic" required placeholder="Animals"/></label><label>Câu tiếng Anh<input id="v11LessonText" required placeholder="I can see a little dog."/></label><button type="submit" class="primary v11-admin-full">➕ Thêm bài luyện</button></form></div>
    </section>`;
    const tabs=document.querySelectorAll('[data-admin-tab]');
    tabs.forEach(btn=>btn.onclick=()=>{tabs.forEach(x=>x.classList.toggle('active',x===btn));document.querySelectorAll('[data-admin-panel]').forEach(el=>el.classList.toggle('hidden',el.dataset.adminPanel!==btn.dataset.adminTab));});
    function drawRows(){const term=$('#v11UserSearch').value.toLocaleLowerCase('vi').trim(),role=$('#v11RoleFilter').value,status=$('#v11StatusFilter').value;
      const filtered=users.filter(u=>(u.full_name+' '+u.email).toLocaleLowerCase('vi').includes(term)&&(role==='all'||u.role===role)&&(status==='all'||(status==='active'&&u.active)||(status==='inactive'&&!u.active)||(status==='unverified'&&!u.verified)));
      $('#v11UserRows').innerHTML=filtered.map(u=>`<tr><td><b>${esc(u.full_name)}</b><small class="v11-block">${esc(u.email)}</small></td><td><span class="v11-role ${esc(u.role)}">${u.role==='student'?'Học sinh':u.role==='teacher'?'Giáo viên':'Admin'}</span></td><td>${u.grade??'—'}</td><td>${u.verified?'✅':'Chưa'}</td><td><span class="v11-service ${u.active?'ready':'offline'}">${u.active?'Đang mở':'Đã khóa'}</span></td><td><button type="button" class="secondary v11-small-action" data-user-id="${esc(u.id)}" data-next-active="${u.active?'false':'true'}" ${u.id===state.user.id?'disabled title="Không thể tự khóa chính mình"':''}>${u.active?'Khóa':'Mở khóa'}</button></td></tr>`).join('')||'<tr><td colspan="6">Không tìm thấy tài khoản phù hợp.</td></tr>';
      $('#v11UserCount').textContent=`Đang hiển thị ${filtered.length}/${users.length} tài khoản.`;
      $('#v11UserRows').querySelectorAll('[data-user-id]').forEach(btn=>btn.onclick=async()=>{
        if(btn.dataset.nextActive==='false'&&!confirm('Khóa tài khoản này? Người dùng sẽ không đăng nhập được.'))return;
        btn.disabled=true;try{await api(`/api/v1/admin/users/${encodeURIComponent(btn.dataset.userId)}/active?active=${btn.dataset.nextActive}`,{method:'PATCH'});toast('Đã cập nhật trạng thái.');renderAdminV11();}catch(err){toast(err.message,true);btn.disabled=false}
      });
    }
    ['v11UserSearch','v11RoleFilter','v11StatusFilter'].forEach(id=>$(`#${id}`).addEventListener('input',drawRows));drawRows();
    $('#inviteRole').onchange=()=>{$('#inviteGradeGroup').classList.toggle('hidden',$('#inviteRole').value!=='student');$('#inviteGuardian').required=$('#inviteRole').value==='student';};$('#inviteRole').onchange();
    $('#v11InviteForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{
      const role=$('#inviteRole').value;const body={full_name:$('#inviteName').value.trim(),email:$('#inviteEmail').value.trim(),role,grade:role==='student'?Number($('#inviteGrade').value):null,guardian_confirmed:$('#inviteGuardian').checked};
      const result=await api('/api/v1/admin/invitations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      toast(result.message);renderAdminV11();
    }catch(err){toast(err.message,true);b.disabled=false}};
    if($('#v11LocalCreate'))$('#v11LocalCreate').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;const role=$('#localRole').value,pw=$('#localPassword').value;
      if(pw!==$('#localConfirm').value){toast('Hai mật khẩu không trùng khớp.',true);b.disabled=false;return;}
      try{await api('/api/v1/admin/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({full_name:$('#localName').value,email:$('#localEmail').value,role,grade:role==='student'?Number($('#localGrade').value):null,password:pw,guardian_confirmed:$('#localGuardian').checked})});toast('Đã tạo tài khoản (không gửi email).');renderAdminV11();}
      catch(err){toast(err.message,true);b.disabled=false}
    };
    $('#v11AssignForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;const fd=new FormData();fd.append('teacher_id',$('#v11AssignTeacher').value);fd.append('student_id',$('#v11AssignStudent').value);
      try{await api('/api/v1/admin/teacher-students',{method:'POST',body:fd});toast('Đã lưu phân công GV–HS.');}catch(err){toast(err.message,true)}finally{b.disabled=false}
    };
    $('#v11LessonForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;
      try{await api('/api/v1/admin/lessons',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:$('#v11LessonId').value,grade:Number($('#v11LessonGrade').value),topic:$('#v11LessonTopic').value,target_text:$('#v11LessonText').value,hint:'Listen and repeat.',focus_sound:''})});toast('Đã thêm bài luyện.');renderAdminV11();}
      catch(err){toast(err.message,true);b.disabled=false}
    };
  }catch(err){$('#content').innerHTML=`<section class="card">⚠️ ${esc(err.message)}</section>`;toast(err.message,true);}
}
renderAdmin=renderAdminV11;

/* V12 – Teacher Studio: teacher can author and assign age-appropriate practice
   only to students already assigned by Admin. Backend enforces the same scope. */
async function renderTeacherV12(){
  $('#content').innerHTML='<section class="card"><p>Đang tải học sinh và bài GV giao…</p></section>';
  try{
    const [overview,items]=await Promise.all([api('/api/v1/teacher/overview'),api('/api/v1/teacher/lessons')]);
    const learners=overview.students||[],lessons=items.lessons||[];
    let editingId=null;
    $('#content').innerHTML=`<div class="v11-admin-hero"><h1>👩‍🏫 Teacher Studio</h1><p>Tạo từ vựng hoặc câu luyện đọc theo khối lớp, chọn học sinh được giao bài và theo dõi kết quả. Nội dung do GV tự biên soạn và phê duyệt trước khi sử dụng.</p></div>
      <div class="grid v11-admin-stats">
        <article class="card span-4 metric"><div><small>Học sinh phụ trách</small><b>${learners.length}</b></div><span>👩‍🎓</span></article>
        <article class="card span-4 metric"><div><small>Bài GV đã tạo</small><b>${lessons.filter(x=>x.active).length}</b></div><span>📚</span></article>
        <article class="card span-4 metric"><div><small>Mục tiêu HS</small><b>3 câu/ngày</b></div><span>🎯</span></article>
      </div>
      <div class="grid" style="margin-top:16px">
        <section class="span-7 v12-teacher-card"><h3>✏️ Biên soạn từ, mẫu câu cho học sinh</h3><p class="hintnote">Chọn lớp, nội dung ngắn và HS cần giao. Bài GV tự tạo chỉ hiện trong tài khoản HS được chọn, không tự phát cho toàn trường.</p>
          <form id="v12TeacherForm" class="v12-teacher-form">
            <label>Khối lớp<select id="v12Grade" required>${[1,2,3,4,5].map(g=>`<option value="${g}" ${g===3?'selected':''}>Lớp ${g}</option>`).join('')}</select></label>
            <label>Chủ đề / Unit<input id="v12Topic" maxlength="80" minlength="2" required placeholder="Ví dụ: My pets"/></label>
            <label class="full">Từ hoặc câu HS sẽ nghe và nói lại<input id="v12Target" maxlength="180" minlength="1" required placeholder="Ví dụ: I like cats."/></label>
            <label class="full">Gợi ý của GV (tùy chọn)<textarea id="v12Hint" rows="2" maxlength="200" placeholder="Phát âm chậm rồi nói lại cả câu."></textarea></label>
            <div class="full"><strong>Giao cho HS đang phụ trách và đúng khối lớp</strong><div id="v12TeacherLearners" class="v12-learner-choices"></div>
              <p class="hintnote">Chỉ HS được chọn mới thấy bài trong Luyện phát âm và Face-to-face. Admin phân công HS cho GV trước khi giao bài.</p></div>
            <div class="full v12-teacher-actions"><button class="primary" id="v12SaveLesson" type="submit">➕ Tạo và giao bài</button><button class="secondary" id="v12ResetEdit" type="button">Xóa nội dung đang nhập</button></div>
          </form>
        </section>
        <section class="span-5 v12-teacher-card"><h3>📖 Bài GV đã biên soạn</h3><div id="v12LessonList" class="v12-lesson-list"></div></section>
        <section class="span-12 v12-teacher-card"><h3>📈 Tiến độ học sinh</h3><div class="table-wrap"><table class="data-table"><thead><tr><th>Học sinh</th><th>Lớp</th><th>Lượt luyện</th><th>Điểm trung bình</th><th>Số câu hôm nay</th></tr></thead><tbody>${learners.map(x=>`<tr><td><strong>${esc(x.full_name)}</strong></td><td>${x.grade||'—'}</td><td>${x.attempts||0}</td><td>${x.average_score??'—'}</td><td>${x.speaking_today||0}/3</td></tr>`).join('')||'<tr><td colspan="5">Chưa được Admin phân công học sinh.</td></tr>'}</tbody></table></div></section>
      </div>`;
    const gradeField=$('#v12Grade'), list=$('#v12LessonList'), form=$('#v12TeacherForm');
    function drawLearners(selected=[]){
      const grade=Number(gradeField.value),inGrade=learners.filter(x=>Number(x.grade)===grade);
      $('#v12TeacherLearners').innerHTML=inGrade.map(x=>`<label><input type="checkbox" name="v12Learner" value="${esc(x.id)}" ${selected.includes(x.id)?'checked':''}/><span>${esc(x.full_name)} · lớp ${x.grade}</span></label>`).join('') || '<span>Chưa có HS lớp này được phân công.</span>';
    }
    function drawLessons(){
      list.innerHTML=lessons.filter(x=>x.active).map(x=>`<div class="v11-suggestion"><small>📚 ${esc(x.topic)} · lớp ${x.grade}</small><strong>${esc(x.target_text)}</strong><p class="hintnote">Đã giao ${x.student_ids.length} HS</p><div class="v12-teacher-actions"><button type="button" class="secondary" data-edit-lesson="${esc(x.id)}">✏️ Sửa / Giao lại</button><button type="button" class="secondary" data-remove-lesson="${esc(x.id)}">🗑 Ẩn bài</button></div></div>`).join('')||'<p class="muted">Chưa tạo bài riêng. Hãy bắt đầu bằng một câu ngắn phù hợp với lớp.</p>';
      list.querySelectorAll('[data-edit-lesson]').forEach(b=>b.onclick=()=>{
        const lesson=lessons.find(x=>x.id===b.dataset.editLesson);if(!lesson)return;
        editingId=lesson.id;gradeField.value=lesson.grade;$('#v12Topic').value=lesson.topic;
        $('#v12Target').value=lesson.target_text;$('#v12Hint').value=lesson.hint||'';
        drawLearners(lesson.student_ids);$('#v12SaveLesson').textContent='💾 Lưu chỉnh sửa và giao bài';
        form.scrollIntoView({behavior:'smooth',block:'start'});
      });
      list.querySelectorAll('[data-remove-lesson]').forEach(b=>b.onclick=async()=>{
        if(!confirm('Ẩn bài này khỏi tài khoản học sinh? Lịch sử cũ được giữ lại.'))return;
        try{await api('/api/v1/teacher/lessons/'+encodeURIComponent(b.dataset.removeLesson),{method:'DELETE'});
          toast('Đã ẩn bài luyện.');renderTeacherV12();}catch(e){toast(e.message,true)}
      });
    }
    gradeField.onchange=()=>drawLearners();drawLearners();drawLessons();
    $('#v12ResetEdit').onclick=()=>{editingId=null;form.reset();gradeField.value='3';drawLearners();$('#v12SaveLesson').textContent='➕ Tạo và giao bài';};
    form.onsubmit=async e=>{
      e.preventDefault();const btn=$('#v12SaveLesson');btn.disabled=true;
      const grade=Number(gradeField.value),target=$('#v12Target').value.trim();
      const limit={1:8,2:12,3:18,4:24,5:30}[grade];
      if(target.split(/\s+/).length>limit){toast(`Lớp ${grade}: tối đa ${limit} từ/câu để luyện tập.`,true);btn.disabled=false;return;}
      const selected=[...document.querySelectorAll('input[name=v12Learner]:checked')].map(x=>x.value);
      if(!selected.length){toast('Hãy chọn ít nhất một HS được phân công trong lớp này.',true);btn.disabled=false;return;}
      try{
        const body={grade,topic:$('#v12Topic').value.trim(),target_text:target,hint:$('#v12Hint').value.trim(),student_ids:selected};
        await api(editingId?'/api/v1/teacher/lessons/'+encodeURIComponent(editingId):'/api/v1/teacher/lessons',
          {method:editingId?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        toast(editingId?'Đã cập nhật và giao lại bài.':'Đã lưu và giao bài cho học sinh.');renderTeacherV12();
      }catch(err){toast(err.message,true);btn.disabled=false;}
    };
  }catch(err){$('#content').innerHTML=`<section class="card">⚠️ ${esc(err.message)}</section>`;toast(err.message,true)}
}
renderTeacher=renderTeacherV12;
