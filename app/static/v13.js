/* V13 extends existing HS/GV/Admin flows without replacing their layout. */
const v13Labels={accuracy:'Khớp từ nhận dạng',fluency:'Độ trôi chảy (ước tính)',completeness:'Đủ từ đúng thứ tự',prosody:'Nhịp và âm lượng (ước tính)'};
const v13PronBase=renderPronunciation;
renderPronunciation=async function(){
  await v13PronBase();
  const transcript=$('#demoTranscript');
  if(transcript){
    const label=transcript.closest('label');
    if(state.health?.environment!=='local')label.hidden=true;
    else {const detail=document.createElement('details');detail.innerHTML='<summary>Công cụ kiểm thử local</summary>';label.before(detail);detail.appendChild(label);}
  }
  const intro=$('#content .card p');if(intro)intro.textContent='Chọn bài, nghe mẫu, thu âm và nhận gợi ý để luyện lại.';
  if(state.v13PreferredLesson){
    const id=state.v13PreferredLesson;state.v13PreferredLesson=null;
    const lesson=state.lessons.find(x=>x.id===id);
    if(lesson){state.currentLesson=lesson;$('#lessonSelect').value=id;updateLessonBox();}
  }
};
renderPronResult=function(d){
  const s=d.scores, feedback=d.audio_feedback;
  const status={matched:'Đã nghe đúng từ',substitution:'Nghe khác từ mẫu',omission:'Chưa nghe thấy',insertion:'Từ thêm'};
  $('#pronResult').innerHTML=`<p class="eyebrow">KẾT QUẢ LUYỆN TẬP · V13</p>
    <div class="score-ring" style="--score:${Number(s.overall)}"><strong>${s.overall}</strong></div>
    <p>${d.saved?'Đã lưu lượt luyện.':'Kiểm thử thủ công: không lưu vào tiến bộ học tập.'}</p>
    <div class="bars">${Object.keys(v13Labels).map(k=>`<div class="bar-row"><span>${v13Labels[k]}</span><div class="bar"><span style="width:${Number(s[k])}%"></span></div><b>${s[k]}</b></div>`).join('')}</div>
    <div class="lesson-box"><b>Máy nghe được</b><p>${esc(d.transcript)}</p><div class="v13-words">${(s.word_alignment||[]).map(w=>`<span class="v13-word ${esc(w.status)}" title="${status[w.status]}">${esc(w.expected||w.heard)}${w.status==='substitution'?` → ${esc(w.heard)}`:''}<small>${status[w.status]}</small></span>`).join('')}</div></div>
    ${feedback?`<div class="lesson-box"><b>🎧 Bibi nghe bản ghi của em</b><p>${esc(feedback.feedback_vi)}</p>${feedback.practice_words.length?`<p>Luyện thêm: ${feedback.practice_words.map(esc).join(', ')}</p>`:''}${feedback.uncertain?'<small>Bản ghi chưa rõ: em có thể ghi lại hoặc nhờ GV nghe giúp.</small>':''}</div>`:''}
    <details><summary>Thông tin đánh giá</summary><p>Điểm là chỉ báo luyện tập từ nội dung nhận dạng và tín hiệu âm thanh; chưa phải điểm chính xác từng âm vị. Từ được đánh dấu phản ánh kết quả nhận dạng, có thể khác lời em thực sự nói.</p><p>${esc(d.ai_note)}</p><small>${d.acoustic.duration}s · ${s.wpm} từ/phút · ${d.latency_ms}ms</small></details>`;
};
async function v13Recommendations(){
  if(state.user?.role!=='student')return;
  try{
    const data=await api('/api/v1/learning/recommendations');
    if(!['dashboard','progress'].includes(state.page))return;
    const section=document.createElement('section');section.className='card v13-recommendations';
    section.innerHTML='<h3>🧭 Bài luyện tiếp theo của em</h3><p>Ưu tiên bài cần ôn và chọn độ dài phù hợp với kết quả gần đây.</p><div class="v13-rec-grid">'+data.items.map(l=>`<button class="secondary v13-rec" data-lesson="${esc(l.id)}"><b>${esc(l.target_text)}</b><small>${esc(l.topic)} · ${esc(l.reason)}</small></button>`).join('')+'</div>';
    $('#content').appendChild(section);
    section.querySelectorAll('[data-lesson]').forEach(b=>b.onclick=()=>{state.v13PreferredLesson=b.dataset.lesson;navigate('pronunciation');});
  }catch(err){toast('Chưa tải được bài gợi ý. '+err.message,true);}
}
const v13DashboardBase=renderDashboard;
renderDashboard=async function(){await v13DashboardBase();await v13Recommendations();};
const v13ProgressBase=renderProgress;
renderProgress=async function(){await v13ProgressBase();await v13Recommendations();
  $('#content').querySelectorAll('.bar-row > span').forEach(el=>{if(v13Labels[el.textContent])el.textContent=v13Labels[el.textContent];});
};
const v13AdminBase=renderAdmin;
renderAdmin=async function(){
  await v13AdminBase();if(state.page!=='admin')return;
  const box=document.createElement('section');box.className='card';box.style.marginTop='20px';
  box.innerHTML='<h3>⚙️ Kết nối AI · V13</h3><p>Kiểm tra model hội thoại trước khi mở buổi luyện. Kiểm tra này gửi một yêu cầu ngắn tới AI.</p><button id="v13CheckAI" class="primary">Kiểm tra AI</button><p id="v13AIResult" role="status"></p>';
  $('#content').appendChild(box);
  $('#v13CheckAI').onclick=async()=>{const b=$('#v13CheckAI'),out=$('#v13AIResult');b.disabled=true;out.textContent='Đang kiểm tra…';try{const r=await api('/api/v1/admin/ai/check',{method:'POST'});out.textContent=(r.ok?'✓ ':'⚠ ')+r.message+(r.model?' · '+r.model:'');}catch(e){out.textContent=e.message;}finally{b.disabled=false;}};
};
