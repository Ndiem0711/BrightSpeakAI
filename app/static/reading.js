// A short guided reading can also run without a Gemini Live connection.
let readingBusy = null;
let sampleAudio=null;
function stopSample(){
  if(sampleAudio){sampleAudio.pause();sampleAudio=null;}
}
function cancelReading(){
  stopSample();
  const task=readingBusy;
  readingBusy=null;
  if(task){
    clearTimeout(task.timer);
    if(task.started && !task.stopping)task.rec.stop().catch(()=>{});
  }
  if('speechSynthesis' in window)speechSynthesis.cancel();
}
function readEnglish(text,id){
  if(readingBusy || liveActive || liveConnecting){
    toast('Em hãy kết thúc lượt hiện tại trước khi nghe mẫu.');return;
  }
  stopSample();
  if('speechSynthesis' in window)speechSynthesis.cancel();
  id=readingAudioAliases[id]||id;
  const match=/^GS([1-5])-\d+-\d+$/.exec(id||'');
  if(match){
    const clip=new Audio('/static/readings/'+match[1]+'/'+encodeURIComponent(id)+'.mp3');
    sampleAudio=clip;
    clip.play().catch(()=>{if(sampleAudio===clip)readEnglish(text);});
    return;
  }
  if(!('speechSynthesis' in window)){toast('Thiết bị chưa hỗ trợ giọng đọc. Em có thể dùng Bibi Live.',true);return;}
  speechSynthesis.cancel();
  const voice=new SpeechSynthesisUtterance(text);
  voice.lang='en-US';
  voice.rate=Number(state.user?.grade||3)<=2?.76:.86;
  voice.onerror=e=>{if(!['interrupted','canceled'].includes(e.error))toast('Chưa phát được giọng tiếng Anh. Em kiểm tra loa hoặc dùng Bibi Live.',true);};
  speechSynthesis.speak(voice);
}
function wordButtons(container,words){
  for(const word of words){
    const b=document.createElement('button');
    b.type='button';b.className='secondary';b.textContent='🔊 '+word;
    b.onclick=()=>readEnglish(word);container.appendChild(b);
  }
}
function showReadingFeedback(panel,d){
  if(!panel)return;
  panel.innerHTML='<div class="lesson-box"><strong></strong><p class="heard"></p><p class="hint"></p><div class="words toolbar"></div><button type="button" class="secondary go">Mở phần Luyện nói lại</button></div>';
  panel.querySelector('strong').textContent=d.pending?'Mình luyện thêm một chút nhé':'Em đã đọc đủ câu mẫu!';
  panel.querySelector('.heard').textContent='Bibi nghe được: '+d.heard;
  panel.querySelector('.hint').textContent=d.hint+(d.pending?' Câu này đã được lưu ở chủ đề '+d.topic+'.':'');
  wordButtons(panel.querySelector('.words'),d.words.slice(0,3));
  panel.querySelector('.go').onclick=()=>navigate('pronunciation');
}
function mountReading(panel,id,target,topic){
  if(readingBusy && panel.contains(readingBusy.btn))cancelReading();
  panel.innerHTML='<h3></h3><p class="sentence"></p><div class="toolbar"><button class="secondary listen">🔊 Nghe câu tiếng Anh</button><button class="primary record">🎤 Đọc câu này</button></div><p class="status" aria-live="polite"></p><div class="result" aria-live="polite"></div>';
  panel.querySelector('h3').textContent='Luyện đọc · '+topic;
  panel.querySelector('.sentence').textContent=target;
  panel.querySelector('.listen').onclick=()=>readEnglish(target,id);
  const btn=panel.querySelector('.record'),status=panel.querySelector('.status');
  btn.onclick=async()=>{
    if(liveActive || liveConnecting){toast('Bibi Live đang nghe. Em đọc trực tiếp vào mic nhé.');return;}
    if(readingBusy && readingBusy.btn!==btn){toast('Em hãy hoàn thành lượt đọc đang ghi trước nhé.');return;}
    if(!readingBusy){
      stopSample();
      if('speechSynthesis' in window)speechSynthesis.cancel();
      const task={rec:new WavRecorder(),btn,started:false,stopping:false};
      readingBusy=task;btn.disabled=true;
      try{
        await task.rec.start();
        if(readingBusy!==task || !btn.isConnected){await task.rec.stop();return;}
        task.started=true;btn.textContent='✓ Đọc xong';status.textContent='Đang nghe em đọc…';
        task.timer=setTimeout(()=>btn.click(),30000);
      }catch{task.rec.stream?.getTracks().forEach(t=>t.stop());if(readingBusy===task)readingBusy=null;status.textContent='Em hãy cho phép dùng mic rồi thử lại.';}
      finally{btn.disabled=false;}
      return;
    }
    const task=readingBusy;task.stopping=true;clearTimeout(task.timer);
    btn.disabled=true;status.textContent='Bibi đang nghe lại…';
    try{
      const audio=await task.rec.stop();
      if(readingBusy!==task)return;
      const form=new FormData();form.append('prompt_id',id);form.append('audio',audio,'reading.wav');
      const result=await api('/api/v1/speaking/read',{method:'POST',body:form});
      if(readingBusy!==task || !btn.isConnected)return;
      showReadingFeedback(panel.querySelector('.result'),result);
      const goal=$('#liveGoal');
      if(goal && result.goal)goal.textContent='🎯 '+result.goal.count+' / 3 câu hôm nay';
      status.textContent='';
    }catch(err){status.textContent=err.message;}
    finally{if(readingBusy===task)readingBusy=null;btn.disabled=false;btn.textContent='🎤 Đọc lại';}
  };
}
const originalPronunciation=renderPronunciation;
renderPronunciation=async function(){
  await originalPronunciation();
  if(state.page!=='pronunciation')return;
  const section=document.createElement('section');section.className='card';
  section.innerHTML='<h2>Luyện nói lại</h2><p aria-live="polite">Đang tải các câu của em…</p>';
  $('#content').prepend(section);
  try{
    const rows=await api('/api/v1/speaking/review');
    if(!section.isConnected)return;
    section.querySelector('p').textContent=rows.length?'Chọn câu em muốn luyện. Em có thể nghe từng từ trước.':'Em chưa có câu cần ôn từ Face-to-face.';
    for(const row of rows){
      const box=document.createElement('details'),summary=document.createElement('summary');
      summary.textContent=row.topic+' · '+row.target;box.appendChild(summary);
      const words=document.createElement('div');words.className='toolbar';
      wordButtons(words,row.words);box.appendChild(words);
      const reading=document.createElement('div');box.appendChild(reading);section.appendChild(box);
      mountReading(reading,row.prompt_id,row.target,row.topic);
    }
  }catch{section.querySelector('p').textContent='Chưa tải được bài ôn. Em mở lại mục Luyện phát âm để thử lại nhé.';}
};

