(function () {
  'use strict';
  var labels = {editor:'Editor (nhập tay)',phraseology:'Huấn lệnh không lưu (Doc 4444)',callsign:'Callsign hãng bay',taxiway:'Đường lăn sân bay VN',navigation:'Dẫn đường / PANS-OPS',atc:'Kiểm soát không lưu',atm:'Vùng trời / ATFM',ais:'AIS / NOTAM / FPL',met:'Khí tượng hàng không',safety:'An toàn / SMS',frms:'FRMS / mệt mỏi',conference:'Thuyết trình / hội nghị',aviation_sentence:'Câu hội thảo hàng không',legacy:'Thư viện có sẵn',general:'Từ điển phổ thông'};
  var sources = new Map(ATC.library.data.sources.map(function(s){return [s.id,s];}));
  var q=document.getElementById('q'), domain=document.getElementById('domain'), kind=document.getElementById('kind');
  Object.keys(labels).forEach(function(k){domain.add(new Option(labels[k],k));});
  var page=0, size=60;
  function render(reset) {
    if(reset) page=0;
    var hits=ATC.library.search(q.value,domain.value,kind.value), body=document.getElementById('rows');
    body.replaceChildren();
    hits.slice(page*size,(page+1)*size).forEach(function(r){
      var tr=document.createElement('tr');
      [r.abbr,r.en,r.vi].forEach(function(v){var td=document.createElement('td');td.textContent=v;tr.appendChild(td);});
      var td=document.createElement('td'), s=sources.get(r.source), details=document.createElement('details'), summary=document.createElement('summary');
      summary.textContent=(labels[r.domain]||r.domain)+' · '+(r.status==='referenced'?'Có đối chiếu nguồn':'Chưa thẩm định');
      details.appendChild(summary);
      var p=document.createElement('p');p.textContent=[r.note,s&&s.title,s&&s.note].filter(Boolean).join(' — ');details.appendChild(p);
      if(s&&s.url){var a=document.createElement('a');a.href=s.url;a.textContent='Mở nguồn (cần mạng)';a.target='_blank';a.rel='noopener noreferrer';details.appendChild(a);}
      td.appendChild(details);tr.appendChild(td);body.appendChild(tr);
    });
    document.getElementById('count').textContent=hits.length+' / '+ATC.library.data.entries.length+' mục · Trang '+(page+1)+'/'+Math.max(1,Math.ceil(hits.length/size));
    document.getElementById('prev').disabled=!page;
    document.getElementById('next').disabled=(page+1)*size>=hits.length;
  }
  q.addEventListener('input',function(){render(true);});
  domain.addEventListener('change',function(){render(true);});
  kind.addEventListener('change',function(){render(true);});
  document.getElementById('prev').onclick=function(){page--;render(false);};
  document.getElementById('next').onclick=function(){page++;render(false);};
  ATC.glossaryUI = {render: render, labels: labels};
  render(true);
})();
