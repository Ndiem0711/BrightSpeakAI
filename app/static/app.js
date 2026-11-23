const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const state = { user: null, health: null, page: 'dashboard', lessons: [], currentLesson: null, recorder: null, wavBlob: null, captchaId: '' };

function toast(message, error=false){ const el=$('#toast'); el.textContent=message; el.className='toast show'+(error?' error':''); clearTimeout(window.__toast); window.__toast=setTimeout(()=>el.className='toast',3200); }
function esc(v=''){ return String(v).replace(/[&<>'"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function token(){ return localStorage.getItem('bs_access')||''; }
function saveTokens(data){ if(data.access_token)localStorage.setItem('bs_access',data.access_token); if(data.refresh_token)localStorage.setItem('bs_refresh',data.refresh_token); }
function logout(){ if(state.recorder){const r=state.recorder;state.recorder=null;r.stop().catch(()=>{});}if(typeof stopFeatureRecording==='function')stopFeatureRecording(); if(typeof cancelReading==="function")cancelReading(); if(typeof stopLive==='function')stopLive({closeCamera:true}); if('speechSynthesis' in window)speechSynthesis.cancel(); localStorage.removeItem('bs_access');localStorage.removeItem('bs_refresh');state.user=null;$('#appView').classList.add('hidden');$('#authView').classList.remove('hidden'); }

async function refreshAccess(){ const rt=localStorage.getItem('bs_refresh'); if(!rt)return false; try{ const r=await fetch('/api/v1/auth/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({refresh_token:rt})}); if(!r.ok)return false; const d=await r.json(); saveTokens(d); return true;}catch{return false;} }
async function api(path, options={}, retry=true){
  options.headers=options.headers||{}; if(token()) options.headers.Authorization=`Bearer ${token()}`;
  const r=await fetch(path,options);
  if(r.status===401 && retry && await refreshAccess()) return api(path,options,false);
  let data=null; const ct=r.headers.get('content-type')||''; try{ data=ct.includes('json')?await r.json():await r.text(); }catch{}
  if(!r.ok) throw new Error(data?.detail || data?.message || `HTTP ${r.status}`);
  return data;
}

async function bootstrap(){
  const accountToken=new URLSearchParams(location.search).get('account_token');
  if(accountToken){
    localStorage.removeItem('bs_access');localStorage.removeItem('bs_refresh');
    $$('.auth-form').forEach(x=>x.classList.add('hidden'));
    $('#resetForm').classList.remove('hidden');
    try{const r=await fetch('/api/v1/auth/password/link-info?token='+encodeURIComponent(accountToken));
      const data=await r.json();if(!r.ok)throw Error(data.detail||'Liên kết không hợp lệ');
      $('#resetInstructions').textContent=data.purpose==='invite'?'Lời mời đã xác thực. Hãy tự tạo mật khẩu để kích hoạt tài khoản.':'Đặt lại mật khẩu của bạn.';
    }catch(err){$('#resetInstructions').textContent='⚠ '+err.message;$('#resetForm').querySelector('button[type=submit]').disabled=true;}
    return;
  }
  try{ state.health=await (await fetch('/api/v1/system/health', {cache:'no-store'})).json(); if(state.health.environment!=='local')document.querySelector('.demo-card')?.remove(); $('#aiStatus').textContent=state.health.gemini_enabled?`Gemini: ${state.health.gemini_model} · ASR: ${state.health.asr_provider||'đang kiểm tra'}`:('ASR: Chưa có Gemini API key'); $('#aiStatus').classList.toggle('good',!!state.health.gemini_enabled); }catch{}
  if(token()){ try{ state.user=await api('/api/v1/auth/me'); showApp(); return; }catch{ logout(); } }
}

$$('[data-auth]').forEach(btn=>btn.onclick=()=>{ $$('[data-auth]').forEach(b=>b.classList.toggle('active',b===btn)); $('#loginForm').classList.toggle('hidden',btn.dataset.auth!=='login'); $('#registerForm').classList.toggle('hidden',btn.dataset.auth!=='register'); if(btn.dataset.auth==='register')loadRegistrationCaptcha();$('#forgotForm').classList.add('hidden');$('#resetForm').classList.add('hidden'); });
$('#loginForm').onsubmit=async e=>{ e.preventDefault(); try{ const d=await api('/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('#loginEmail').value,password:$('#loginPassword').value})}); saveTokens(d); state.user=d.user; showApp(); }catch(err){toast(err.message,true);} };
async function loadRegistrationCaptcha(){
  const image=$('#regCaptchaImage'); const help=$('#regCaptchaHelp');
  try{
    state.captchaId=''; image.removeAttribute('src');
    help.textContent='Đang tạo mã CAPTCHA…';
    const d=await api('/api/v1/auth/captcha');
    if(!d.captcha_id || !d.image_data)throw Error('Không tạo được CAPTCHA.');
    state.captchaId=d.captcha_id; image.src=d.image_data;
    $('#regCaptchaText').value='';help.textContent='Nhập 5 ký tự trong hình (không cần phân biệt chữ hoa, chữ thường).';
  }catch(err){help.textContent='⚠ '+err.message;toast('Không tải được CAPTCHA. Hãy bấm Mã khác.',true);}
}
$('#regCaptchaRefresh').onclick=loadRegistrationCaptcha;
$('#registerForm').onsubmit=async e=>{
  e.preventDefault();
  try{
    if(!state.captchaId)throw Error('Chưa tải mã CAPTCHA. Hãy bấm Mã khác.');
    const body={full_name:$('#regName').value,email:$('#regEmail').value,
      password:$('#regPassword').value,confirm_password:$('#regConfirm').value,
      grade:Number($('#regGrade').value),guardian_confirmed:$('#regGuardian').checked,
      captcha_id:state.captchaId,captcha_code:$('#regCaptchaText').value.trim().toUpperCase()};
    if(body.password!==body.confirm_password)throw Error('Hai mật khẩu không trùng khớp.');
    const d=await api('/api/v1/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!d.access_token || !d.user)throw Error('Máy chủ chưa trả phiên đăng nhập.');
    saveTokens(d);state.user=d.user;$('#registerForm').reset();state.captchaId='';
    showApp();toast('Đăng ký thành công!');
  }catch(err){toast(err.message,true);if(/CAPTCHA|captcha/i.test(err.message))loadRegistrationCaptcha();}
};
$('#forgotPasswordBtn').onclick=()=>{
  $$('.auth-form').forEach(x=>x.classList.add('hidden'));
  $('#forgotForm').classList.remove('hidden');
  $('#forgotEmail').value=$('#loginEmail').value||'';
};
$('#forgotBack').onclick=$('#resetBack').onclick=()=>{
  $$('.auth-form').forEach(x=>x.classList.add('hidden'));
  $('#loginForm').classList.remove('hidden');
  history.replaceState(null,'',location.pathname);
};
$('#forgotForm').onsubmit=async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;
  try{const d=await api('/api/v1/auth/password/forgot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('#forgotEmail').value})});toast(d.message);$('#forgotForm').reset();}
  catch(err){toast(err.message,true)}finally{btn.disabled=false;}
};
$('#resetForm').onsubmit=async e=>{e.preventDefault();const pw=$('#resetNewPass').value,confirm=$('#resetConfirmPass').value;
  if(pw!==confirm){toast('Hai mật khẩu không trùng nhau.',true);return;}
  const btn=e.submitter;btn.disabled=true;
  try{const d=await api('/api/v1/auth/password/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:new URLSearchParams(location.search).get('account_token'),new_password:pw,confirm_password:confirm})});
  toast(d.message);$('#resetForm').reset();$('#resetBack').click();}
  catch(err){toast(err.message,true)}finally{btn.disabled=false;}
};
$('#logoutBtn').onclick=logout;

function showApp(){
  $('#authView').classList.add('hidden');$('#appView').classList.remove('hidden');
  const u=state.user; $('#sideUser').innerHTML=`<strong>${esc(u.full_name)}</strong>${esc(u.role)}${u.grade?` · Lớp ${u.grade}`:''}`;
  $$('.teacher-only').forEach(x=>x.classList.toggle('hidden',!['teacher','admin'].includes(u.role)));
  $$('.admin-only').forEach(x=>x.classList.toggle('hidden',u.role!=='admin'));
  $$('.student-only').forEach(x=>x.classList.toggle('hidden',u.role!=='student'));
  if(u.role==='teacher') state.page='teacher'; else if(u.role==='admin') state.page='admin'; else state.page='dashboard';
  navigate(state.page);
}

$$('.nav-item').forEach(btn=>btn.onclick=()=>navigate(btn.dataset.page));
function navigate(page){ if(typeof cancelReading==="function")cancelReading(); if(state.recorder && page!==state.page){const rec=state.recorder;state.recorder=null;rec.stop().catch(()=>{});state.wavBlob=null;} if(page==='live' && 'speechSynthesis' in window)speechSynthesis.cancel(); if(state.page==='live' && page!=='live' && typeof stopLive==='function')stopLive(); if(['look','conversation'].includes(state.page) && page!==state.page && typeof stopFeatureRecording==='function')stopFeatureRecording();state.page=page; $$('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.page===page)); const titles={live:'Face-to-face AI',profile:'Hồ sơ của tôi',dashboard:'Trang chủ',pronunciation:'Luyện phát âm',conversation:'Nói với AI',look:'Look & Speak',progress:'Tiến bộ của em',teacher:'Teacher Dashboard',admin:'Admin Console'}; $('#pageTitle').textContent=titles[page]||page; ({live:renderLive,profile:renderProfile,dashboard:renderDashboard,pronunciation:renderPronunciation,conversation:renderConversation,look:renderLookSpeak,progress:renderProgress,teacher:renderTeacher,admin:renderAdmin}[page]||renderDashboard)(); }

async function renderDashboard(){
  const u=state.user; let progress=null; if(u.role==='student'){ try{progress=await api('/api/v1/progress/me')}catch{} }
  $('#content').innerHTML=`
    <section class="hero-banner"><p class="eyebrow" style="color:#dcd7ff">PERSONALIZED ENGLISH PRACTICE</p><h1>Xin chào, ${esc(u.full_name)}! 👋</h1><p>${u.role==='student'?'Hôm nay em muốn luyện phát âm, nói chuyện với Bibi hay thử một bài Look & Speak?':'Theo dõi hệ thống và tiến độ học sinh từ bảng điều khiển của bạn.'}</p></section>
    <div class="grid">
      ${u.role==='student'?`
      <article class="card span-3 metric"><div><small>Lượt luyện gần đây</small><b>${progress?.count||0}</b></div><span>🎯</span></article>
      <article class="card span-3 metric"><div><small>Điểm trung bình</small><b>${progress?.averages?.overall??'—'}</b></div><span>⭐</span></article>
      <article class="card span-3 metric"><div><small>Cần ưu tiên</small><b style="font-size:1.15rem">${esc(progress?.weakest||'Bắt đầu luyện')}</b></div><span>🧭</span></article>
      <article class="card span-3 metric"><div><small>Chế độ AI</small><b style="font-size:1.15rem">${state.health?.asr_provider==='gemini'?'Gemini ASR':'ASR chưa sẵn sàng'}</b></div><span>✨</span></article>
      <article class="card span-4 feature-card" onclick="navigate('pronunciation')"><div class="icon-box">🎤</div><h3>Pronunciation Lab</h3><p>Nghe mẫu, thu âm WAV và nhận điểm Accuracy · Fluency · Completeness · Prosody.</p></article>
      <article class="card span-4 feature-card" onclick="navigate('conversation')"><div class="icon-box">💬</div><h3>Talk with Bibi</h3><p>Hội thoại ngắn theo trình độ, sửa tối đa một lỗi quan trọng mỗi lượt.</p></article>
      <article class="card span-4 feature-card" onclick="navigate('look')"><div class="icon-box">🖼️</div><h3>Look & Speak</h3><p>Chọn ảnh, mô tả bằng tiếng Anh và nhận phản hồi multimodal.</p></article>
      <article class="card span-12"><h3>Gợi ý cá nhân hóa</h3><p>${esc(progress?.recommendation||'Hoàn thành bài luyện đầu tiên để hệ thống bắt đầu cá nhân hóa.')}</p></article>`:`
      <article class="card span-6 feature-card" onclick="navigate('${u.role==='admin'?'admin':'teacher'}')"><div class="icon-box">📊</div><h3>${u.role==='admin'?'System Administration':'Student Monitoring'}</h3><p>Mở bảng điều khiển để xem dữ liệu hệ thống.</p></article>
      <article class="card span-6"><div class="icon-box">☁️</div><h3>Cloud-ready architecture</h3><p>Local dùng SQLite ổn định; cấu hình Cloud Run/Cloud SQL/GCS được tách riêng để không ảnh hưởng luồng test.</p></article>`}
    </div>`;
}

async function renderPronunciation(){
  $('#content').innerHTML=`<div class="grid"><section class="card span-7"><h3>🎤 Pronunciation Lab</h3><p>Chọn bài, nghe mẫu rồi thu âm. Trình duyệt tạo WAV PCM trực tiếp — không cần FFmpeg.</p><label>Chọn Unit hoặc bài ôn<select id="pronTopic"></select></label><label>Bài luyện<select id="lessonSelect"><option>Đang tải…</option></select></label><div id="lessonBox" class="lesson-box"></div><div class="toolbar" style="margin-top:16px"><button id="listenBtn" class="secondary">🔊 Nghe mẫu</button><button id="recordBtn" class="record-btn" title="Ghi âm">●</button><span id="recordStatus">Sẵn sàng</span></div><label style="margin-top:14px;${location.search.includes('diagnostic=1')?'':'display:none'}">Transcript kiểm thử thủ công (không phải nhận dạng thật)<input id="demoTranscript" placeholder="Để trống để Gemini API nhận dạng giọng nói" /></label><button id="analyzeBtn" class="primary wide" style="margin-top:14px" disabled>Phân tích phát âm</button></section><aside class="card span-5" id="pronResult"><div class="empty">Kết quả sẽ xuất hiện ở đây.</div></aside></div>`;
  try{ state.lessons=await api('/api/v1/lessons'); const topic=$('#pronTopic'),sel=$('#lessonSelect');
    topic.innerHTML=[...new Set(state.lessons.map(l=>l.topic))].map(t=>'<option>'+esc(t)+'</option>').join('');
    topic.onchange=()=>selectPronUnit(topic.value);
    sel.onchange=()=>{state.currentLesson=state.lessons.find(l=>l.id===sel.value);updateLessonBox();};
    selectPronUnit(state.lessons.find(l=>l.topic.startsWith('Unit 01 ·'))?.topic || topic.value); }catch(err){toast(err.message,true);}
  $('#listenBtn').onclick=()=>{const l=state.currentLesson;if(l)readEnglish(l.target_text,l.id);};
  $('#recordBtn').onclick=toggleRecording; $('#analyzeBtn').onclick=submitPronunciation;
}
function selectPronUnit(topic,id){
  if(state.recorder){const active=state.recorder;state.recorder=null;active.stop().catch(()=>{});}
  const rows=state.lessons.filter(l=>l.topic===topic),sel=$('#lessonSelect');
  $('#pronTopic').value=topic;
  sel.innerHTML=rows.map(l=>'<option value="'+esc(l.id)+'">'+esc(l.target_text+' · '+l.hint)+'</option>').join('');
  state.currentLesson=rows.find(l=>l.id===id)||rows[0];
  if(state.currentLesson){sel.value=state.currentLesson.id;updateLessonBox();}
}
function updateLessonBox(){ const l=state.currentLesson;if(!l)return;$('#lessonBox').innerHTML=`<p class="eyebrow">${esc(l.topic)} · GRADE ${l.grade}</p><div class="target-sentence">${esc(l.target_text)}</div><p>💡 ${esc(l.hint||'Listen and repeat.')}</p>`; $('#demoTranscript').value=''; state.wavBlob=null; $('#analyzeBtn').disabled=true;const record=$('#recordBtn');if(record){record.classList.remove('recording');record.textContent='●';}if($('#recordStatus'))$('#recordStatus').textContent='Sẵn sàng'; }

class WavRecorder{
  constructor(){this.chunks=[];this.context=null;this.stream=null;this.processor=null;this.source=null;this.monitor=null;this.closed=false;this.started=false;this.startTime=0;this.tooLong=false;}
  async start(){
    if(this.closed)throw Error('Bản ghi đã được hủy.');
    if(!navigator.mediaDevices?.getUserMedia)throw Error('Microphone cần trình duyệt hiện đại và HTTPS hoặc localhost.');
    const media=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    if(this.closed){media.getTracks().forEach(t=>t.stop());return;}
    this.stream=media;
    try{
      const AudioContextImpl=window.AudioContext||window.webkitAudioContext;
      this.context=new AudioContextImpl();
      this.source=this.context.createMediaStreamSource(media);
      this.processor=this.context.createScriptProcessor(2048,1,1);
      this.monitor=this.context.createGain();this.monitor.gain.value=0;
      this.chunks=[];
      this.processor.onaudioprocess=e=>{
        if(!this.closed){
          if(this.chunks.length < Math.ceil(this.context.sampleRate*28/2048))
            this.chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
          else this.tooLong=true;
        }
      };
      this.source.connect(this.processor);
      this.processor.connect(this.monitor);this.monitor.connect(this.context.destination);
      await this.context.resume();
      if(this.context.state!=='running')throw Error('AudioContext chưa hoạt động. Hãy nhấn lại nút ghi âm.');
      this.started=true;this.startTime=performance.now();
    }catch(err){await this.stop().catch(()=>{});throw err;}
  }
  async stop(){
    if(this.closed && !this.context)return null;
    this.closed=true;
    if(this.processor){this.processor.onaudioprocess=null;try{this.processor.disconnect();}catch{}this.processor=null;}
    if(this.monitor){try{this.monitor.disconnect();}catch{}this.monitor=null;}
    if(this.source){try{this.source.disconnect();}catch{}this.source=null;}
    if(this.stream){this.stream.getTracks().forEach(t=>t.stop());this.stream=null;}
    if(!this.context){this.chunks=[];return null;}
    const context=this.context;this.context=null;const rate=context.sampleRate;
    try{await context.close();}catch{}
    if(!this.started){this.chunks=[];return null;}
    const length=this.chunks.reduce((n,c)=>n+c.length,0);
    const samples=new Float32Array(length);let off=0;
    for(const chunk of this.chunks){samples.set(chunk,off);off+=chunk.length;}
    this.chunks=[];
    if(this.tooLong)throw Error('Bản ghi tối đa 28 giây. Em hãy nói một câu ngắn rồi dừng.');
    if(samples.length/rate < 0.4)throw Error('Bản ghi dưới 0,4 giây. Em hãy nói rồi mới bấm dừng.');
    let sum=0,peak=0,count=0;
    for(let i=0;i<samples.length;i+=32){const v=Math.abs(samples[i]);sum+=v*v;peak=Math.max(peak,v);count++;}
    const rms=Math.sqrt(sum/Math.max(1,count));
    if(peak<0.008 || rms<0.0015)throw Error('Microphone chưa thu được tiếng nói. Kiểm tra đúng thiết bị mic và nói gần hơn.');
    const targetRate=Math.min(rate,16000);return encodeWav(downsampleSpeech(samples,rate,targetRate),targetRate);
  }
}
function downsampleSpeech(samples,inputRate,targetRate){
  if(inputRate<=targetRate)return samples;
  const ratio=inputRate/targetRate, out=new Float32Array(Math.floor(samples.length/ratio));
  for(let i=0;i<out.length;i++){
    const from=Math.floor(i*ratio),to=Math.max(from+1,Math.min(samples.length,Math.floor((i+1)*ratio)));
    let sum=0;for(let j=from;j<to;j++)sum+=samples[j];out[i]=sum/(to-from);
  }
  return out;
}
function encodeWav(samples,rate){ const buf=new ArrayBuffer(44+samples.length*2),v=new DataView(buf); const write=(o,s)=>[...s].forEach((c,i)=>v.setUint8(o+i,c.charCodeAt(0))); write(0,'RIFF');v.setUint32(4,36+samples.length*2,true);write(8,'WAVE');write(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,rate,true);v.setUint32(28,rate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);write(36,'data');v.setUint32(40,samples.length*2,true);let o=44;for(let i=0;i<samples.length;i++,o+=2){const s=Math.max(-1,Math.min(1,samples[i]));v.setInt16(o,s<0?s*0x8000:s*0x7fff,true);} return new Blob([v],{type:'audio/wav'}); }
async function toggleRecording(){
  const btn=$('#recordBtn');if(!btn||btn.disabled)return;
  btn.disabled=true;
  const recorder=state.recorder;
  try{
    if(!recorder){
      const next=new WavRecorder();state.recorder=next;state.wavBlob=null;
      await next.start();
      if(state.recorder!==next || next.closed || !document.contains(btn))return;
      btn.classList.add('recording');btn.textContent='■';
      $('#recordStatus').textContent='Đang ghi âm… nhấn lại để dừng';$('#analyzeBtn').disabled=true;
    }else{
      state.recorder=null;const recorded=await recorder.stop();
      if(!document.contains(btn))return;
      if(!recorded||recorded.size<100){throw Error('Bản ghi quá ngắn. Em hãy thử lại.');}
      state.wavBlob=recorded;btn.classList.remove('recording');btn.textContent='●';
      $('#recordStatus').textContent=`Đã ghi ${(recorded.size/1024).toFixed(0)} KB`;
      $('#analyzeBtn').disabled=false;
    }
  }catch(err){
    if(state.recorder)await state.recorder.stop().catch(()=>{});
    state.recorder=null;state.wavBlob=null;
    if(document.contains(btn)){btn.classList.remove('recording');btn.textContent='●';$('#recordStatus').textContent='Chưa ghi được âm thanh.';}
    toast(err?.message?.includes('Bản ghi')||err?.message?.includes('Microphone chưa thu') ? err.message : (typeof micError==='function'?micError(err):'Không mở được microphone. Kiểm tra quyền micro và thử lại.'),true);
  }finally{if(document.contains(btn))btn.disabled=false;}
}
async function submitPronunciation(){ if(!state.wavBlob||!state.currentLesson)return; const btn=$('#analyzeBtn');btn.disabled=true;btn.textContent='Đang phân tích…'; const fd=new FormData();fd.append('lesson_id',state.currentLesson.id);fd.append('demo_transcript',$('#demoTranscript').value);fd.append('audio',state.wavBlob,'recording.wav'); try{const d=await api('/api/v1/pronunciation/analyze',{method:'POST',body:fd});renderPronResult(d);}catch(err){toast(err.message,true);}finally{btn.disabled=false;btn.textContent='Phân tích phát âm';} }
function renderPronResult(d){ const s=d.scores;$('#pronResult').innerHTML=`<p class="eyebrow">KẾT QUẢ LUYỆN TẬP · ${esc(d.ai_mode.toUpperCase())}</p><div style="display:flex;gap:20px;align-items:center"><div class="score-ring" style="--score:${s.overall}"><strong>${s.overall}</strong></div><div><h3>Good practice!</h3><p>${esc(d.ai_note)}</p></div></div><div class="bars" style="margin-top:20px">${['accuracy','fluency','completeness','prosody'].map(k=>`<div class="bar-row"><span>${k}</span><div class="bar"><span style="width:${s[k]}%"></span></div><b>${s[k]}</b></div>`).join('')}</div><div class="lesson-box"><b>Transcript</b><p>${esc(d.transcript)}</p><b>Gợi ý</b><p>${esc(s.feedback)}</p><small>Duration ${d.acoustic.duration}s · ${s.wpm} WPM${d.latency_ms?' · AI '+(d.latency_ms/1000).toFixed(1)+'s':''}</small></div>${d.keyword_ml?`<div class="lesson-box"><b>ML nhận diện từ khóa (thử nghiệm độc lập)</b><p>${esc(d.keyword_ml.keyword)} · độ tin cậy ${(100*d.keyword_ml.probability).toFixed(1)}%</p><small>Không phải chấm phát âm; mô hình chưa đánh giá trên giọng trẻ em.</small></div>`:""}`; }

function renderConversation(){ $('#content').innerHTML=`<div class="grid"><section class="card span-8"><h3>💬 Talk with Bibi</h3><p>Hội thoại thích ứng theo lớp. Có thể dùng microphone của Chrome/Edge để nhập giọng nói và TTS để nghe phản hồi.</p><div id="chat" class="chat"><div class="bubble ai">Hi! I'm Bibi. What would you like to talk about today?</div></div><div class="chat-compose"><input id="chatInput" placeholder="Type or speak in English…"/><button id="speechBtn" class="secondary">🎙️</button><button id="sendBtn" class="primary">Gửi</button></div></section><aside class="card span-4"><label>Chủ đề<input id="chatTopic" value="Daily life" /></label><p><b>Nguyên tắc phản hồi</b></p><p>✓ Ngắn gọn theo lớp<br/>✓ Sửa tối đa 1 lỗi quan trọng<br/>✓ Có câu hỏi tiếp nối<br/>✓ Không suy luận cảm xúc/tính cách</p></aside></div>`; $('#sendBtn').onclick=sendChat;$('#chatInput').onkeydown=e=>{if(e.key==='Enter')sendChat()};$('#speechBtn').onclick=startSpeechInput; }
async function sendChat(){ const input=$('#chatInput'),text=input.value.trim();if(!text)return; addBubble(text,'user');input.value=''; try{const d=await api('/api/v1/conversation/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:$('#chatTopic').value||'Daily life',text})});addBubble(d.reply,'ai');if(!liveActive && !liveWS && !liveConnecting){const u=new SpeechSynthesisUtterance(d.reply);u.lang='en-US';u.rate=.9;speechSynthesis.cancel();speechSynthesis.speak(u);}}catch(err){toast(err.message,true);} }
function addBubble(text,type){const el=document.createElement('div');el.className=`bubble ${type}`;el.textContent=text;$('#chat').appendChild(el);$('#chat').scrollTop=$('#chat').scrollHeight;}
function startSpeechInput(){ const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){toast('Trình duyệt này chưa hỗ trợ Speech Recognition. Hãy dùng Chrome/Edge hoặc gõ văn bản.',true);return;} const r=new SR();r.lang='en-US';r.interimResults=false;r.onresult=e=>$('#chatInput').value=e.results[0][0].transcript;r.onerror=()=>toast('Không nhận được giọng nói.',true);r.start(); }

function renderLookSpeak(){ $('#content').innerHTML=`<div class="grid"><section class="card span-7"><h3>🖼️ Look & Speak</h3><p>Chọn một ảnh, mô tả bằng tiếng Anh rồi để Multimodal AI đánh giá độ liên quan.</p><label>Ảnh<input id="imageInput" type="file" accept="image/*" /></label><div style="margin-top:12px"><img id="imagePreview" class="preview hidden" /></div><label style="margin-top:14px">Câu trả lời tiếng Anh<textarea id="lookAnswer" rows="4" placeholder="I can see…"></textarea></label><button id="lookBtn" class="primary wide">Phân tích ảnh + câu nói</button></section><aside id="lookResult" class="card span-5"><div class="empty">Chọn ảnh để bắt đầu.</div></aside></div>`; $('#imageInput').onchange=e=>{const f=e.target.files[0];if(f){const p=$('#imagePreview');p.src=URL.createObjectURL(f);p.classList.remove('hidden');}};$('#lookBtn').onclick=submitLook; }
async function submitLook(){const f=$('#imageInput').files[0],answer=$('#lookAnswer').value.trim();if(!f||!answer){toast('Hãy chọn ảnh và nhập câu trả lời.',true);return;}const fd=new FormData();fd.append('image',f);fd.append('answer',answer);try{const d=await api('/api/v1/multimodal/look-speak',{method:'POST',body:fd});$('#lookResult').innerHTML=`<p class="eyebrow">${esc(d.ai_mode.toUpperCase())} MULTIMODAL</p><div class="score-ring" style="--score:${d.score}"><strong>${Math.round(d.score)}</strong></div><h3 style="margin-top:20px">${esc(d.feedback)}</h3><div class="lesson-box"><b>Model sentence</b><p>${esc(d.model_sentence)}</p><b>Next question</b><p>${esc(d.next_question)}</p></div>`;}catch(err){toast(err.message,true);} }

async function renderProgress(){ $('#content').innerHTML=`<div class="card"><div class="empty">Đang tải tiến độ…</div></div>`;try{const d=await api('/api/v1/progress/me'); const a=d.averages;$('#content').innerHTML=`<div class="grid"><article class="card span-4"><p class="eyebrow">OVERALL</p><div class="metric"><b>${a?.overall??'—'}</b><span>⭐</span></div><p>${esc(d.recommendation)}</p></article><article class="card span-8"><h3>Hồ sơ năng lực gần đây</h3>${a?`<div class="bars">${['accuracy','fluency','completeness','prosody'].map(k=>`<div class="bar-row"><span>${k}</span><div class="bar"><span style="width:${a[k]}%"></span></div><b>${a[k]}</b></div>`).join('')}</div>`:'<div class="empty">Chưa có dữ liệu.</div>'}</article><article class="card span-12"><h3>Lịch sử luyện phát âm</h3><div class="table-wrap"><table class="data-table"><thead><tr><th>Chủ đề</th><th>Câu luyện</th><th>Overall</th><th>Accuracy</th><th>Fluency</th><th>AI mode</th></tr></thead><tbody>${d.attempts.map(r=>`<tr><td>${esc(r.topic)}</td><td>${esc(r.target_text)}</td><td><b>${r.overall}</b></td><td>${r.accuracy}</td><td>${r.fluency}</td><td><span class="badge ${r.ai_mode==='gemini'?'purple':''}">${esc(r.ai_mode)}</span></td></tr>`).join('')||'<tr><td colspan="6">Chưa có dữ liệu.</td></tr>'}</tbody></table></div></article></div>`;}catch(err){toast(err.message,true);} }

async function renderTeacher(){ $('#content').innerHTML=`<div class="card"><div class="empty">Đang tải dữ liệu lớp…</div></div>`;try{const d=await api('/api/v1/teacher/overview');$('#content').innerHTML=`<div class="grid"><article class="card span-4 metric"><div><small>Tổng học sinh</small><b>${d.total_students}</b></div><span>👩‍🎓</span></article><article class="card span-8"><h3>Teacher Dashboard</h3><p>Theo dõi lượt luyện và điểm trung bình; không sử dụng camera/emotion để suy luận năng lực.</p></article><article class="card span-12"><div class="table-wrap"><table class="data-table"><thead><tr><th>Học sinh</th><th>Lớp</th><th>Email</th><th>Lượt luyện</th><th>Điểm TB</th><th>Lần gần nhất</th></tr></thead><tbody>${d.students.map(s=>`<tr><td><b>${esc(s.full_name)}</b></td><td>${s.grade??'—'}</td><td>${esc(s.email)}</td><td>${s.attempts}</td><td>${s.average_score??'—'}</td><td>${s.last_practice?new Date(s.last_practice).toLocaleString():'—'}</td></tr>`).join('')}</tbody></table></div></article></div>`;}catch(err){toast(err.message,true);} }

async function renderAdmin(){ $('#content').innerHTML=`<div class="card"><div class="empty">Đang tải hệ thống…</div></div>`;try{const d=await api('/api/v1/admin/overview');$('#content').innerHTML=`<div class="grid"><article class="card span-3 metric"><div><small>Users</small><b>${d.users.length}</b></div><span>👥</span></article><article class="card span-3 metric"><div><small>Lessons</small><b>${d.lesson_count}</b></div><span>📚</span></article><article class="card span-3 metric"><div><small>Attempts</small><b>${d.attempt_count}</b></div><span>🎤</span></article><article class="card span-3 metric"><div><small>AI</small><b style="font-size:1rem">${state.health?.asr_provider==='gemini'?'Gemini ASR':'ASR chưa sẵn sàng'}</b></div><span>✨</span></article><article class="card span-12"><h3>Quản lý tài khoản</h3><div class="table-wrap"><table class="data-table"><thead><tr><th>Tên</th><th>Email</th><th>Role</th><th>Verified</th><th>Active</th></tr></thead><tbody>${d.users.map(u=>`<tr><td>${esc(u.full_name)}</td><td>${esc(u.email)}</td><td><span class="badge">${esc(u.role)}</span></td><td>${u.verified?'✓':'—'}</td><td>${u.active?'✓':'—'}</td></tr>`).join('')}</tbody></table></div></article></div>`;}catch(err){toast(err.message,true);} }

bootstrap();