// Pages stay on the reader's device. Verify the edition before using PDF page offsets.
const localBooks=new Map();
let knownBookList={};
function updateBookReference(prompt){
  const section=$('#bookReference');
  if(!section)return;
  section.hidden=!prompt?.book;
  if(section.hidden)return;
  const page=prompt.source_pdf || prompt.practice_pdf || prompt.lesson_pdf || prompt.book_map_pdf;
  const link=$('#sourcePage'),fileURL=localBooks.get(prompt.book);
  const mapOnly=!prompt.lesson_pdf && !prompt.source_pdf;
  $('#bookPageNote').textContent=prompt.book+' · Trang PDF '+page+
    (mapOnly?' (Book Map). File mẫu chỉ có bảng nội dung cho Unit này.':'.');
  link.hidden=!fileURL;
  if(fileURL)link.href=fileURL+'#page='+page;
  else link.removeAttribute('href');
  $('#sourceStatus').textContent=fileURL?'Đã mở đúng sách trên thiết bị.':'';
}
async function attachSourceBook(event){
  const file=event.target.files[0],prompt=currentLivePrompt(),status=$('#sourceStatus');
  if(!file || !prompt?.book)return;
  try{
    status.textContent='Đang đối chiếu tập sách…';
    knownBookList[prompt.grade] ||= await api('/api/v1/curriculum/books');
    const raw=await file.arrayBuffer();
    const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),
      b=>b.toString(16).padStart(2,'0')).join('');
    const book=knownBookList[prompt.grade].find(b=>b.sha256===digest);
    if(!book || book.name!==prompt.book)throw new Error('Em chọn đúng file '+prompt.book+' nhé.');
    if(!localBooks.has(book.name))localBooks.set(book.name,URL.createObjectURL(file));
    updateBookReference(currentLivePrompt());
  }catch(error){status.textContent=error.message;}
  finally{event.target.value='';}
}
